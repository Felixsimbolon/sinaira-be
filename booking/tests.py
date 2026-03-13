from django.test import TestCase
from datetime import date, time, timedelta
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from .models import Booking
from .utils import (
    sanitize_whatsapp_text,
    normalize_phone,
    normalize_aromatherapy,
    extract_booking_from_whatsapp_message,
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
    def test_converts_leading_zero_to_plus62(self):
        self.assertEqual(normalize_phone("08123456789"), "+628123456789")

    def test_removes_spaces_and_dashes(self):
        self.assertEqual(normalize_phone("0812 3456-789"), "+628123456789")

    def test_keeps_plus62_prefix(self):
        self.assertEqual(normalize_phone("+628123456789"), "+628123456789")

    def test_empty_string(self):
        self.assertEqual(normalize_phone(""), "")

    def test_removes_parentheses(self):
        self.assertEqual(normalize_phone("(0812)3456789"), "+6281234567 89".replace(" ", ""))


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
        self.assertEqual(result["no_hp"], "+628123456789")
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
        self.assertEqual(result["no_hp"], "+6285612345678")


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
        booking = self._create_booking(status_value=Booking.BookingStatus.CONFIRMED)
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
        booking = self._create_booking(status_value=Booking.BookingStatus.CONFIRMED)
        self.client.force_authenticate(user=self.admin)

        response = self.client.patch(
            f'/api/admin/bookings/{booking.booking_id}/assign-therapist/',
            {'therapist_id': self.therapist.id},
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
