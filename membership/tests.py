from datetime import date, time

from rest_framework import status
from rest_framework.test import APITestCase

from booking.models import Booking


class MembershipCheckEndpointAPITest(APITestCase):
    def setUp(self):
        self.phone_number = '08123456789'

        Booking.objects.create(
            nama='Siti Rahma',
            alamat='Jl. Melati No. 1',
            kota='Jakarta',
            no_hp=self.phone_number,
            tgl_treatment=date(2026, 3, 10),
            jam_treatment=time(9, 0),
            perawatan_pilihan='Relaxing Massage',
            aromatherapy_oil=Booking.AromatherapyChoice.JASMINE,
            status=Booking.BookingStatus.COMPLETED,
        )
        Booking.objects.create(
            nama='Siti Rahma',
            alamat='Jl. Melati No. 1',
            kota='Jakarta',
            no_hp=self.phone_number,
            tgl_treatment=date(2026, 3, 9),
            jam_treatment=time(9, 0),
            perawatan_pilihan='Deep Tissue',
            aromatherapy_oil=Booking.AromatherapyChoice.LAVENDER,
            status=Booking.BookingStatus.COMPLETED,
        )
        Booking.objects.create(
            nama='Siti Rahma',
            alamat='Jl. Melati No. 1',
            kota='Jakarta',
            no_hp=self.phone_number,
            tgl_treatment=date(2026, 3, 8),
            jam_treatment=time(9, 0),
            perawatan_pilihan='Foot Reflexology',
            aromatherapy_oil=Booking.AromatherapyChoice.ROSE,
            status=Booking.BookingStatus.COMPLETED,
        )
        Booking.objects.create(
            nama='Siti Rahma',
            alamat='Jl. Melati No. 1',
            kota='Jakarta',
            no_hp=self.phone_number,
            tgl_treatment=date(2026, 3, 7),
            jam_treatment=time(9, 0),
            perawatan_pilihan='Thai Massage',
            aromatherapy_oil=Booking.AromatherapyChoice.SANDALWOOD,
            status=Booking.BookingStatus.COMPLETED,
        )
        Booking.objects.create(
            nama='Siti Rahma',
            alamat='Jl. Melati No. 1',
            kota='Jakarta',
            no_hp=self.phone_number,
            tgl_treatment=date(2026, 3, 6),
            jam_treatment=time(9, 0),
            perawatan_pilihan='Aromatherapy Massage',
            aromatherapy_oil=Booking.AromatherapyChoice.JASMINE,
            status=Booking.BookingStatus.COMPLETED,
        )
        Booking.objects.create(
            nama='Siti Rahma',
            alamat='Jl. Melati No. 1',
            kota='Jakarta',
            no_hp=self.phone_number,
            tgl_treatment=date(2026, 3, 5),
            jam_treatment=time(9, 0),
            perawatan_pilihan='Shiatsu',
            aromatherapy_oil=Booking.AromatherapyChoice.LAVENDER,
            status=Booking.BookingStatus.COMPLETED,
        )
        Booking.objects.create(
            nama='Siti Rahma',
            alamat='Jl. Melati No. 1',
            kota='Jakarta',
            no_hp=self.phone_number,
            tgl_treatment=date(2026, 3, 4),
            jam_treatment=time(9, 0),
            perawatan_pilihan='Hot Stone',
            aromatherapy_oil=Booking.AromatherapyChoice.ROSE,
            status=Booking.BookingStatus.CANCELLED,
        )

    def test_membership_check_requires_phone_number(self):
        response = self.client.get('/api/membership/check', format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, {'error': 'phoneNumber is required'})

    def test_membership_check_returns_not_found_for_unknown_customer(self):
        response = self.client.get('/api/membership/check?phoneNumber=08999999999', format='json')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data, {'error': 'Customer tidak ditemukan'})

    def test_membership_check_returns_progress_and_latest_five_completed_bookings(self):
        response = self.client.get(f'/api/membership/check?phoneNumber={self.phone_number}', format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['namaCustomer'], 'Siti Rahma')
        self.assertEqual(response.data['phoneNumber'], self.phone_number)
        self.assertEqual(response.data['totalBookingCompleted'], 6)
        self.assertEqual(response.data['milestonesAchieved'], [4])
        self.assertEqual(response.data['nextMilestone'], 7)
        self.assertEqual(response.data['remainingToNextMilestone'], 1)
        self.assertEqual(len(response.data['bookingHistory']), 5)

        first_booking = response.data['bookingHistory'][0]
        last_booking = response.data['bookingHistory'][-1]

        self.assertEqual(first_booking['tanggal'], '2026-03-10')
        self.assertEqual(first_booking['layanan'], 'Relaxing Massage')
        self.assertEqual(first_booking['status'], Booking.BookingStatus.COMPLETED)
        self.assertEqual(last_booking['tanggal'], '2026-03-06')

    def test_membership_check_returns_zero_progress_when_customer_has_no_completed_booking(self):
        pending_phone = '08111111111'
        Booking.objects.create(
            nama='Ayu Lestari',
            alamat='Jl. Kenanga No. 2',
            kota='Bogor',
            no_hp=pending_phone,
            tgl_treatment=date(2026, 4, 1),
            jam_treatment=time(13, 0),
            perawatan_pilihan='Relaxing Massage',
            aromatherapy_oil=Booking.AromatherapyChoice.JASMINE,
            status=Booking.BookingStatus.PENDING,
        )

        response = self.client.get(f'/api/membership/check?phoneNumber={pending_phone}', format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['namaCustomer'], 'Ayu Lestari')
        self.assertEqual(response.data['totalBookingCompleted'], 0)
        self.assertEqual(response.data['milestonesAchieved'], [])
        self.assertEqual(response.data['nextMilestone'], 4)
        self.assertEqual(response.data['remainingToNextMilestone'], 4)
        self.assertEqual(response.data['bookingHistory'], [])
