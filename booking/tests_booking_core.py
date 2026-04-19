from datetime import date, time, timedelta

from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from layanan.models import Layanan, LayananKategori
from booking.models import Booking


class BookingCreateEndpointAPITest(APITestCase):
    def setUp(self):
        self.kategori = LayananKategori.objects.create(nama='Massage')
        self.swedish = Layanan.objects.create(
            kategori=self.kategori,
            nama='Swedish Massage',
            durasi_menit=60,
            harga=180000,
            is_active=True,
        )
        self.deep_tissue = Layanan.objects.create(
            kategori=self.kategori,
            nama='Deep Tissue',
            durasi_menit=60,
            harga=220000,
            is_active=True,
        )

    def _payload(self, **overrides):
        payload = {
            'nama': 'Customer Create',
            'alamat': 'Jl. Mawar No. 1',
            'kota': 'Serang',
            'kode_pos': '42111',
            'no_hp': '081234567890',
            'tgl_treatment': (date.today() + timedelta(days=1)).isoformat(),
            'jam_treatment': '10:00:00',
            'perawatan_pilihan': 'Swedish Massage',
            'aromatherapy_oil': Booking.AromatherapyChoice.JASMINE,
            'kondisi_khusus': '',
            'tahu_dari': 'Instagram',
        }
        payload.update(overrides)
        return payload

    def test_create_booking_success(self):
        response = self.client.post('/api/bookings/', self._payload(), format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('data', response.data)
        self.assertIn('booking_id', response.data['data'])

        booking = Booking.objects.get(booking_id=response.data['data']['booking_id'])
        self.assertEqual(booking.status, Booking.BookingStatus.PENDING)
        self.assertEqual(booking.nama, 'Customer Create')

    def test_create_booking_reject_past_date(self):
        response = self.client.post(
            '/api/bookings/',
            self._payload(tgl_treatment=(date.today() - timedelta(days=1)).isoformat()),
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('tgl_treatment', response.data)

    def test_create_booking_reject_more_than_one_year(self):
        response = self.client.post(
            '/api/bookings/',
            self._payload(tgl_treatment=(date.today() + timedelta(days=366)).isoformat()),
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('tgl_treatment', response.data)

    def test_create_booking_reject_total_layanan_below_minimum(self):
        Layanan.objects.create(
            kategori=self.kategori,
            nama='Express',
            durasi_menit=30,
            harga=100000,
            is_active=True,
        )

        response = self.client.post(
            '/api/bookings/',
            self._payload(perawatan_pilihan='Express'),
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('perawatan_pilihan', response.data)

    def test_create_booking_applies_loyalty_discount_as_cheapest_service(self):
        for idx in range(4):
            Booking.objects.create(
                nama=f'Customer Lama {idx}',
                alamat='Jl. Lama',
                kota='Serang',
                no_hp='6281234567890',
                tgl_treatment=date.today() + timedelta(days=1),
                jam_treatment=time(9, 0),
                perawatan_pilihan='Swedish Massage',
                aromatherapy_oil=Booking.AromatherapyChoice.JASMINE,
                status=Booking.BookingStatus.COMPLETED,
                harga=180000,
                total_pembayaran=180000,
            )

        response = self.client.post(
            '/api/bookings/',
            self._payload(
                no_hp='081234567890',
                perawatan_pilihan='Swedish Massage, Deep Tissue',
                voucher_code='LOYALTY-4',
            ),
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        booking = Booking.objects.get(booking_id=response.data['data']['booking_id'])
        self.assertEqual(float(booking.harga), 400000.00)
        self.assertEqual(float(booking.total_pembayaran), 220000.00)
        self.assertEqual(booking.voucher_code, 'LOYALTY-4')

    def test_create_booking_rejects_loyalty_when_not_eligible(self):
        for idx in range(3):
            Booking.objects.create(
                nama=f'Customer Baru {idx}',
                alamat='Jl. Baru',
                kota='Serang',
                no_hp='081234567890',
                tgl_treatment=date.today() + timedelta(days=1),
                jam_treatment=time(9, 0),
                perawatan_pilihan='Swedish Massage',
                aromatherapy_oil=Booking.AromatherapyChoice.JASMINE,
                status=Booking.BookingStatus.COMPLETED,
                harga=180000,
                total_pembayaran=180000,
            )

        response = self.client.post(
            '/api/bookings/',
            self._payload(voucher_code='LOYALTY-4'),
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('voucher_code', response.data)

    def test_create_booking_rejects_loyalty_after_passing_milestone(self):
        for idx in range(5):
            Booking.objects.create(
                nama=f'Customer Loyal {idx}',
                alamat='Jl. Loyal',
                kota='Serang',
                no_hp='081234567890',
                tgl_treatment=date.today() + timedelta(days=1),
                jam_treatment=time(9, 0),
                perawatan_pilihan='Swedish Massage',
                aromatherapy_oil=Booking.AromatherapyChoice.JASMINE,
                status=Booking.BookingStatus.COMPLETED,
                harga=180000,
                total_pembayaran=180000,
            )

        response = self.client.post(
            '/api/bookings/',
            self._payload(voucher_code='LOYALTY-4'),
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('voucher_code', response.data)


class BookingAdminListEndpointAPITest(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='booking_admin',
            email='booking_admin@example.com',
            password='password123',
            name='Booking Admin',
            role=User.Role.ADMIN,
        )
        self.therapist = User.objects.create_user(
            username='booking_therapist',
            email='booking_therapist@example.com',
            password='password123',
            name='Booking Therapist',
            role=User.Role.THERAPIST,
        )

        self.booking_a = Booking.objects.create(
            nama='Alice',
            alamat='Jl. A',
            kota='Serang',
            no_hp='081111111111',
            tgl_treatment=date.today() + timedelta(days=1),
            jam_treatment=time(9, 0),
            perawatan_pilihan='Swedish Massage',
            aromatherapy_oil=Booking.AromatherapyChoice.JASMINE,
            status=Booking.BookingStatus.PENDING,
            harga=180000,
            total_pembayaran=200000,
        )
        self.booking_b = Booking.objects.create(
            nama='Budi',
            alamat='Jl. B',
            kota='Cilegon',
            no_hp='082222222222',
            tgl_treatment=date.today() + timedelta(days=2),
            jam_treatment=time(10, 0),
            perawatan_pilihan='Deep Tissue',
            aromatherapy_oil=Booking.AromatherapyChoice.ROSE,
            status=Booking.BookingStatus.CONFIRMED,
            harga=220000,
            total_pembayaran=220000,
        )

    def test_admin_can_get_all_booking_list(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.get('/api/admin/bookings/', format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('count', response.data)
        self.assertIn('results', response.data)
        self.assertGreaterEqual(response.data['count'], 2)

        first_item = response.data['results'][0]
        self.assertIn('booking_id', first_item)
        self.assertIn('nama', first_item)
        self.assertIn('status', first_item)
        self.assertIn('harga', first_item)
        self.assertIn('total_pembayaran', first_item)

    def test_admin_can_search_booking_list(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.get('/api/admin/bookings/?search=Alice', format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['nama'], 'Alice')

    def test_therapist_forbidden_from_admin_booking_list(self):
        self.client.force_authenticate(user=self.therapist)

        response = self.client.get('/api/admin/bookings/', format='json')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class BookingAdminDetailEndpointAPITest(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='detail_admin',
            email='detail_admin@example.com',
            password='password123',
            name='Detail Admin',
            role=User.Role.ADMIN,
        )
        self.therapist = User.objects.create_user(
            username='detail_therapist',
            email='detail_therapist@example.com',
            password='password123',
            name='Detail Therapist',
            role=User.Role.THERAPIST,
        )

        self.booking = Booking.objects.create(
            nama='Detail Customer',
            alamat='Jl. Detail No. 7',
            kota='Batam',
            no_hp='083333333333',
            tgl_treatment=date.today() + timedelta(days=1),
            jam_treatment=time(11, 0),
            perawatan_pilihan='Swedish Massage',
            aromatherapy_oil=Booking.AromatherapyChoice.LAVENDER,
            status=Booking.BookingStatus.PAID,
            harga=250000,
            total_pembayaran=275000,
        )

    def test_admin_can_get_booking_detail(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.get(f'/api/admin/bookings/{self.booking.booking_id}/', format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['booking_id'], self.booking.booking_id)
        self.assertEqual(response.data['nama'], 'Detail Customer')
        self.assertEqual(str(response.data['harga']), '250000.00')
        self.assertEqual(str(response.data['total_pembayaran']), '275000.00')

    def test_admin_get_booking_detail_not_found(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.get('/api/admin/bookings/INVALID1/', format='json')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_therapist_forbidden_from_admin_booking_detail(self):
        self.client.force_authenticate(user=self.therapist)

        response = self.client.get(f'/api/admin/bookings/{self.booking.booking_id}/', format='json')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
