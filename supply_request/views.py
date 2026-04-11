from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from inventory.models import Inventory

from .models import InventoryStockHistory, SupplyRequest
from .permissions import IsSupervisorRole, IsTherapistRole
from .serializers import (
	SupplyRequestCreateSerializer,
	SupplyRequestInventoryItemSerializer,
	SupplyRequestReadSerializer,
	SupplyRequestStatusUpdateSerializer,
)


class SupplyRequestCollectionView(APIView):
	def get_permissions(self):
		if self.request.method == "POST":
			return [IsAuthenticated(), IsTherapistRole()]
		return [IsAuthenticated(), IsSupervisorRole()]

	def post(self, request):
		try:
			serializer = SupplyRequestCreateSerializer(
				data=request.data,
				context={"request": request},
			)
			serializer.is_valid(raise_exception=True)
			supply_request = serializer.save()

			output = SupplyRequestReadSerializer(supply_request)
			return Response(output.data, status=status.HTTP_201_CREATED)
		except APIException:
			raise
		except Exception:
			return Response(
				{"error": "Terjadi kesalahan server internal."},
				status=status.HTTP_500_INTERNAL_SERVER_ERROR,
			)

	def get(self, request):
		try:
			queryset = SupplyRequest.objects.select_related("item", "created_by").all()
			serializer = SupplyRequestReadSerializer(queryset, many=True)
			return Response(serializer.data, status=status.HTTP_200_OK)
		except APIException:
			raise
		except Exception:
			return Response(
				{"error": "Terjadi kesalahan server internal."},
				status=status.HTTP_500_INTERNAL_SERVER_ERROR,
			)


class MySupplyRequestListView(APIView):
	permission_classes = [IsAuthenticated, IsTherapistRole]

	def get(self, request):
		try:
			queryset = (
				SupplyRequest.objects.select_related("item", "created_by")
				.filter(created_by=request.user)
				.order_by("-created_at")
			)
			serializer = SupplyRequestReadSerializer(queryset, many=True)
			return Response(serializer.data, status=status.HTTP_200_OK)
		except APIException:
			raise
		except Exception:
			return Response(
				{"error": "Terjadi kesalahan server internal."},
				status=status.HTTP_500_INTERNAL_SERVER_ERROR,
			)


class SupplyRequestItemOptionListView(APIView):
	permission_classes = [IsAuthenticated, IsTherapistRole]

	def get(self, request):
		try:
			queryset = Inventory.objects.filter(is_deleted=False).order_by("nama_barang")
			serializer = SupplyRequestInventoryItemSerializer(queryset, many=True)
			return Response(serializer.data, status=status.HTTP_200_OK)
		except APIException:
			raise
		except Exception:
			return Response(
				{"error": "Terjadi kesalahan server internal."},
				status=status.HTTP_500_INTERNAL_SERVER_ERROR,
			)


class SupplyRequestDetailView(APIView):
	permission_classes = [IsAuthenticated, IsSupervisorRole]

	def get(self, request, id):
		try:
			supply_request = (
				SupplyRequest.objects.select_related("item", "created_by")
				.filter(pk=id)
				.first()
			)
			if supply_request is None:
				return Response(
					{"error": "Supply request tidak ditemukan."},
					status=status.HTTP_404_NOT_FOUND,
				)

			serializer = SupplyRequestReadSerializer(supply_request)
			return Response(serializer.data, status=status.HTTP_200_OK)
		except APIException:
			raise
		except Exception:
			return Response(
				{"error": "Terjadi kesalahan server internal."},
				status=status.HTTP_500_INTERNAL_SERVER_ERROR,
			)

	def patch(self, request, id):
		payload = SupplyRequestStatusUpdateSerializer(data=request.data)
		payload.is_valid(raise_exception=True)
		target_status = payload.validated_data["status"]

		try:
			with transaction.atomic():
				supply_request = (
					SupplyRequest.objects.select_related("item", "created_by")
					.select_for_update()
					.filter(pk=id)
					.first()
				)

				if supply_request is None:
					return Response(
						{"error": "Supply request tidak ditemukan."},
						status=status.HTTP_404_NOT_FOUND,
					)

				if supply_request.status != SupplyRequest.Status.PENDING:
					return Response(
						{"error": "Supply request hanya dapat diproses saat status PENDING."},
						status=status.HTTP_400_BAD_REQUEST,
					)

				if target_status == SupplyRequest.Status.APPROVED:
					item = (
						Inventory.objects.select_for_update()
						.filter(pk=supply_request.item_id, is_deleted=False)
						.first()
					)

					if item is None:
						return Response(
							{"error": "Item inventory tidak ditemukan atau sudah nonaktif."},
							status=status.HTTP_404_NOT_FOUND,
						)

					if item.jumlah_stok < supply_request.quantity:
						return Response(
							{"error": "Stok inventory tidak mencukupi untuk approval."},
							status=status.HTTP_400_BAD_REQUEST,
						)

					previous_stock = item.jumlah_stok
					new_stock = previous_stock - supply_request.quantity
					item.jumlah_stok = new_stock
					item.save(update_fields=["jumlah_stok", "updated_at"])

					InventoryStockHistory.objects.create(
						item=item,
						supply_request=supply_request,
						previous_stock=previous_stock,
						quantity_changed=-supply_request.quantity,
						new_stock=new_stock,
						changed_by=request.user,
						note="Pengurangan stok dari approval supply request.",
					)

				supply_request.status = target_status
				supply_request.reviewed_by = request.user
				supply_request.reviewed_at = timezone.now()
				supply_request.save(
					update_fields=["status", "reviewed_by", "reviewed_at", "updated_at"]
				)

			supply_request.refresh_from_db()
			output = SupplyRequestReadSerializer(supply_request)
			return Response(output.data, status=status.HTTP_200_OK)
		except APIException:
			raise
		except Exception:
			return Response(
				{"error": "Terjadi kesalahan server internal."},
				status=status.HTTP_500_INTERNAL_SERVER_ERROR,
			)
