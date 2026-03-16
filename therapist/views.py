from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from booking.utils import geocode_location_from_address

from .models import Therapist
from .permissions import CanManageTherapist
from .serializers import TherapistCreateSerializer, TherapistSerializer


class TherapistViewSet(viewsets.ModelViewSet):
    queryset = Therapist.objects.all()
    serializer_class = TherapistSerializer
    permission_classes = [IsAuthenticated, CanManageTherapist]

    def get_serializer_class(self):
        if self.action == 'create':
            return TherapistCreateSerializer
        return TherapistSerializer


class AdminTherapistGeocodeView(APIView):
    permission_classes = [IsAuthenticated, CanManageTherapist]

    def post(self, request, id):
        try:
            therapist = Therapist.objects.get(id=id)
        except Therapist.DoesNotExist:
            return Response(
                {
                    'error': 'Therapist tidak ditemukan',
                    'detail': f'Therapist dengan ID {id} tidak ditemukan.'
                },
                status=status.HTTP_404_NOT_FOUND
            )

        latitude, longitude = geocode_location_from_address(
            alamat=therapist.alamat or '',
            kelurahan=therapist.kelurahan or '',
            kecamatan=therapist.kecamatan or '',
            kota=therapist.kota or '',
        )

        if latitude is None or longitude is None:
            return Response(
                {
                    'error': 'Koordinat tidak ditemukan untuk therapist ini.'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        therapist.latitude = latitude
        therapist.longitude = longitude
        therapist.save(update_fields=['latitude', 'longitude', 'updated_at'])

        return Response(
            {
                'message': 'Therapist geocode updated successfully',
                'data': {
                    'id': therapist.id,
                    'latitude': therapist.latitude,
                    'longitude': therapist.longitude,
                }
            },
            status=status.HTTP_200_OK
        )
