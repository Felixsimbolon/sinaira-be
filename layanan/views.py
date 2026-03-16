from rest_framework import viewsets

from .models import Layanan
from .permissions import LayananPermission
from .serializers import LayananSerializer


class LayananViewSet(viewsets.ModelViewSet):
	queryset = Layanan.objects.all()
	serializer_class = LayananSerializer
	permission_classes = [LayananPermission]
