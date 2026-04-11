from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Inventory
from .permissions import IsOwnerRole
from .serializers import InventorySerializer, InventoryWriteSerializer


class InventoryViewSet(viewsets.ModelViewSet):
    """
    OWNER only. Daftar hanya baris is_deleted=False.
    DELETE = soft delete (200 OK).
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
        write.save()
        instance.refresh_from_db()
        return Response(InventorySerializer(instance).data, status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_deleted = True
        instance.save(update_fields=["is_deleted", "updated_at"])
        return Response(status=status.HTTP_200_OK)
