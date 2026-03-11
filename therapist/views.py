from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from .models import Therapist
from .permissions import CanManageTherapist
from .serializers import TherapistSerializer


class TherapistViewSet(viewsets.ModelViewSet):
    queryset = Therapist.objects.all()
    serializer_class = TherapistSerializer
    permission_classes = [IsAuthenticated, CanManageTherapist]
