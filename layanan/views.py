from rest_framework import viewsets

from .models import Layanan, LayananKategori
from .permissions import LayananPermission
from .serializers import LayananKategoriSerializer, LayananSerializer


class LayananKategoriViewSet(viewsets.ModelViewSet):
	queryset = LayananKategori.objects.all()
	serializer_class = LayananKategoriSerializer
	permission_classes = [LayananPermission]
	lookup_field = "kategori_id"
	lookup_url_kwarg = "kategori_id"


class LayananViewSet(viewsets.ModelViewSet):
	queryset = Layanan.active_objects.select_related("kategori")
	serializer_class = LayananSerializer
	permission_classes = [LayananPermission]
	lookup_field = "layanan_id"
	lookup_url_kwarg = "layanan_id"

	def get_queryset(self):
		queryset = super().get_queryset()
		kategori_id = self.request.query_params.get("kategori_id")
		is_active = self.request.query_params.get("is_active")

		if kategori_id:
			queryset = queryset.filter(kategori__kategori_id=kategori_id)

		if is_active is not None:
			normalized = is_active.strip().lower()
			if normalized in {"true", "1", "yes"}:
				queryset = queryset.filter(is_active=True)
			elif normalized in {"false", "0", "no"}:
				queryset = queryset.filter(is_active=False)

		return queryset

	def perform_destroy(self, instance):
		instance.soft_delete()
