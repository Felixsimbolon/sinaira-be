from django.db import transaction
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Inventory, TherapistSupplyAssignment
from .permissions import IsOwnerRole, IsOwnerOrSupervisor
from .serializers import (
    InventorySerializer,
    InventoryWriteSerializer,
    AssignmentReadSerializer,
    AssignmentCreateSerializer,
    AssignmentUpdateSerializer,
)


def _find_duplicate_inventory(*, nama_barang: str, lokasi: str, exclude_pk: int | None = None):
    """
    Find an existing, non-deleted Inventory row with the same (nama_barang, lokasi)
    pair using case-insensitive name matching. Whitespace is ignored.
    """
    normalized_name = (nama_barang or "").strip()
    if not normalized_name:
        return None
    qs = Inventory.objects.filter(
        is_deleted=False,
        lokasi=lokasi,
        nama_barang__iexact=normalized_name,
    )
    if exclude_pk is not None:
        qs = qs.exclude(pk=exclude_pk)
    return qs.first()


class InventoryViewSet(viewsets.ModelViewSet):
    """
    OWNER only. Daftar hanya baris is_deleted=False.
    DELETE = soft delete (200 OK).

    Duplicate handling:
      - POST dengan (nama_barang, lokasi) yang sudah ada → 409 Conflict dengan
        field ``existing_item`` agar FE bisa mengarahkan user ke halaman edit.
      - PUT yang mengganti nama menjadi collision dengan item lain di lokasi
        yang sama → 409 Conflict dengan behaviour yang sama.
    """

    permission_classes = [IsAuthenticated, IsOwnerRole]
    pagination_class = None
    http_method_names = ["get", "post", "put", "delete", "head", "options"]
    lookup_value_regex = r"[0-9]+"

    def get_queryset(self):
        return Inventory.objects.filter(is_deleted=False).order_by("nama_barang")

    def get_serializer_class(self):
        if self.action in ("create", "update"):
            return InventoryWriteSerializer
        return InventorySerializer

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def create(self, request, *args, **kwargs):
        write = InventoryWriteSerializer(data=request.data)
        write.is_valid(raise_exception=True)

        duplicate = _find_duplicate_inventory(
            nama_barang=write.validated_data.get("nama_barang", ""),
            lokasi=write.validated_data.get("lokasi", ""),
        )
        if duplicate is not None:
            return Response(
                {
                    "detail": (
                        f"Item '{duplicate.nama_barang}' sudah ada di lokasi "
                        f"{duplicate.lokasi}. Silakan edit data yang sudah ada."
                    ),
                    "code": "duplicate_inventory",
                    "existing_item": InventorySerializer(duplicate).data,
                },
                status=status.HTTP_409_CONFLICT,
            )

        instance = write.save()
        return Response(
            InventorySerializer(instance).data,
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        write = InventoryWriteSerializer(instance, data=request.data, partial=partial)
        write.is_valid(raise_exception=True)

        new_nama = write.validated_data.get("nama_barang", instance.nama_barang)
        new_lokasi = write.validated_data.get("lokasi", instance.lokasi)
        duplicate = _find_duplicate_inventory(
            nama_barang=new_nama,
            lokasi=new_lokasi,
            exclude_pk=instance.pk,
        )
        if duplicate is not None:
            return Response(
                {
                    "detail": (
                        f"Nama '{duplicate.nama_barang}' sudah dipakai item lain di lokasi "
                        f"{duplicate.lokasi}. Silakan gunakan nama yang berbeda atau edit item tersebut."
                    ),
                    "code": "duplicate_inventory",
                    "existing_item": InventorySerializer(duplicate).data,
                },
                status=status.HTTP_409_CONFLICT,
            )

        write.save()
        instance.refresh_from_db()
        return Response(InventorySerializer(instance).data, status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_deleted = True
        instance.save(update_fields=["is_deleted", "updated_at"])
        return Response(status=status.HTTP_200_OK)


class TherapistSupplyAssignmentViewSet(viewsets.ViewSet):
    """
    CRUD endpoint for therapist supply assignments.
    Only OWNER and SUPERVISOR may access.
    """

    permission_classes = [IsAuthenticated, IsOwnerOrSupervisor]

    def list(self, request):
        """GET /api/therapist-supply-assignments/"""
        qs = TherapistSupplyAssignment.objects.filter(is_deleted=False).select_related(
            "item", "therapist", "assigned_by"
        )

        # Optional filters
        item_id = request.query_params.get("item_id")
        therapist_id = request.query_params.get("therapist_id")
        assignment_status = request.query_params.get("status")

        if item_id:
            qs = qs.filter(item_id=item_id)
        if therapist_id:
            qs = qs.filter(therapist_id=therapist_id)
        if assignment_status:
            qs = qs.filter(status=assignment_status.upper())

        serializer = AssignmentReadSerializer(qs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @transaction.atomic
    def create(self, request):
        """POST /api/therapist-supply-assignments/"""
        serializer = AssignmentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        item = Inventory.objects.select_for_update().get(
            pk=data["item_id"], is_deleted=False
        )

        # Re-validate stock inside transaction (race-condition safe)
        if data["quantity_assigned"] > item.jumlah_stok:
            return Response(
                {
                    "quantity_assigned": [
                        f"Quantity melebihi stok tersedia ({item.jumlah_stok} tersisa)."
                    ]
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        usage_per_unit = item.usage_per_unit
        total_usage = data["quantity_assigned"] * usage_per_unit

        assignment = TherapistSupplyAssignment.objects.create(
            item=item,
            therapist_id=data["therapist_id"],
            quantity_assigned=data["quantity_assigned"],
            usage_per_unit=usage_per_unit,
            total_usage=total_usage,
            remaining_usage=total_usage,
            status=TherapistSupplyAssignment.Status.ACTIVE,
            notes=data.get("notes", ""),
            assigned_by=request.user,
        )

        # Deduct stock
        item.jumlah_stok -= data["quantity_assigned"]
        item.save(update_fields=["jumlah_stok", "updated_at"])

        return Response(
            AssignmentReadSerializer(assignment).data,
            status=status.HTTP_201_CREATED,
        )

    @transaction.atomic
    def partial_update(self, request, pk=None):
        """PATCH /api/therapist-supply-assignments/{id}/"""
        try:
            assignment = (
                TherapistSupplyAssignment.objects.select_for_update()
                .select_related("item")
                .get(pk=pk, is_deleted=False)
            )
        except TherapistSupplyAssignment.DoesNotExist:
            return Response(
                {"detail": "Assignment tidak ditemukan."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = AssignmentUpdateSerializer(
            data=request.data,
            context={"assignment": assignment},
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        new_quantity = data.get("quantity_assigned")

        if new_quantity is not None:
            item = Inventory.objects.select_for_update().get(pk=assignment.item_id)
            old_quantity = assignment.quantity_assigned

            # Re-validate stock inside transaction
            available = item.jumlah_stok + old_quantity
            if new_quantity > available:
                return Response(
                    {
                        "quantity_assigned": [
                            f"Quantity melebihi stok tersedia ({available} tersisa)."
                        ]
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Recalculate usage
            new_total = new_quantity * assignment.usage_per_unit
            old_total = assignment.total_usage
            usage_diff = new_total - old_total

            assignment.quantity_assigned = new_quantity
            assignment.total_usage = new_total
            assignment.remaining_usage = max(0, assignment.remaining_usage + usage_diff)

            # Adjust stock
            item.jumlah_stok = available - new_quantity
            item.save(update_fields=["jumlah_stok", "updated_at"])

        if "notes" in data:
            assignment.notes = data["notes"]

        assignment.updated_by = request.user
        assignment.save()

        return Response(
            AssignmentReadSerializer(assignment).data,
            status=status.HTTP_200_OK,
        )

    @transaction.atomic
    def destroy(self, request, pk=None):
        """DELETE /api/therapist-supply-assignments/{id}/ (soft delete)"""
        try:
            assignment = (
                TherapistSupplyAssignment.objects.select_for_update()
                .get(pk=pk, is_deleted=False)
            )
        except TherapistSupplyAssignment.DoesNotExist:
            return Response(
                {"detail": "Assignment tidak ditemukan."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Return stock
        item = Inventory.objects.select_for_update().get(pk=assignment.item_id)
        item.jumlah_stok += assignment.quantity_assigned
        item.save(update_fields=["jumlah_stok", "updated_at"])

        # Soft delete
        assignment.is_deleted = True
        assignment.deleted_at = timezone.now()
        assignment.deleted_by = request.user
        assignment.status = TherapistSupplyAssignment.Status.INACTIVE
        assignment.save()

        return Response(status=status.HTTP_200_OK)


from rest_framework.views import APIView

class SupplyTrackerView(APIView):
    """
    Endpoint read-only untuk kalkulasi pemakaian bahan per therapist dan estimasi.
    Hanya dibuka untuk SUPERVISOR / OWNER.
    """
    permission_classes = [IsAuthenticated, IsOwnerOrSupervisor]

    def get(self, request, *args, **kwargs):
        from .services import calculate_supply_tracker
        
        start_date = request.query_params.get('startDate')
        end_date = request.query_params.get('endDate')
        item_id = request.query_params.get('itemId')
        therapist_id = request.query_params.get('therapistId')

        # Convert date strings if needed
        # Service handles string-based filtering gracefully for 'YYYY-MM-DD' on native django DateFields
        if start_date and end_date and start_date > end_date:
            return Response(
                {"detail": "startDate tidak boleh lebih besar dari endDate"},
                status=status.HTTP_400_BAD_REQUEST
            )

        data = calculate_supply_tracker(
            start_date=start_date,
            end_date=end_date,
            item_id=item_id,
            therapist_id=therapist_id
        )

        return Response(data, status=status.HTTP_200_OK)

