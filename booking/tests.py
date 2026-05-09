from django.test import TestCase
from datetime import date, time, timedelta
from unittest.mock import MagicMock, patch
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from layanan.models import Layanan, LayananKategori
from .models import Booking, BookingChangeLog
from therapist.models import Therapist, TherapistWeeklyAvailability
from .utils import (
    sanitize_whatsapp_text,
    normalize_phone,
    normalize_aromatherapy,
    extract_booking_from_whatsapp_message,
    geocode_location_from_address,
    get_distances_to_therapists_in_same_city,
)


# ──────────────────────────────────────────────────────────────────
# Helper function tests
# ──────────────────────────────────────────────────────────────────

class SanitizeWhatsAppTextTest(TestCase):
    def test_removes_bold_markers(self):
        self.assertEqual(sanitize_whatsapp_text("*Nama*"), "Nama")

    def test_removes_italic_markers(self):
        self.assertEqual(sanitize_whatsapp_text("_Alamat_"), "Alamat")

    def test_removes_strikethrough_markers(self):
        self.assertEqual(sanitize_whatsapp_text("~teks~"), "teks")

    def test_collapses_extra_spaces(self):
        self.assertEqual(sanitize_whatsapp_text("Tgl  Treatment   :"), "Tgl Treatment :")

    def test_strips_leading_trailing_whitespace(self):
        self.assertEqual(sanitize_whatsapp_text("  teks  "), "teks")


class NormalizePhoneTest(TestCase):
    def test_keeps_leading_zero(self):
        self.assertEqual(normalize_phone("08123456789"), "08123456789")

    def test_removes_spaces_and_dashes(self):
        self.assertEqual(normalize_phone("0812 3456-789"), "08123456789")

    def test_keeps_plus62_prefix(self):
        self.assertEqual(normalize_phone("+628123456789"), "+628123456789")

    def test_empty_string(self):
        self.assertEqual(normalize_phone(""), "")

    def test_removes_parentheses(self):
        self.assertEqual(normalize_phone("(0812)3456789"), "08123456789")


class NormalizeAromatherapyTest(TestCase):
    def test_jasmine(self):
        self.assertEqual(normalize_aromatherapy("Jasmine"), "JASMINE")

    def test_lavender_lowercase(self):
        self.assertEqual(normalize_aromatherapy("lavender"), "LAVENDER")

    def test_rose(self):
        self.assertEqual(normalize_aromatherapy("ROSE"), "ROSE")

    def test_sandalwood(self):
        self.assertEqual(normalize_aromatherapy("Sandalwood"), "SANDALWOOD")

    def test_partial_match_first_token(self):
        # "Jasmine/Lavender" — should return the first match found
        result = normalize_aromatherapy("Jasmine/Lavender")
        self.assertIn(result, ("JASMINE", "LAVENDER"))

    def test_invalid_returns_empty(self):
        self.assertEqual(normalize_aromatherapy("Mint"), "")

    def test_empty_string(self):
        self.assertEqual(normalize_aromatherapy(""), "")


# ──────────────────────────────────────────────────────────────────
# Full message extraction tests
# ──────────────────────────────────────────────────────────────────

_STANDARD_MESSAGE = """
Terima kasih sudah menghubungi Sènaira! 😊

Untuk reservasi bisa mengisi detil berikut :
Nama   : Budi Santoso
Alamat : Jl. Mawar No. 5, RT 03/RW 02
Kota   : Jakarta Selatan
No. Hp : 08123456789
Tgl Treatment : 15 Maret 2026
Jam Treatment : 10.00
Perawatan Pilihan : Swedish Massage
Aromatherapy Oil Pilihan : Lavender
Hamil/Pasca Lahiran/Haid/Kondisi Medis : Tidak ada
Tahu Sènaira dari : Instagram

Note:
1. Min. Reservasi 180K
2. Blm termasuk biaya transport
"""

_BOLD_ITALIC_MESSAGE = """
*Nama*   : _Siti Rahayu_
*Alamat* : Jl. Anggrek No. 10
*Kota*   : Depok
*No. Hp* : 0856-1234-5678
*Tgl Treatment* : 20 Maret 2026
*Jam Treatment* : 14.00
*Perawatan Pilihan* : Deep Tissue
*Aromatherapy Oil Pilihan* : Rose
*Hamil/Pasca Lahiran/Haid/Kondisi Medis* : Haid
*Tahu Sènaira dari* : Teman
"""

_MULTILINE_ALAMAT_MESSAGE = """
Nama   : Rina Wati
Alamat : Jl. Kenanga Blok C No. 12
         Perumahan Griya Asri
Kota   : Bekasi
No. Hp : 0878-9999-0000
Tgl Treatment : 25 Maret 2026
Jam Treatment : 09.00
Perawatan Pilihan : Reflexology
Aromatherapy Oil Pilihan : Jasmine
Hamil/Pasca Lahiran/Haid/Kondisi Medis : Pasca lahiran 3 bulan
Tahu Sènaira dari : Google

Note:
1. Min. Reservasi 180K
"""

_MISSING_FIELDS_MESSAGE = """
Nama   : Andi Wijaya
No. Hp : 085678901234
Tgl Treatment : 10 April 2026
Perawatan Pilihan : Hot Stone
"""


class ExtractBookingFromWhatsAppMessageTest(TestCase):

    def test_standard_message(self):
        result = extract_booking_from_whatsapp_message(_STANDARD_MESSAGE)
        self.assertEqual(result["nama"], "Budi Santoso")
        self.assertEqual(result["kota"], "Jakarta Selatan")
        self.assertEqual(result["no_hp"], "08123456789")
        self.assertEqual(result["tgl_treatment"], "15 Maret 2026")
        self.assertEqual(result["jam_treatment"], "10.00")
        self.assertEqual(result["perawatan_pilihan"], "Swedish Massage")
        self.assertEqual(result["aromatherapy_oil"], "LAVENDER")
        self.assertEqual(result["kondisi_khusus"], "Tidak ada")
        self.assertEqual(result["tahu_dari"], "Instagram")
        # Alamat should contain the street
        self.assertIn("Jl. Mawar", result["alamat"])

    def test_bold_italic_formatting_stripped(self):
        result = extract_booking_from_whatsapp_message(_BOLD_ITALIC_MESSAGE)
        self.assertEqual(result["nama"], "Siti Rahayu")
        self.assertEqual(result["kota"], "Depok")
        self.assertEqual(result["aromatherapy_oil"], "ROSE")
        self.assertEqual(result["kondisi_khusus"], "Haid")
        self.assertEqual(result["tahu_dari"], "Teman")

    def test_note_section_not_parsed(self):
        result = extract_booking_from_whatsapp_message(_STANDARD_MESSAGE)
        # None of the Note lines should bleed into fields
        for value in result.values():
            self.assertNotIn("Min. Reservasi", value)
            self.assertNotIn("transport", value)

    def test_multiline_alamat(self):
        result = extract_booking_from_whatsapp_message(_MULTILINE_ALAMAT_MESSAGE)
        self.assertIn("Jl. Kenanga", result["alamat"])
        self.assertIn("Perumahan Griya Asri", result["alamat"])

    def test_missing_fields_return_empty_string(self):
        result = extract_booking_from_whatsapp_message(_MISSING_FIELDS_MESSAGE)
        self.assertEqual(result["nama"], "Andi Wijaya")
        self.assertEqual(result["alamat"], "")
        self.assertEqual(result["kota"], "")
        self.assertEqual(result["aromatherapy_oil"], "")
        self.assertEqual(result["kondisi_khusus"], "")
        self.assertEqual(result["tahu_dari"], "")

    def test_empty_message_returns_all_empty(self):
        result = extract_booking_from_whatsapp_message("")
        for value in result.values():
            self.assertEqual(value, "")

    def test_phone_normalised(self):
        result = extract_booking_from_whatsapp_message(_BOLD_ITALIC_MESSAGE)
        self.assertEqual(result["no_hp"], "085612345678")


