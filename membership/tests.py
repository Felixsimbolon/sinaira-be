from datetime import date, time
from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from booking.models import Booking

User = get_user_model()


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


class MembershipAdminEndpointAPITest(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='password',
            name='Admin User',
            role=User.Role.ADMIN,
        )

        self.client.force_authenticate(user=self.admin)

        self._create_booking(
            nama='Siti Lama',
            no_hp='08123456789',
            perawatan_pilihan='Relaxing Massage, Facial',
            total_pembayaran=Decimal('100000'),
            status=Booking.BookingStatus.COMPLETED,
        )
        self._create_booking(
            nama='Siti Baru',
            no_hp='08123456789',
            perawatan_pilihan='Relaxing Massage',
            total_pembayaran=Decimal('200000'),
            status=Booking.BookingStatus.COMPLETED,
        )
        self._create_booking(
            nama='Ayu Lestari',
            no_hp='08999999999',
            perawatan_pilihan='Foot Reflexology',
            total_pembayaran=None,
            status=Booking.BookingStatus.COMPLETED,
        )
        self._create_booking(
            nama='Siti Baru',
            no_hp='08123456789',
            perawatan_pilihan='Hot Stone',
            total_pembayaran=Decimal('300000'),
            status=Booking.BookingStatus.CANCELLED,
        )

    def _create_booking(
        self,
        *,
        nama,
        no_hp,
        perawatan_pilihan,
        total_pembayaran,
        status,
    ):
        return Booking.objects.create(
            nama=nama,
            alamat='Jl. Melati No. 1',
            kota='Jakarta',
            no_hp=no_hp,
            tgl_treatment=date(2026, 3, 10),
            jam_treatment=time(9, 0),
            perawatan_pilihan=perawatan_pilihan,
            total_pembayaran=total_pembayaran,
            aromatherapy_oil=Booking.AromatherapyChoice.JASMINE,
            status=status,
        )

    def test_membership_admin_returns_aggregated_customer_summary(self):
        response = self.client.get('/api/membership/admin?ordering=-totalBooking', format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 2)

        first_customer = response.data['results'][0]
        second_customer = response.data['results'][1]

        self.assertEqual(first_customer['idCustomer'], '08123456789')
        self.assertEqual(first_customer['namaCustomer'], 'Siti Baru')
        self.assertEqual(first_customer['nomorTelepon'], '08123456789')
        self.assertEqual(first_customer['totalBooking'], 2)
        self.assertEqual(first_customer['totalPembayaran'], 300000)
        self.assertEqual(first_customer['layananTerbanyak'], 'Relaxing Massage')

        self.assertEqual(second_customer['idCustomer'], '08999999999')
        self.assertEqual(second_customer['totalBooking'], 1)
        self.assertEqual(second_customer['totalPembayaran'], 0)

    def test_membership_admin_supports_search_min_booking_and_ordering(self):
        response = self.client.get(
            '/api/membership/admin?search=Siti&min_booking=2&ordering=totalPembayaran',
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['nomorTelepon'], '08123456789')

    def test_membership_export_returns_csv(self):
        response = self.client.get('/api/membership/admin/export?ordering=-totalBooking')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertEqual(
            response['Content-Disposition'],
            'attachment; filename="membership.csv"',
        )

        content = response.content.decode()
        self.assertIn('Nama,Nomor Telepon,Total Booking,Total Pembayaran,Layanan Terbanyak', content)
        self.assertIn('Siti Baru,08123456789,2,300000,Relaxing Massage', content)
