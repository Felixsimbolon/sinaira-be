from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Promo
from .permissions import IsAdminSupervisorOrOwner, IsOwnerOnly, PublicReadPermission
from .repositories import PromoRepository
from .serializers import PromoAdminListSerializer, PromoReadSerializer, PromoWriteSerializer
from .services import PromoService, build_promo_recommendations


class AdminPromoListCreateView(generics.ListCreateAPIView):
	permission_classes = [IsOwnerOnly]

	def __init__(self, **kwargs):
		super().__init__(**kwargs)
		self.repository = PromoRepository()
		self.service = PromoService(self.repository)

	def get_queryset(self):
		return self.repository.admin_queryset()

	def get_serializer_class(self):
		if self.request.method == "POST":
			return PromoWriteSerializer
		return PromoAdminListSerializer

	def list(self, request, *args, **kwargs):
		queryset = self.get_queryset()
		serializer = self.get_serializer(queryset, many=True)
		if not serializer.data:
			return Response({"message": "Data promo tidak tersedia", "results": []})
		return Response({"count": len(serializer.data), "results": serializer.data})

	def create(self, request, *args, **kwargs):
		serializer = self.get_serializer(data=request.data)
		serializer.is_valid(raise_exception=True)
		promo = self.service.create_promo(validated_data=serializer.validated_data, user=request.user)
		data = PromoReadSerializer(promo).data
		return Response(data, status=status.HTTP_201_CREATED)


class AdminPromoDetailView(APIView):
	permission_classes = [IsOwnerOnly]

	def __init__(self, **kwargs):
		super().__init__(**kwargs)
		self.repository = PromoRepository()
		self.service = PromoService(self.repository)

	def get_object(self, pk):
		return get_object_or_404(self.repository.admin_queryset(), pk=pk)

	def get(self, request, pk):
		promo = self.get_object(pk)
		return Response(PromoAdminListSerializer(promo).data)

	def put(self, request, pk):
		promo = self.get_object(pk)
		serializer = PromoWriteSerializer(promo, data=request.data)
		serializer.is_valid(raise_exception=True)
		promo = self.service.update_promo(promo=promo, validated_data=serializer.validated_data, user=request.user)
		return Response(PromoReadSerializer(promo).data)

	def delete(self, request, pk):
		promo = self.get_object(pk)
		self.service.soft_delete(promo=promo, user=request.user)
		return Response(status=status.HTTP_204_NO_CONTENT)


class AdminPromoArchiveView(APIView):
	permission_classes = [IsOwnerOnly]

	def __init__(self, **kwargs):
		super().__init__(**kwargs)
		self.repository = PromoRepository()
		self.service = PromoService(self.repository)

	def patch(self, request, pk):
		promo = get_object_or_404(self.repository.admin_queryset(), pk=pk)
		promo = self.service.archive_promo(promo=promo, user=request.user)
		return Response(PromoReadSerializer(promo).data)


class AdminPromoUnarchiveView(APIView):
	permission_classes = [IsOwnerOnly]

	def __init__(self, **kwargs):
		super().__init__(**kwargs)
		self.repository = PromoRepository()
		self.service = PromoService(self.repository)

	def patch(self, request, pk):
		promo = get_object_or_404(self.repository.admin_queryset(), pk=pk)
		promo = self.service.unarchive_promo(promo=promo, user=request.user)
		return Response(PromoReadSerializer(promo).data)


class PublicPromoListView(generics.ListAPIView):
	serializer_class = PromoReadSerializer
	permission_classes = [PublicReadPermission]

	def __init__(self, **kwargs):
		super().__init__(**kwargs)
		self.repository = PromoRepository()

	def get_queryset(self):
		return self.repository.public_queryset()


class PublicPromoDetailView(generics.RetrieveAPIView):
	serializer_class = PromoReadSerializer
	permission_classes = [PublicReadPermission]

	def __init__(self, **kwargs):
		super().__init__(**kwargs)
		self.repository = PromoRepository()

	def get_queryset(self):
		return self.repository.public_queryset()


class PromoRecommendationListView(APIView):
	"""
	GET /api/recommendations/promos

	Returns personalized promo recommendations for repeating customers
	(customers with ≥ 3 completed bookings). Accessible to Owner, Supervisor,
	and Admin roles only.
	"""

	permission_classes = [IsAdminSupervisorOrOwner]

	def get(self, request):
		recommendations = build_promo_recommendations()
		return Response(
			{"count": len(recommendations), "results": recommendations},
			status=status.HTTP_200_OK,
		)