class BookingStatusFlowAPITest(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='admin_user',
            email='admin@example.com',
            password='password123',
            name='Admin User',
            role=User.Role.ADMIN,
        )
        self.therapist = User.objects.create_user(
            username='therapist_user',
            email='therapist@example.com',
            password='password123',
            name='Therapist User',
            role=User.Role.THERAPIST,
        )
        self.other_therapist = User.objects.create_user(
            username='other_therapist',
            email='other_therapist@example.com',
            password='password123',
            name='Other Therapist',
            role=User.Role.THERAPIST,
        )

    def _create_booking(self, status_value=Booking.BookingStatus.PENDING, therapist=None):
        return Booking.objects.create(
            nama='Budi Santoso',
            alamat='Jl. Mawar No. 5',
            kota='Jakarta',
            no_hp='081234567890',
            tgl_treatment=date.today() + timedelta(days=1),
            jam_treatment=time(10, 0),
            perawatan_pilihan='Swedish Massage',
            aromatherapy_oil=Booking.AromatherapyChoice.LAVENDER,
            kondisi_khusus='',
            tahu_dari='Instagram',
            status=status_value,
            therapist=therapist,
        )

    @staticmethod
    def _ensure_therapist_profile(user, city='Jakarta'):
        return Therapist.objects.get_or_create(
            username=user.username,
            defaults={
                'name': user.name,
                'email': user.email,
                'alamat': 'Jl. Profile Therapist',
                'kota': city,
            },
        )

    def _full_update_payload(self):
        return {
            'nama': 'Budi Santoso Updated',
            'alamat': 'Jl. Melati No. 10',
            'kota': 'Depok',
            'no_hp': '081234567891',
            'tgl_treatment': (date.today() + timedelta(days=2)).isoformat(),
            'jam_treatment': '11:00:00',
            'perawatan_pilihan': 'Deep Tissue',
            'aromatherapy_oil': Booking.AromatherapyChoice.ROSE,
            'kondisi_khusus': 'None',
            'tahu_dari': 'Google',
            'notes': 'Updated notes',
            'voucher_code': 'PROMO10',
        }

    def test_admin_bisa_full_update_booking_saat_pending(self):
        booking = self._create_booking(status_value=Booking.BookingStatus.PENDING)
        self.client.force_authenticate(user=self.admin)

        response = self.client.put(
            f'/api/admin/bookings/{booking.booking_id}/',
            self._full_update_payload(),
            format='json',
        )

        booking.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(booking.nama, 'Budi Santoso Updated')
        self.assertEqual(booking.kota, 'Depok')

    def test_booking_confirmed_tidak_bisa_full_update(self):
        booking = self._create_booking(status_value=Booking.BookingStatus.CONFIRMED)
        self.client.force_authenticate(user=self.admin)

        response = self.client.put(
            f'/api/admin/bookings/{booking.booking_id}/',
            self._full_update_payload(),
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_booking_assigned_tidak_bisa_full_update(self):
        booking = self._create_booking(status_value=Booking.BookingStatus.ASSIGNED, therapist=self.therapist)
        self.client.force_authenticate(user=self.admin)

        response = self.client.put(
            f'/api/admin/bookings/{booking.booking_id}/',
            self._full_update_payload(),
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_booking_checked_in_tidak_bisa_full_update(self):
        booking = self._create_booking(status_value=Booking.BookingStatus.CHECKED_IN, therapist=self.therapist)
        self.client.force_authenticate(user=self.admin)

        response = self.client.put(
            f'/api/admin/bookings/{booking.booking_id}/',
            self._full_update_payload(),
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_therapist_tidak_bisa_full_update_booking(self):
        booking = self._create_booking(status_value=Booking.BookingStatus.PENDING)
        self.client.force_authenticate(user=self.therapist)

        response = self.client.put(
            f'/api/admin/bookings/{booking.booking_id}/',
            self._full_update_payload(),
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_user_tanpa_hak_akses_tidak_bisa_full_update_booking(self):
        booking = self._create_booking(status_value=Booking.BookingStatus.PENDING)

        response = self.client.put(
            f'/api/admin/bookings/{booking.booking_id}/',
            self._full_update_payload(),
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_booking_baru_default_status_pending(self):
        booking = self._create_booking()
        self.assertEqual(booking.status, Booking.BookingStatus.PENDING)

    def test_admin_bisa_ubah_pending_ke_confirmed(self):
        booking = self._create_booking()
        self.client.force_authenticate(user=self.admin)

        response = self.client.patch(
            f'/api/admin/bookings/{booking.booking_id}/status/',
            {'status': Booking.BookingStatus.CONFIRMED},
            format='json',
        )

        booking.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(booking.status, Booking.BookingStatus.CONFIRMED)

    def test_admin_tidak_bisa_cancel_tanpa_alasan(self):
        booking = self._create_booking(status_value=Booking.BookingStatus.PENDING)
        self.client.force_authenticate(user=self.admin)

        response = self.client.patch(
            f'/api/admin/bookings/{booking.booking_id}/status/',
            {'status': Booking.BookingStatus.CANCELLED},
            format='json',
        )

        booking.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('cancellation_reason', response.data)
        self.assertEqual(booking.status, Booking.BookingStatus.PENDING)

    def test_admin_bisa_cancel_dengan_alasan_dan_tersimpan(self):
        booking = self._create_booking(status_value=Booking.BookingStatus.PENDING)
        self.client.force_authenticate(user=self.admin)

        response = self.client.patch(
            f'/api/admin/bookings/{booking.booking_id}/status/',
            {
                'status': Booking.BookingStatus.CANCELLED,
                'cancellation_reason': 'Customer meminta pembatalan karena bentrok jadwal.',
            },
            format='json',
        )

        booking.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(booking.status, Booking.BookingStatus.CANCELLED)
        self.assertEqual(
            booking.cancellation_reason,
            'Customer meminta pembatalan karena bentrok jadwal.',
        )

    def test_booking_detail_menampilkan_cancellation_reason(self):
        booking = self._create_booking(status_value=Booking.BookingStatus.PENDING)
        self.client.force_authenticate(user=self.admin)

        cancel_response = self.client.patch(
            f'/api/admin/bookings/{booking.booking_id}/status/',
            {
                'status': Booking.BookingStatus.CANCELLED,
                'cancellation_reason': 'Customer tidak bisa hadir.',
            },
            format='json',
        )
        detail_response = self.client.get(
            f'/api/admin/bookings/{booking.booking_id}/',
            format='json',
        )

        self.assertEqual(cancel_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.data['cancellation_reason'], 'Customer tidak bisa hadir.')

    def test_admin_tidak_bisa_ubah_pending_ke_checked_in(self):
        booking = self._create_booking()
        self.client.force_authenticate(user=self.admin)

        response = self.client.patch(
            f'/api/admin/bookings/{booking.booking_id}/status/',
            {'status': Booking.BookingStatus.CHECKED_IN},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_admin_bisa_assign_therapist_saat_confirmed(self):
        booking = self._create_booking(status_value=Booking.BookingStatus.PAID)
        self._ensure_therapist_profile(self.therapist)
        self.client.force_authenticate(user=self.admin)

        response = self.client.patch(
            f'/api/admin/bookings/{booking.booking_id}/assign-therapist/',
            {'therapist_id': self.therapist.id},
            format='json',
        )

        booking.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(booking.therapist_id, self.therapist.id)

    def test_assign_therapist_mengubah_status_menjadi_assigned(self):
        booking = self._create_booking(status_value=Booking.BookingStatus.PAID)
        self._ensure_therapist_profile(self.therapist)
        self.client.force_authenticate(user=self.admin)

        response = self.client.patch(
            f'/api/admin/bookings/{booking.booking_id}/assign-therapist/',
            {'therapist_id': self.therapist.id},
            format='json',
        )

        booking.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(booking.status, Booking.BookingStatus.ASSIGNED)

    def test_admin_bisa_reassign_therapist_saat_status_assigned(self):
        booking = self._create_booking(
            status_value=Booking.BookingStatus.ASSIGNED,
            therapist=self.therapist,
        )
        self._ensure_therapist_profile(self.therapist)
        self._ensure_therapist_profile(self.other_therapist)
        self.client.force_authenticate(user=self.admin)

        response = self.client.patch(
            f'/api/admin/bookings/{booking.booking_id}/assign-therapist/',
            {'therapist_id': self.other_therapist.id},
            format='json',
        )

        booking.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(booking.therapist_id, self.other_therapist.id)

    def test_reassign_therapist_status_tetap_assigned(self):
        booking = self._create_booking(
            status_value=Booking.BookingStatus.ASSIGNED,
            therapist=self.therapist,
        )
        self._ensure_therapist_profile(self.therapist)
        self._ensure_therapist_profile(self.other_therapist)
        self.client.force_authenticate(user=self.admin)

        response = self.client.patch(
            f'/api/admin/bookings/{booking.booking_id}/assign-therapist/',
            {'therapist_id': self.other_therapist.id},
            format='json',
        )

        booking.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(booking.status, Booking.BookingStatus.ASSIGNED)

    def test_therapist_non_assigned_tidak_bisa_checked_in_booking_orang_lain(self):
        booking = self._create_booking(
            status_value=Booking.BookingStatus.ASSIGNED,
            therapist=self.therapist,
        )
        self.client.force_authenticate(user=self.other_therapist)

        response = self.client.patch(
            f'/api/therapist/bookings/{booking.booking_id}/status/',
            {'status': Booking.BookingStatus.CHECKED_IN},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_therapist_assigned_bisa_checked_in(self):
        booking = self._create_booking(
            status_value=Booking.BookingStatus.ASSIGNED,
            therapist=self.therapist,
        )
        self.client.force_authenticate(user=self.therapist)

        response = self.client.patch(
            f'/api/therapist/bookings/{booking.booking_id}/status/',
            {'status': Booking.BookingStatus.CHECKED_IN},
            format='json',
        )

        booking.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(booking.status, Booking.BookingStatus.CHECKED_IN)

    def test_therapist_assigned_bisa_checked_out_setelah_checked_in(self):
        booking = self._create_booking(
            status_value=Booking.BookingStatus.CHECKED_IN,
            therapist=self.therapist,
        )
        self.client.force_authenticate(user=self.therapist)

        response = self.client.patch(
            f'/api/therapist/bookings/{booking.booking_id}/status/',
            {'status': Booking.BookingStatus.CHECKED_OUT},
            format='json',
        )

        booking.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(booking.status, Booking.BookingStatus.CHECKED_OUT)

    def test_admin_bisa_checked_in_booking_yang_sudah_assigned(self):
        booking = self._create_booking(
            status_value=Booking.BookingStatus.ASSIGNED,
            therapist=self.therapist,
        )
        self.client.force_authenticate(user=self.admin)

        response = self.client.patch(
            f'/api/admin/bookings/{booking.booking_id}/status/',
            {'status': Booking.BookingStatus.CHECKED_IN},
            format='json',
        )

        booking.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(booking.status, Booking.BookingStatus.CHECKED_IN)

    def test_admin_bisa_checked_out_booking_yang_status_checked_in(self):
        booking = self._create_booking(
            status_value=Booking.BookingStatus.CHECKED_IN,
            therapist=self.therapist,
        )
        self.client.force_authenticate(user=self.admin)

        response = self.client.patch(
            f'/api/admin/bookings/{booking.booking_id}/status/',
            {'status': Booking.BookingStatus.CHECKED_OUT},
            format='json',
        )

        booking.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(booking.status, Booking.BookingStatus.CHECKED_OUT)

    def test_user_tanpa_hak_akses_tidak_bisa_checked_in_dan_checked_out_via_admin_endpoint(self):
        assigned_booking = self._create_booking(
            status_value=Booking.BookingStatus.ASSIGNED,
            therapist=self.therapist,
        )
        checked_in_booking = self._create_booking(
            status_value=Booking.BookingStatus.CHECKED_IN,
            therapist=self.therapist,
        )
        self.client.force_authenticate(user=self.therapist)

        checked_in_response = self.client.patch(
            f'/api/admin/bookings/{assigned_booking.booking_id}/status/',
            {'status': Booking.BookingStatus.CHECKED_IN},
            format='json',
        )
        checked_out_response = self.client.patch(
            f'/api/admin/bookings/{checked_in_booking.booking_id}/status/',
            {'status': Booking.BookingStatus.CHECKED_OUT},
            format='json',
        )

        self.assertEqual(checked_in_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(checked_out_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_booking_cancelled_tidak_bisa_checked_in_atau_checked_out_walau_oleh_admin(self):
        cancelled_booking = self._create_booking(status_value=Booking.BookingStatus.CANCELLED)
        self.client.force_authenticate(user=self.admin)

        checked_in_response = self.client.patch(
            f'/api/admin/bookings/{cancelled_booking.booking_id}/status/',
            {'status': Booking.BookingStatus.CHECKED_IN},
            format='json',
        )
        checked_out_response = self.client.patch(
            f'/api/admin/bookings/{cancelled_booking.booking_id}/status/',
            {'status': Booking.BookingStatus.CHECKED_OUT},
            format='json',
        )

        self.assertEqual(checked_in_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(checked_out_response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_booking_completed_tidak_bisa_checked_in_atau_checked_out_walau_oleh_admin(self):
        completed_booking = self._create_booking(status_value=Booking.BookingStatus.COMPLETED)
        self.client.force_authenticate(user=self.admin)

        checked_in_response = self.client.patch(
            f'/api/admin/bookings/{completed_booking.booking_id}/status/',
            {'status': Booking.BookingStatus.CHECKED_IN},
            format='json',
        )
        checked_out_response = self.client.patch(
            f'/api/admin/bookings/{completed_booking.booking_id}/status/',
            {'status': Booking.BookingStatus.CHECKED_OUT},
            format='json',
        )

        self.assertEqual(checked_in_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(checked_out_response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_booking_tidak_bisa_completed_sebelum_checked_out(self):
        booking = self._create_booking(
            status_value=Booking.BookingStatus.CHECKED_IN,
            therapist=self.therapist,
        )
        self.client.force_authenticate(user=self.admin)

        response = self.client.patch(
            f'/api/admin/bookings/{booking.booking_id}/status/',
            {'status': Booking.BookingStatus.COMPLETED},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_booking_tidak_bisa_diassign_jika_status_cancelled(self):
        booking = self._create_booking(status_value=Booking.BookingStatus.CANCELLED)
        self.client.force_authenticate(user=self.admin)

        response = self.client.patch(
            f'/api/admin/bookings/{booking.booking_id}/assign-therapist/',
            {'therapist_id': self.therapist.id},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reassign_gagal_jika_status_bukan_assigned(self):
        booking = self._create_booking(status_value=Booking.BookingStatus.CHECKED_IN, therapist=self.therapist)
        self.client.force_authenticate(user=self.admin)

        response = self.client.patch(
            f'/api/admin/bookings/{booking.booking_id}/assign-therapist/',
            {'therapist_id': self.other_therapist.id},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_assign_gagal_jika_status_bukan_confirmed(self):
        booking = self._create_booking(status_value=Booking.BookingStatus.PENDING)
        self.client.force_authenticate(user=self.admin)

        response = self.client.patch(
            f'/api/admin/bookings/{booking.booking_id}/assign-therapist/',
            {'therapist_id': self.therapist.id},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_admin_harus_isi_total_pembayaran_dan_harga_saat_confirmed_ke_paid(self):
        booking = self._create_booking(status_value=Booking.BookingStatus.CONFIRMED)
        self.client.force_authenticate(user=self.admin)

        response = self.client.patch(
            f'/api/admin/bookings/{booking.booking_id}/status/',
            {'status': Booking.BookingStatus.PAID},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('total_pembayaran', response.data)

    def test_admin_bisa_ubah_confirmed_ke_paid_jika_nominal_diisi(self):
        booking = self._create_booking(status_value=Booking.BookingStatus.CONFIRMED)
        self.client.force_authenticate(user=self.admin)

        response = self.client.patch(
            f'/api/admin/bookings/{booking.booking_id}/status/',
            {
                'status': Booking.BookingStatus.PAID,
                'harga': '250000.00',
                'total_pembayaran': '275000.00',
            },
            format='json',
        )

        booking.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(booking.status, Booking.BookingStatus.PAID)
        self.assertEqual(str(booking.harga), '250000.00')
        self.assertEqual(str(booking.total_pembayaran), '275000.00')

    def test_admin_tidak_bisa_assign_therapist_saat_status_confirmed(self):
        booking = self._create_booking(status_value=Booking.BookingStatus.CONFIRMED)
        self.client.force_authenticate(user=self.admin)

        response = self.client.patch(
            f'/api/admin/bookings/{booking.booking_id}/assign-therapist/',
            {'therapist_id': self.therapist.id},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_booking_completed_tidak_bisa_assign_atau_reassign_therapist(self):
        booking = self._create_booking(status_value=Booking.BookingStatus.COMPLETED, therapist=self.therapist)
        self.client.force_authenticate(user=self.admin)

        response = self.client.patch(
            f'/api/admin/bookings/{booking.booking_id}/assign-therapist/',
            {'therapist_id': self.other_therapist.id},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_booking_tidak_bisa_diubah_jika_status_completed(self):
        booking = self._create_booking(status_value=Booking.BookingStatus.COMPLETED)
        self.client.force_authenticate(user=self.admin)

        response = self.client.patch(
            f'/api/admin/bookings/{booking.booking_id}/status/',
            {'status': Booking.BookingStatus.CANCELLED},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_hanya_role_therapist_yang_bisa_dipilih_saat_assign_therapist(self):
        booking = self._create_booking(status_value=Booking.BookingStatus.CONFIRMED)
        self.client.force_authenticate(user=self.admin)

        response = self.client.patch(
            f'/api/admin/bookings/{booking.booking_id}/assign-therapist/',
            {'therapist_id': self.admin.id},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_assign_ditolak_jika_therapist_tidak_available_di_timetable(self):
        booking = self._create_booking(status_value=Booking.BookingStatus.PAID)
        Therapist.objects.create(
            username=self.therapist.username,
            name='Therapist Profile For Timetable',
            email='therapist_profile_timetable@example.com',
            alamat='Jl. Timetable',
            kota='Jakarta',
        )
        # Booking jam 10:00, slot only covers afternoon.
        TherapistWeeklyAvailability.objects.create(
            therapist=Therapist.objects.get(username=self.therapist.username),
            day_of_week=booking.tgl_treatment.weekday(),
            start_time='14:00:00',
            end_time='20:00:00',
            is_active=True,
        )

        self.client.force_authenticate(user=self.admin)
        response = self.client.patch(
            f'/api/admin/bookings/{booking.booking_id}/assign-therapist/',
            {'therapist_id': self.therapist.id},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_assign_ditolak_jika_therapist_tidak_punya_profile(self):
        booking = self._create_booking(status_value=Booking.BookingStatus.PAID)
        self.client.force_authenticate(user=self.admin)

        response = self.client.patch(
            f'/api/admin/bookings/{booking.booking_id}/assign-therapist/',
            {'therapist_id': self.therapist.id},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class BookingCreateAndAdminListFlowAPITest(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='admin_list_user',
            email='admin_list@example.com',
            password='password123',
            name='Admin List User',
            role=User.Role.ADMIN,
        )
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

    def test_booking_create_public_tersimpan_dan_muncul_di_admin_list(self):
        create_payload = {
            'nama': 'Customer Booking List',
            'alamat': 'Jl. Melati No. 3',
            'kota': 'Serang',
            'kode_pos': '42111',
            'no_hp': '081234567890',
            'tgl_treatment': (date.today() + timedelta(days=1)).isoformat(),
            'jam_treatment': '14:30:00',
            'perawatan_pilihan': 'Swedish Massage',
            'aromatherapy_oil': Booking.AromatherapyChoice.JASMINE,
            'kondisi_khusus': '',
            'tahu_dari': 'Instagram',
        }

        create_response = self.client.post('/api/bookings/', create_payload, format='json')
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)

        booking_id = create_response.data['data']['booking_id']
        self.assertTrue(Booking.objects.filter(booking_id=booking_id).exists())

        self.client.force_authenticate(user=self.admin)
        list_response = self.client.get('/api/admin/bookings/', format='json')
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)

        returned_ids = [item['booking_id'] for item in list_response.data.get('results', [])]
        self.assertIn(booking_id, returned_ids)

    def test_booking_create_auto_set_harga_dari_layanan(self):
        create_payload = {
            'nama': 'Customer Auto Harga',
            'alamat': 'Jl. Anggrek No. 4',
            'kota': 'Serang',
            'kode_pos': '42111',
            'no_hp': '081234567891',
            'tgl_treatment': (date.today() + timedelta(days=1)).isoformat(),
            'jam_treatment': '15:00:00',
            'perawatan_pilihan': 'Swedish Massage, Deep Tissue',
            'aromatherapy_oil': Booking.AromatherapyChoice.JASMINE,
            'kondisi_khusus': '',
            'tahu_dari': 'Instagram',
        }

        create_response = self.client.post('/api/bookings/', create_payload, format='json')
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)

        booking_id = create_response.data['data']['booking_id']
        created_booking = Booking.objects.get(booking_id=booking_id)
        self.assertEqual(float(created_booking.harga), float(self.swedish.harga + self.deep_tissue.harga))

        self.client.force_authenticate(user=self.admin)

        detail_response = self.client.get(f'/api/admin/bookings/{booking_id}/', format='json')
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(float(detail_response.data['harga']), float(self.swedish.harga + self.deep_tissue.harga))

        list_response = self.client.get('/api/admin/bookings/', format='json')
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        booking_item = next(
            item for item in list_response.data.get('results', []) if item['booking_id'] == booking_id
        )
        self.assertEqual(float(booking_item['harga']), float(self.swedish.harga + self.deep_tissue.harga))


class BookingGeolocationTest(TestCase):
    def test_create_booking_tanpa_field_geolokasi_tetap_valid(self):
        booking = Booking.objects.create(
            nama='Geo Customer',
            alamat='Jl. Geo No. 1',
            kota='Jakarta',
            no_hp='081234567890',
            tgl_treatment=date.today() + timedelta(days=1),
            jam_treatment=time(9, 0),
            perawatan_pilihan='Swedish Massage',
            aromatherapy_oil=Booking.AromatherapyChoice.JASMINE,
        )

        self.assertIsNone(booking.latitude)
        self.assertIsNone(booking.longitude)
        self.assertIsNone(booking.kelurahan)
        self.assertIsNone(booking.kecamatan)

    @patch('booking.utils.Nominatim')
    def test_geocoding_sukses_dari_alamat_lengkap(self, mock_nominatim):
        geolocator = mock_nominatim.return_value
        geolocator.geocode.return_value = MagicMock(latitude=-6.2, longitude=106.8)

        lat, lon = geocode_location_from_address(
            alamat='Jl. Mawar No. 5',
            kelurahan='Cilandak Barat',
            kecamatan='Cilandak',
            kota='Jakarta Selatan',
        )

        self.assertEqual(lat, -6.2)
        self.assertEqual(lon, 106.8)
        geolocator.geocode.assert_called_once()

    @patch('booking.utils.Nominatim')
    def test_geocoding_fallback_ke_kelurahan_saat_alamat_lengkap_gagal(self, mock_nominatim):
        geolocator = mock_nominatim.return_value
        geolocator.geocode.side_effect = [None, MagicMock(latitude=-6.3, longitude=106.7)]

        lat, lon = geocode_location_from_address(
            alamat='Alamat Tidak Ditemukan',
            kelurahan='Pondok Labu',
            kecamatan='Cilandak',
            kota='Jakarta Selatan',
        )

        self.assertEqual(lat, -6.3)
        self.assertEqual(lon, 106.7)
        self.assertEqual(geolocator.geocode.call_count, 2)

    def test_hitung_jarak_booking_ke_therapist_kota_yang_sama(self):
        booking = Booking.objects.create(
            nama='Distance Customer',
            alamat='Jl. Distance No. 2',
            kota='Jakarta Selatan',
            no_hp='081234567891',
            tgl_treatment=date.today() + timedelta(days=1),
            jam_treatment=time(11, 0),
            perawatan_pilihan='Deep Tissue',
            aromatherapy_oil=Booking.AromatherapyChoice.ROSE,
            latitude=-6.30,
            longitude=106.80,
        )

        near_therapist = Therapist.objects.create(
            username='near_therapist',
            name='Near Therapist',
            email='near@example.com',
            kota='Jakarta Selatan',
            latitude=-6.31,
            longitude=106.81,
        )
        far_therapist = Therapist.objects.create(
            username='far_therapist',
            name='Far Therapist',
            email='far@example.com',
            kota='Jakarta Selatan',
            latitude=-6.40,
            longitude=106.90,
        )
        Therapist.objects.create(
            username='other_city_therapist',
            name='Other City Therapist',
            email='othercity@example.com',
            kota='Bandung',
            latitude=-6.91,
            longitude=107.61,
        )

        results = get_distances_to_therapists_in_same_city(booking)

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]['id'], near_therapist.id)
        self.assertEqual(results[1]['id'], far_therapist.id)

    def test_hitung_jarak_skip_therapist_tanpa_lat_lng(self):
        booking = Booking.objects.create(
            nama='Skip Customer',
            alamat='Jl. Skip No. 3',
            kota='Jakarta Selatan',
            no_hp='081234567892',
            tgl_treatment=date.today() + timedelta(days=1),
            jam_treatment=time(12, 0),
            perawatan_pilihan='Reflexology',
            aromatherapy_oil=Booking.AromatherapyChoice.LAVENDER,
            latitude=-6.30,
            longitude=106.80,
        )

        Therapist.objects.create(
            username='missing_coord_therapist',
            name='Missing Coord Therapist',
            email='missing@example.com',
            kota='Jakarta Selatan',
            latitude=None,
            longitude=None,
        )

        results = get_distances_to_therapists_in_same_city(booking)
        self.assertEqual(results, [])

    def test_hitung_jarak_return_error_jika_booking_tanpa_lat_lng(self):
        booking = Booking.objects.create(
            nama='NoCoord Customer',
            alamat='Jl. NoCoord No. 4',
            kota='Jakarta Selatan',
            no_hp='081234567893',
            tgl_treatment=date.today() + timedelta(days=1),
            jam_treatment=time(13, 0),
            perawatan_pilihan='Swedish Massage',
            aromatherapy_oil=Booking.AromatherapyChoice.SANDALWOOD,
        )

        with self.assertRaises(ValueError):
            get_distances_to_therapists_in_same_city(booking)


class BookingAutoGeocodeAPITest(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='booking_geo_admin',
            email='booking_geo_admin@example.com',
            password='password123',
            name='Booking Geo Admin',
            role=User.Role.ADMIN,
        )
        self.therapist_user = User.objects.create_user(
            username='booking_geo_therapist',
            email='booking_geo_therapist@example.com',
            password='password123',
            name='Booking Geo Therapist',
            role=User.Role.THERAPIST,
        )

        kategori = LayananKategori.objects.create(nama='Body Treatment')
        Layanan.objects.create(
            kategori=kategori,
            nama='Swedish Massage',
            durasi_menit=60,
            harga=180000,
            is_active=True,
        )
        Layanan.objects.create(
            kategori=kategori,
            nama='Deep Tissue',
            durasi_menit=60,
            harga=220000,
            is_active=True,
        )
        Layanan.objects.create(
            kategori=kategori,
            nama='Reflexology',
            durasi_menit=60,
            harga=190000,
            is_active=True,
        )

        self.booking = Booking.objects.create(
            nama='Auto Geo Customer',
            alamat='Jl. Auto Geo No. 1',
            kelurahan='Kelurahan Lama',
            kecamatan='Kecamatan Lama',
            kota='Jakarta Selatan',
            no_hp='081234567811',
            tgl_treatment=date.today() + timedelta(days=1),
            jam_treatment=time(10, 0),
            perawatan_pilihan='Swedish Massage',
            aromatherapy_oil=Booking.AromatherapyChoice.LAVENDER,
            latitude=-6.20,
            longitude=106.80,
            status=Booking.BookingStatus.PENDING,
        )

    @patch('booking.serializers.geocode_location_from_address')
    def test_create_booking_auto_geocode_sukses(self, mock_geocode):
        mock_geocode.return_value = (-6.25, 106.82)

        response = self.client.post(
            '/api/bookings/',
            {
                'nama': 'Create Auto Geocode',
                'alamat': 'Jl. Baru No. 1',
                'kelurahan': 'Kelurahan Baru',
                'kecamatan': 'Kecamatan Baru',
                'kota': 'Jakarta Selatan',
                'no_hp': '081234567812',
                'tgl_treatment': (date.today() + timedelta(days=1)).isoformat(),
                'jam_treatment': '09:30:00',
                'perawatan_pilihan': 'Deep Tissue',
                'aromatherapy_oil': Booking.AromatherapyChoice.ROSE,
                'latitude': -1.0,
                'longitude': 100.0,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created = Booking.objects.get(booking_id=response.data['data']['booking_id'])
        self.assertEqual(created.latitude, -6.25)
        self.assertEqual(created.longitude, 106.82)

    @patch('booking.serializers.geocode_location_from_address')
    def test_create_booking_auto_geocode_gagal_tetap_sukses(self, mock_geocode):
        mock_geocode.return_value = (None, None)

        response = self.client.post(
            '/api/bookings/',
            {
                'nama': 'Create Auto Geocode Fail',
                'alamat': 'Alamat Tidak Dikenal',
                'kelurahan': 'Kelurahan Tidak Dikenal',
                'kecamatan': 'Kecamatan Tidak Dikenal',
                'kota': 'Jakarta Selatan',
                'no_hp': '081234567813',
                'tgl_treatment': (date.today() + timedelta(days=1)).isoformat(),
                'jam_treatment': '10:30:00',
                'perawatan_pilihan': 'Reflexology',
                'aromatherapy_oil': Booking.AromatherapyChoice.JASMINE,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created = Booking.objects.get(booking_id=response.data['data']['booking_id'])
        self.assertIsNone(created.latitude)
        self.assertIsNone(created.longitude)

    def test_latitude_longitude_tidak_wajib_saat_create(self):
        response = self.client.post(
            '/api/bookings/',
            {
                'nama': 'Create Without LatLng',
                'alamat': 'Jl. Tanpa LatLng',
                'kota': 'Jakarta Selatan',
                'no_hp': '081234567814',
                'tgl_treatment': (date.today() + timedelta(days=1)).isoformat(),
                'jam_treatment': '11:00:00',
                'perawatan_pilihan': 'Deep Tissue',
                'aromatherapy_oil': Booking.AromatherapyChoice.ROSE,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    @patch('booking.serializers.geocode_location_from_address')
    def test_update_alamat_booking_auto_geocode_ulang(self, mock_geocode):
        mock_geocode.return_value = (-6.31, 106.77)
        self.client.force_authenticate(user=self.admin)

        response = self.client.patch(
            f'/api/admin/bookings/{self.booking.booking_id}/',
            {
                'alamat': 'Jl. Updated No. 2',
                'kelurahan': 'Kelurahan Updated',
                'kecamatan': 'Kecamatan Updated',
                'kota': 'Depok',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.latitude, -6.31)
        self.assertEqual(self.booking.longitude, 106.77)

    @patch('booking.serializers.geocode_location_from_address')
    def test_update_alamat_booking_auto_geocode_gagal_graceful(self, mock_geocode):
        mock_geocode.return_value = (None, None)
        self.client.force_authenticate(user=self.admin)

        response = self.client.patch(
            f'/api/admin/bookings/{self.booking.booking_id}/',
            {
                'alamat': 'Alamat Tidak Dikenal',
                'kota': 'Depok',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.booking.refresh_from_db()
        self.assertIsNone(self.booking.latitude)
        self.assertIsNone(self.booking.longitude)

    def test_latitude_longitude_bisa_diedit_saat_update(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.patch(
            f'/api/admin/bookings/{self.booking.booking_id}/',
            {
                'latitude': -6.45,
                'longitude': 107.01,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.latitude, -6.45)
        self.assertEqual(self.booking.longitude, 107.01)

    @patch('booking.views.geocode_location_from_address')
    def test_manual_geocode_trigger_booking_detail_success(self, mock_geocode):
        mock_geocode.return_value = (-6.21, 106.79)
        self.client.force_authenticate(user=self.admin)

        response = self.client.post(
            f'/api/admin/bookings/{self.booking.booking_id}/geocode/',
            {},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.latitude, -6.21)
        self.assertEqual(self.booking.longitude, 106.79)

    @patch('booking.views.geocode_location_from_address')
    def test_manual_geocode_trigger_booking_detail_gagal_graceful(self, mock_geocode):
        mock_geocode.return_value = (None, None)
        self.client.force_authenticate(user=self.admin)

        response = self.client.post(
            f'/api/admin/bookings/{self.booking.booking_id}/geocode/',
            {},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_manual_geocode_trigger_booking_detail_forbidden_non_admin(self):
        self.client.force_authenticate(user=self.therapist_user)

        response = self.client.post(
            f'/api/admin/bookings/{self.booking.booking_id}/geocode/',
            {},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class BookingGeolocationEndpointAPITest(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='geo_admin',
            email='geo_admin@example.com',
            password='password123',
            name='Geo Admin',
            role=User.Role.ADMIN,
        )
        self.non_admin = User.objects.create_user(
            username='geo_therapist_actor',
            email='geo_therapist_actor@example.com',
            password='password123',
            name='Geo Therapist Actor',
            role=User.Role.THERAPIST,
        )

        self.near_user = User.objects.create_user(
            username='distance_near_user',
            email='distance_near_user@example.com',
            password='password123',
            name='Distance Near User',
            role=User.Role.THERAPIST,
        )
        self.far_user = User.objects.create_user(
            username='distance_far_user',
            email='distance_far_user@example.com',
            password='password123',
            name='Distance Far User',
            role=User.Role.THERAPIST,
        )
        self.no_coord_user = User.objects.create_user(
            username='distance_nocoord_user',
            email='distance_nocoord_user@example.com',
            password='password123',
            name='Distance NoCoord User',
            role=User.Role.THERAPIST,
        )
        self.other_city_user = User.objects.create_user(
            username='distance_other_city_user',
            email='distance_other_city_user@example.com',
            password='password123',
            name='Distance Other City User',
            role=User.Role.THERAPIST,
        )

        Therapist.objects.create(
            username=self.near_user.username,
            name='Distance Near Profile',
            email='distance_near_profile@example.com',
            kota='Jakarta Selatan',
            kelurahan='Kelurahan Near',
            kecamatan='Kecamatan Near',
            latitude=-6.31,
            longitude=106.81,
        )
        Therapist.objects.create(
            username=self.far_user.username,
            name='Distance Far Profile',
            email='distance_far_profile@example.com',
            kota='Jakarta Selatan',
            kelurahan='Kelurahan Far',
            kecamatan='Kecamatan Far',
            latitude=-6.40,
            longitude=106.90,
        )
        Therapist.objects.create(
            username=self.no_coord_user.username,
            name='Distance NoCoord Profile',
            email='distance_nocoord_profile@example.com',
            kota='Jakarta Selatan',
            latitude=None,
            longitude=None,
        )
        Therapist.objects.create(
            username=self.other_city_user.username,
            name='Distance Other City Profile',
            email='distance_other_city_profile@example.com',
            kota='Bandung',
            kelurahan='Kelurahan Other City',
            kecamatan='Kecamatan Other City',
            latitude=-6.9175,
            longitude=107.6191,
        )

        self.booking = Booking.objects.create(
            nama='Distance Booking',
            alamat='Jl. Booking Distance No. 1',
            kota='Jakarta Selatan',
            no_hp='081234567800',
            tgl_treatment=date.today() + timedelta(days=1),
            jam_treatment=time(10, 0),
            perawatan_pilihan='Swedish Massage',
            aromatherapy_oil=Booking.AromatherapyChoice.LAVENDER,
            latitude=-6.30,
            longitude=106.80,
        )

    @patch('booking.views.geocode_location_from_address')
    def test_geocode_endpoint_success(self, mock_geocode):
        mock_geocode.return_value = (-6.2, 106.8)
        self.client.force_authenticate(user=self.admin)

        response = self.client.post(
            '/api/admin/bookings/geocode/',
            {
                'alamat': 'Jl. Mawar No. 5',
                'kelurahan': 'Cilandak Barat',
                'kecamatan': 'Cilandak',
                'kota': 'Jakarta Selatan',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['latitude'], -6.2)
        self.assertEqual(response.data['data']['longitude'], 106.8)

    @patch('booking.views.geocode_location_from_address')
    def test_geocode_endpoint_fail_not_found(self, mock_geocode):
        mock_geocode.return_value = (None, None)
        self.client.force_authenticate(user=self.admin)

        response = self.client.post(
            '/api/admin/bookings/geocode/',
            {
                'alamat': 'Alamat tidak dikenali',
                'kelurahan': 'Kelurahan Tidak Dikenal',
                'kota': 'Jakarta Selatan',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_non_admin_tidak_bisa_akses_geocode_endpoint(self):
        self.client.force_authenticate(user=self.non_admin)

        response = self.client.post(
            '/api/admin/bookings/geocode/',
            {'alamat': 'Jl. Mawar No. 5'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_therapists_by_distance_return_sorted_nearest_first(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.get(
            f'/api/admin/bookings/{self.booking.booking_id}/therapists-by-distance/'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['data']['results']
        self.assertEqual(len(results), 5)
        self.assertEqual(results[0]['id'], self.near_user.id)

        numeric_distances = [item['distance_km'] for item in results if item['distance_km'] is not None]
        self.assertEqual(numeric_distances, sorted(numeric_distances))

    def test_therapists_by_distance_include_therapist_tanpa_koordinat_di_urutan_bawah(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.get(
            f'/api/admin/bookings/{self.booking.booking_id}/therapists-by-distance/'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['data']['results']
        null_distance_ids = [item['id'] for item in results if item['distance_km'] is None]
        self.assertIn(self.no_coord_user.id, null_distance_ids)
        self.assertTrue(results[-1]['distance_km'] is None)

    def test_therapists_by_distance_include_therapist_beda_kota(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.get(
            f'/api/admin/bookings/{self.booking.booking_id}/therapists-by-distance/'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        result_ids = [item['id'] for item in response.data['data']['results']]
        self.assertIn(self.other_city_user.id, result_ids)

    def test_therapists_by_distance_include_availability_metadata(self):
        TherapistWeeklyAvailability.objects.create(
            therapist=Therapist.objects.get(username=self.far_user.username),
            day_of_week=self.booking.tgl_treatment.weekday(),
            start_time='14:00:00',
            end_time='20:00:00',
            is_active=True,
        )
        self.client.force_authenticate(user=self.admin)

        response = self.client.get(
            f'/api/admin/bookings/{self.booking.booking_id}/therapists-by-distance/'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results_by_id = {item['id']: item for item in response.data['data']['results']}

        self.assertTrue(results_by_id[self.near_user.id]['is_available'])
        self.assertEqual(results_by_id[self.near_user.id]['availability_label'], 'Tersedia')
        self.assertIsNone(results_by_id[self.near_user.id]['availability_reason'])

        self.assertFalse(results_by_id[self.far_user.id]['is_available'])
        self.assertEqual(results_by_id[self.far_user.id]['availability_label'], 'Jadwal tidak tersedia')
        self.assertEqual(
            results_by_id[self.far_user.id]['availability_reason'],
            'Therapist tidak tersedia pada jam booking.'
        )

    def test_therapists_by_distance_tetap_tampil_jika_booking_tanpa_koordinat(self):
        booking_no_coord = Booking.objects.create(
            nama='No Coord Booking',
            alamat='Jl. No Coord',
            kota='Jakarta Selatan',
            no_hp='081234567801',
            tgl_treatment=date.today() + timedelta(days=1),
            jam_treatment=time(14, 0),
            perawatan_pilihan='Reflexology',
            aromatherapy_oil=Booking.AromatherapyChoice.ROSE,
        )
        self.client.force_authenticate(user=self.admin)

        response = self.client.get(
            f'/api/admin/bookings/{booking_no_coord.booking_id}/therapists-by-distance/'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['data']['results']
        self.assertGreater(len(results), 0)
        self.assertTrue(all(item['distance_km'] is None for item in results))

    def test_assign_therapist_berhasil_jika_booking_tanpa_koordinat(self):
        booking_no_coord = Booking.objects.create(
            nama='No Coord Assign Booking',
            alamat='Jl. No Coord Assign',
            kota='Jakarta Selatan',
            no_hp='081234567802',
            tgl_treatment=date.today() + timedelta(days=1),
            jam_treatment=time(14, 0),
            perawatan_pilihan='Reflexology',
            aromatherapy_oil=Booking.AromatherapyChoice.ROSE,
            status=Booking.BookingStatus.PAID,
        )
        self.client.force_authenticate(user=self.admin)

        response = self.client.patch(
            f'/api/admin/bookings/{booking_no_coord.booking_id}/assign-therapist/',
            {
                'therapist_id': self.near_user.id,
            },
            format='json',
        )

        booking_no_coord.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(booking_no_coord.status, Booking.BookingStatus.ASSIGNED)
        self.assertEqual(booking_no_coord.therapist_id, self.near_user.id)

    def test_non_admin_tidak_bisa_akses_therapists_by_distance(self):
        self.client.force_authenticate(user=self.non_admin)

        response = self.client.get(
            f'/api/admin/bookings/{self.booking.booking_id}/therapists-by-distance/'
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class BookingAuditLogAPITest(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='audit_admin',
            email='audit_admin@example.com',
            password='password123',
            name='Audit Admin',
            role=User.Role.ADMIN,
        )
        self.supervisor = User.objects.create_user(
            username='audit_supervisor',
            email='audit_supervisor@example.com',
            password='password123',
            name='Audit Supervisor',
            role=User.Role.SUPERVISOR,
        )
        self.therapist = User.objects.create_user(
            username='audit_therapist',
            email='audit_therapist@example.com',
            password='password123',
            name='Audit Therapist',
            role=User.Role.THERAPIST,
        )
        self.other_therapist = User.objects.create_user(
            username='audit_other_therapist',
            email='audit_other_therapist@example.com',
            password='password123',
            name='Audit Other Therapist',
            role=User.Role.THERAPIST,
        )

        self.booking = Booking.objects.create(
            nama='Audit Customer',
            alamat='Jl. Audit No. 1',
            kelurahan='Kelurahan Audit',
            kecamatan='Kecamatan Audit',
            kota='Jakarta Selatan',
            no_hp='081234560000',
            tgl_treatment=date.today() + timedelta(days=1),
            jam_treatment=time(10, 0),
            perawatan_pilihan='Swedish Massage',
            aromatherapy_oil=Booking.AromatherapyChoice.LAVENDER,
            kondisi_khusus='',
            tahu_dari='Instagram',
            status=Booking.BookingStatus.PENDING,
        )

    @patch('booking.serializers.geocode_location_from_address')
    def test_update_booking_dengan_perubahan_membuat_log(self, mock_geocode):
        mock_geocode.return_value = (-6.25, 106.81)
        self.client.force_authenticate(user=self.admin)

        response = self.client.patch(
            f'/api/admin/bookings/{self.booking.booking_id}/',
            {
                'nama': 'Audit Customer Updated',
                'kota': 'Depok',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(
            BookingChangeLog.objects.filter(
                booking=self.booking,
                field_name='nama',
                old_value='Audit Customer',
                new_value='Audit Customer Updated',
            ).exists()
        )

    @patch('booking.serializers.geocode_location_from_address')
    def test_log_menyimpan_old_dan_new_value(self, mock_geocode):
        mock_geocode.return_value = (-6.26, 106.82)
        self.client.force_authenticate(user=self.admin)

        response = self.client.patch(
            f'/api/admin/bookings/{self.booking.booking_id}/',
            {
                'kota': 'Bandung',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        log = BookingChangeLog.objects.filter(booking=self.booking, field_name='kota').first()
        self.assertIsNotNone(log)
        self.assertEqual(log.old_value, 'Jakarta Selatan')
        self.assertEqual(log.new_value, 'Bandung')

    @patch('booking.serializers.geocode_location_from_address')
    def test_update_tanpa_perubahan_value_tidak_membuat_log(self, mock_geocode):
        mock_geocode.return_value = (None, None)
        self.client.force_authenticate(user=self.admin)

        before_count = BookingChangeLog.objects.filter(booking=self.booking).count()
        response = self.client.patch(
            f'/api/admin/bookings/{self.booking.booking_id}/',
            {
                'nama': self.booking.nama,
                'alamat': self.booking.alamat,
                'kelurahan': self.booking.kelurahan,
                'kecamatan': self.booking.kecamatan,
                'kota': self.booking.kota,
                'no_hp': self.booking.no_hp,
                'tgl_treatment': self.booking.tgl_treatment.isoformat(),
                'jam_treatment': self.booking.jam_treatment.isoformat(),
                'perawatan_pilihan': self.booking.perawatan_pilihan,
                'aromatherapy_oil': self.booking.aromatherapy_oil,
                'kondisi_khusus': self.booking.kondisi_khusus,
                'tahu_dari': self.booking.tahu_dari,
            },
            format='json',
        )
        after_count = BookingChangeLog.objects.filter(booking=self.booking).count()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(before_count, after_count)

    def test_update_status_booking_mencatat_log_status(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.patch(
            f'/api/admin/bookings/{self.booking.booking_id}/status/',
            {
                'status': Booking.BookingStatus.CONFIRMED,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(
            BookingChangeLog.objects.filter(
                booking=self.booking,
                field_name='status',
                old_value=Booking.BookingStatus.PENDING,
                new_value=Booking.BookingStatus.CONFIRMED,
            ).exists()
        )

    def test_assign_dan_reassign_therapist_mencatat_log_therapist(self):
        self.client.force_authenticate(user=self.admin)
        Therapist.objects.create(
            username=self.therapist.username,
            name='Audit Therapist Profile',
            email='audit_therapist_profile@example.com',
            alamat='Jl. Audit Terapis',
            kota='Jakarta Selatan',
        )
        Therapist.objects.create(
            username=self.other_therapist.username,
            name='Audit Other Therapist Profile',
            email='audit_other_therapist_profile@example.com',
            alamat='Jl. Audit Terapis 2',
            kota='Jakarta Selatan',
        )
        self.booking.status = Booking.BookingStatus.PAID
        self.booking.save(update_fields=['status', 'updated_at'])

        assign_response = self.client.patch(
            f'/api/admin/bookings/{self.booking.booking_id}/assign-therapist/',
            {
                'therapist_id': self.therapist.id,
            },
            format='json',
        )
        reassign_response = self.client.patch(
            f'/api/admin/bookings/{self.booking.booking_id}/assign-therapist/',
            {
                'therapist_id': self.other_therapist.id,
            },
            format='json',
        )

        self.assertEqual(assign_response.status_code, status.HTTP_200_OK)
        self.assertEqual(reassign_response.status_code, status.HTTP_200_OK)
        therapist_logs = BookingChangeLog.objects.filter(booking=self.booking, field_name='therapist')
        self.assertEqual(therapist_logs.count(), 2)

    @patch('booking.serializers.geocode_location_from_address')
    def test_changed_by_terisi_jika_request_user_tersedia(self, mock_geocode):
        mock_geocode.return_value = (-6.30, 106.85)
        self.client.force_authenticate(user=self.supervisor)

        response = self.client.patch(
            f'/api/admin/bookings/{self.booking.booking_id}/',
            {
                'kota': 'Bogor',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        log = BookingChangeLog.objects.filter(booking=self.booking, field_name='kota').first()
        self.assertIsNotNone(log)
        self.assertEqual(log.changed_by_id, self.supervisor.id)

    @patch('booking.serializers.geocode_location_from_address')
    def test_endpoint_change_logs_hanya_staff_berwenang(self, mock_geocode):
        mock_geocode.return_value = (-6.20, 106.80)
        self.client.force_authenticate(user=self.admin)
        self.client.patch(
            f'/api/admin/bookings/{self.booking.booking_id}/',
            {
                'kota': 'Tangerang',
            },
            format='json',
        )

        admin_response = self.client.get(
            f'/api/admin/bookings/{self.booking.booking_id}/change-logs/'
        )
        self.client.force_authenticate(user=self.therapist)
        non_admin_response = self.client.get(
            f'/api/admin/bookings/{self.booking.booking_id}/change-logs/'
        )

        self.assertEqual(admin_response.status_code, status.HTTP_200_OK)
        self.assertIn('count', admin_response.data)
        self.assertIn('results', admin_response.data)
        self.assertEqual(non_admin_response.status_code, status.HTTP_403_FORBIDDEN)
