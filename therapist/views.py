from datetime import datetime

from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from booking.utils import geocode_location_from_address

from .models import Therapist, TherapistDateOverride, TherapistWeeklyAvailability
from .permissions import CanManageTherapist
from .serializers import (
    TherapistCreateSerializer,
    TherapistDateOverrideSerializer,
    TherapistSerializer,
    TherapistWeeklyAvailabilitySerializer,
)
from .utils import resolve_therapist_schedule_range


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


class AdminTherapistWeeklyScheduleView(APIView):
    permission_classes = [IsAuthenticated, CanManageTherapist]

    @staticmethod
    def _get_therapist(id):
        try:
            return Therapist.objects.get(id=id)
        except Therapist.DoesNotExist:
            return None

    def get(self, request, id):
        therapist = self._get_therapist(id)
        if therapist is None:
            return Response(
                {
                    'error': 'Therapist tidak ditemukan',
                    'detail': f'Therapist dengan ID {id} tidak ditemukan.'
                },
                status=status.HTTP_404_NOT_FOUND
            )

        queryset = TherapistWeeklyAvailability.objects.filter(therapist=therapist)
        serializer = TherapistWeeklyAvailabilitySerializer(queryset, many=True)
        return Response(
            {
                'count': queryset.count(),
                'results': serializer.data,
            },
            status=status.HTTP_200_OK
        )

    def post(self, request, id):
        therapist = self._get_therapist(id)
        if therapist is None:
            return Response(
                {
                    'error': 'Therapist tidak ditemukan',
                    'detail': f'Therapist dengan ID {id} tidak ditemukan.'
                },
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = TherapistWeeklyAvailabilitySerializer(
            data=request.data,
            context={'therapist': therapist}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {
                'message': 'Weekly schedule slot created successfully',
                'data': serializer.data,
            },
            status=status.HTTP_201_CREATED
        )


class AdminTherapistWeeklyScheduleDetailView(APIView):
    permission_classes = [IsAuthenticated, CanManageTherapist]

    @staticmethod
    def _get_slot(id, slot_id):
        try:
            return TherapistWeeklyAvailability.objects.get(id=slot_id, therapist_id=id)
        except TherapistWeeklyAvailability.DoesNotExist:
            return None

    def patch(self, request, id, slot_id):
        slot = self._get_slot(id, slot_id)
        if slot is None:
            return Response(
                {
                    'error': 'Weekly schedule slot tidak ditemukan',
                    'detail': f'Slot dengan ID {slot_id} untuk therapist {id} tidak ditemukan.'
                },
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = TherapistWeeklyAvailabilitySerializer(
            slot,
            data=request.data,
            partial=True,
            context={'therapist': slot.therapist}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {
                'message': 'Weekly schedule slot updated successfully',
                'data': serializer.data,
            },
            status=status.HTTP_200_OK
        )

    def delete(self, request, id, slot_id):
        slot = self._get_slot(id, slot_id)
        if slot is None:
            return Response(
                {
                    'error': 'Weekly schedule slot tidak ditemukan',
                    'detail': f'Slot dengan ID {slot_id} untuk therapist {id} tidak ditemukan.'
                },
                status=status.HTTP_404_NOT_FOUND
            )

        slot.delete()
        return Response(
            {
                'message': 'Weekly schedule slot deleted successfully',
            },
            status=status.HTTP_200_OK
        )


class AdminTherapistDateOverrideView(APIView):
    permission_classes = [IsAuthenticated, CanManageTherapist]

    @staticmethod
    def _get_therapist(id):
        try:
            return Therapist.objects.get(id=id)
        except Therapist.DoesNotExist:
            return None

    def get(self, request, id):
        therapist = self._get_therapist(id)
        if therapist is None:
            return Response(
                {
                    'error': 'Therapist tidak ditemukan',
                    'detail': f'Therapist dengan ID {id} tidak ditemukan.'
                },
                status=status.HTTP_404_NOT_FOUND
            )

        queryset = TherapistDateOverride.objects.filter(therapist=therapist)

        start_date_raw = request.query_params.get('start_date')
        end_date_raw = request.query_params.get('end_date')
        try:
            if start_date_raw:
                queryset = queryset.filter(date__gte=datetime.strptime(start_date_raw, '%Y-%m-%d').date())
            if end_date_raw:
                queryset = queryset.filter(date__lte=datetime.strptime(end_date_raw, '%Y-%m-%d').date())
        except ValueError:
            return Response(
                {
                    'error': 'Format tanggal tidak valid. Gunakan YYYY-MM-DD.'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = TherapistDateOverrideSerializer(queryset.order_by('date', 'start_time'), many=True)
        return Response(
            {
                'count': queryset.count(),
                'results': serializer.data,
            },
            status=status.HTTP_200_OK
        )

    def post(self, request, id):
        therapist = self._get_therapist(id)
        if therapist is None:
            return Response(
                {
                    'error': 'Therapist tidak ditemukan',
                    'detail': f'Therapist dengan ID {id} tidak ditemukan.'
                },
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = TherapistDateOverrideSerializer(
            data=request.data,
            context={'therapist': therapist}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {
                'message': 'Date override created successfully',
                'data': serializer.data,
            },
            status=status.HTTP_201_CREATED
        )


class AdminTherapistDateOverrideDetailView(APIView):
    permission_classes = [IsAuthenticated, CanManageTherapist]

    @staticmethod
    def _get_override(id, override_id):
        try:
            return TherapistDateOverride.objects.get(id=override_id, therapist_id=id)
        except TherapistDateOverride.DoesNotExist:
            return None

    def patch(self, request, id, override_id):
        override = self._get_override(id, override_id)
        if override is None:
            return Response(
                {
                    'error': 'Date override tidak ditemukan',
                    'detail': f'Override dengan ID {override_id} untuk therapist {id} tidak ditemukan.'
                },
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = TherapistDateOverrideSerializer(
            override,
            data=request.data,
            partial=True,
            context={'therapist': override.therapist}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {
                'message': 'Date override updated successfully',
                'data': serializer.data,
            },
            status=status.HTTP_200_OK
        )

    def delete(self, request, id, override_id):
        override = self._get_override(id, override_id)
        if override is None:
            return Response(
                {
                    'error': 'Date override tidak ditemukan',
                    'detail': f'Override dengan ID {override_id} untuk therapist {id} tidak ditemukan.'
                },
                status=status.HTTP_404_NOT_FOUND
            )

        override.delete()
        return Response(
            {
                'message': 'Date override deleted successfully',
            },
            status=status.HTTP_200_OK
        )


class AdminTherapistTimetableView(APIView):
    permission_classes = [IsAuthenticated, CanManageTherapist]

    def get(self, request, id):
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

        start_date_raw = request.query_params.get('start_date')
        end_date_raw = request.query_params.get('end_date')
        if not start_date_raw or not end_date_raw:
            return Response(
                {
                    'error': 'Query parameter start_date dan end_date wajib diisi (YYYY-MM-DD).'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            start_date = datetime.strptime(start_date_raw, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_raw, '%Y-%m-%d').date()
        except ValueError:
            return Response(
                {
                    'error': 'Format tanggal tidak valid. Gunakan YYYY-MM-DD.'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        if end_date < start_date:
            return Response(
                {
                    'error': 'end_date tidak boleh lebih kecil dari start_date.'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        resolved = resolve_therapist_schedule_range(therapist, start_date, end_date)
        results = []
        for item in resolved:
            results.append(
                {
                    'date': item['date'].isoformat(),
                    'source': item['source'],
                    'off': item['off'],
                    'slots': [
                        {
                            'start_time': slot['start_time'].strftime('%H:%M:%S'),
                            'end_time': slot['end_time'].strftime('%H:%M:%S'),
                        }
                        for slot in item['slots']
                    ],
                }
            )

        return Response(
            {
                'message': 'Therapist timetable retrieved successfully',
                'data': {
                    'therapist_id': therapist.id,
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat(),
                    'results': results,
                },
            },
            status=status.HTTP_200_OK
        )
