import csv

from django.http import HttpResponse
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from booking.permissions import IsAdminOrSupervisorOrOwner

from .services import (
    CustomerNotFoundError,
    get_membership_status,
    get_membership_summary,
)


class MembershipCheckAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        phone_number = request.query_params.get('phoneNumber')

        if not phone_number:
            return Response(
                {'error': 'phoneNumber is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            membership_status = get_membership_status(phone_number)
        except CustomerNotFoundError:
            return Response(
                {'error': 'Customer tidak ditemukan'},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(membership_status, status=status.HTTP_200_OK)


def _get_min_booking(query_params):
    raw_min_booking = query_params.get('min_booking')

    if raw_min_booking in (None, ''):
        return None, None

    try:
        min_booking = int(raw_min_booking)
    except (TypeError, ValueError):
        return None, 'min_booking must be a number'

    if min_booking < 0:
        return None, 'min_booking must be greater than or equal to 0'

    return min_booking, None


class MembershipAdminView(APIView):
    permission_classes = [IsAuthenticated, IsAdminOrSupervisorOrOwner]

    def get(self, request):
        min_booking, error = _get_min_booking(request.query_params)
        if error:
            return Response({'error': error}, status=status.HTTP_400_BAD_REQUEST)

        results = get_membership_summary(
            search=request.query_params.get('search'),
            min_booking=min_booking,
            ordering=request.query_params.get('ordering'),
        )

        return Response(
            {
                'count': len(results),
                'results': results,
            },
            status=status.HTTP_200_OK,
        )


class MembershipExportCSVView(APIView):
    permission_classes = [IsAuthenticated, IsAdminOrSupervisorOrOwner]

    def get(self, request):
        min_booking, error = _get_min_booking(request.query_params)
        if error:
            return Response({'error': error}, status=status.HTTP_400_BAD_REQUEST)

        results = get_membership_summary(
            search=request.query_params.get('search'),
            min_booking=min_booking,
            ordering=request.query_params.get('ordering'),
        )

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="membership.csv"'

        writer = csv.writer(response)
        writer.writerow([
            'Nama',
            'Nomor Telepon',
            'Total Booking',
            'Total Pembayaran',
            'Layanan Terbanyak',
        ])

        for row in results:
            writer.writerow([
                row['namaCustomer'],
                row['nomorTelepon'],
                row['totalBooking'],
                row['totalPembayaran'],
                row['layananTerbanyak'],
            ])

        return response
