from unittest.mock import patch
from datetime import date, timedelta

from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from therapist.models import Therapist, TherapistDateOverride, TherapistWeeklyAvailability


class TherapistGeocodeAndPhoneAPITest(APITestCase):
	def setUp(self):
		self.admin = User.objects.create_user(
			username='therapist_admin',
			email='therapist_admin@example.com',
			password='password123',
			name='Therapist Admin',
			role=User.Role.ADMIN,
		)
		self.non_admin = User.objects.create_user(
			username='therapist_actor',
			email='therapist_actor@example.com',
			password='password123',
			name='Therapist Actor',
			role=User.Role.THERAPIST,
		)

	@patch('therapist.serializers.geocode_location_from_address')
	def test_create_therapist_auto_geocode_success(self, mock_geocode):
		mock_geocode.return_value = (-6.22, 106.81)
		self.client.force_authenticate(user=self.admin)

		response = self.client.post(
			'/api/therapists/',
			{
				'username': 'therapist_auto_geo',
				'name': 'Therapist Auto Geo',
				'email': 'therapist_auto_geo@example.com',
				'alamat': 'Jl. Terapis No. 1',
				'kelurahan': 'Kelurahan Terapis',
				'kecamatan': 'Kecamatan Terapis',
				'kota': 'Jakarta Selatan',
				'no_hp': '081234567899',
				'latitude': -1.0,
				'longitude': 1.0,
			},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_201_CREATED)
		therapist = Therapist.objects.get(username='therapist_auto_geo')
		self.assertEqual(therapist.latitude, -6.22)
		self.assertEqual(therapist.longitude, 106.81)

	@patch('therapist.serializers.geocode_location_from_address')
	def test_create_therapist_auto_geocode_fail_graceful(self, mock_geocode):
		mock_geocode.return_value = (None, None)
		self.client.force_authenticate(user=self.admin)

		response = self.client.post(
			'/api/therapists/',
			{
				'username': 'therapist_auto_geo_fail',
				'name': 'Therapist Auto Geo Fail',
				'email': 'therapist_auto_geo_fail@example.com',
				'alamat': 'Alamat Tidak Dikenal',
				'kota': 'Jakarta Selatan',
				'no_hp': '081234567898',
			},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_201_CREATED)
		therapist = Therapist.objects.get(username='therapist_auto_geo_fail')
		self.assertIsNone(therapist.latitude)
		self.assertIsNone(therapist.longitude)

	def test_latitude_longitude_tidak_wajib_saat_create(self):
		self.client.force_authenticate(user=self.admin)

		response = self.client.post(
			'/api/therapists/',
			{
				'username': 'therapist_no_latlng',
				'name': 'Therapist No LatLng',
				'email': 'therapist_no_latlng@example.com',
				'alamat': 'Jl. Terapis No LatLng',
				'kota': 'Depok',
				'no_hp': '081234567897',
			},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_201_CREATED)

	@patch('therapist.serializers.geocode_location_from_address')
	def test_update_alamat_therapist_auto_geocode_ulang(self, mock_geocode):
		mock_geocode.return_value = (-6.28, 106.75)
		therapist = Therapist.objects.create(
			username='therapist_update_geo',
			name='Therapist Update Geo',
			email='therapist_update_geo@example.com',
			alamat='Alamat Lama',
			kota='Jakarta Selatan',
			latitude=-6.20,
			longitude=106.80,
		)
		self.client.force_authenticate(user=self.admin)

		response = self.client.patch(
			f'/api/therapists/{therapist.id}/',
			{
				'alamat': 'Alamat Baru',
				'kelurahan': 'Kelurahan Baru',
				'kecamatan': 'Kecamatan Baru',
				'kota': 'Depok',
			},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		therapist.refresh_from_db()
		self.assertEqual(therapist.latitude, -6.28)
		self.assertEqual(therapist.longitude, 106.75)

	@patch('therapist.serializers.geocode_location_from_address')
	def test_update_alamat_therapist_auto_geocode_fail_graceful(self, mock_geocode):
		mock_geocode.return_value = (None, None)
		therapist = Therapist.objects.create(
			username='therapist_update_geo_fail',
			name='Therapist Update Geo Fail',
			email='therapist_update_geo_fail@example.com',
			alamat='Alamat Lama',
			kota='Jakarta Selatan',
			latitude=-6.19,
			longitude=106.79,
		)
		self.client.force_authenticate(user=self.admin)

		response = self.client.patch(
			f'/api/therapists/{therapist.id}/',
			{
				'alamat': 'Alamat Tidak Dikenal',
				'kota': 'Depok',
			},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		therapist.refresh_from_db()
		self.assertIsNone(therapist.latitude)
		self.assertIsNone(therapist.longitude)

	def test_latitude_longitude_bisa_diedit_saat_update(self):
		therapist = Therapist.objects.create(
			username='therapist_edit_latlng',
			name='Therapist Edit LatLng',
			email='therapist_edit_latlng@example.com',
			alamat='Alamat Awal',
			kota='Jakarta Selatan',
		)
		self.client.force_authenticate(user=self.admin)

		response = self.client.patch(
			f'/api/therapists/{therapist.id}/',
			{
				'latitude': -6.44,
				'longitude': 107.02,
			},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		therapist.refresh_from_db()
		self.assertEqual(therapist.latitude, -6.44)
		self.assertEqual(therapist.longitude, 107.02)

	@patch('therapist.views.geocode_location_from_address')
	def test_manual_geocode_trigger_therapist_success(self, mock_geocode):
		mock_geocode.return_value = (-6.27, 106.76)
		therapist = Therapist.objects.create(
			username='therapist_manual_geo',
			name='Therapist Manual Geo',
			email='therapist_manual_geo@example.com',
			alamat='Alamat Manual',
			kota='Jakarta Selatan',
		)
		self.client.force_authenticate(user=self.admin)

		response = self.client.post(
			f'/api/admin/therapists/{therapist.id}/geocode/',
			{},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		therapist.refresh_from_db()
		self.assertEqual(therapist.latitude, -6.27)
		self.assertEqual(therapist.longitude, 106.76)

	@patch('therapist.views.geocode_location_from_address')
	def test_manual_geocode_trigger_therapist_fail_graceful(self, mock_geocode):
		mock_geocode.return_value = (None, None)
		therapist = Therapist.objects.create(
			username='therapist_manual_geo_fail',
			name='Therapist Manual Geo Fail',
			email='therapist_manual_geo_fail@example.com',
			alamat='Alamat Manual',
			kota='Jakarta Selatan',
		)
		self.client.force_authenticate(user=self.admin)

		response = self.client.post(
			f'/api/admin/therapists/{therapist.id}/geocode/',
			{},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

	def test_manual_geocode_trigger_therapist_forbidden_non_admin(self):
		therapist = Therapist.objects.create(
			username='therapist_manual_geo_forbidden',
			name='Therapist Manual Geo Forbidden',
			email='therapist_manual_geo_forbidden@example.com',
			alamat='Alamat Manual',
			kota='Jakarta Selatan',
		)
		self.client.force_authenticate(user=self.non_admin)

		response = self.client.post(
			f'/api/admin/therapists/{therapist.id}/geocode/',
			{},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

	def test_therapist_no_hp_validation_invalid(self):
		self.client.force_authenticate(user=self.admin)

		response = self.client.post(
			'/api/therapists/',
			{
				'username': 'therapist_phone_invalid',
				'name': 'Therapist Phone Invalid',
				'email': 'therapist_phone_invalid@example.com',
				'alamat': 'Alamat',
				'kota': 'Depok',
				'no_hp': '08ABC123',
			},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
		self.assertIn('no_hp', response.data)

	def test_therapist_no_hp_validation_valid(self):
		self.client.force_authenticate(user=self.admin)

		response = self.client.post(
			'/api/therapists/',
			{
				'username': 'therapist_phone_valid',
				'name': 'Therapist Phone Valid',
				'email': 'therapist_phone_valid@example.com',
				'alamat': 'Alamat',
				'kota': 'Depok',
				'no_hp': '081234567896',
			},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class TherapistTimetableAPITest(APITestCase):
	def setUp(self):
		self.admin = User.objects.create_user(
			username='timetable_admin',
			email='timetable_admin@example.com',
			password='password123',
			name='Timetable Admin',
			role=User.Role.ADMIN,
		)
		self.non_admin = User.objects.create_user(
			username='timetable_therapist_actor',
			email='timetable_therapist_actor@example.com',
			password='password123',
			name='Timetable Therapist Actor',
			role=User.Role.THERAPIST,
		)
		self.therapist = Therapist.objects.create(
			username='timetable_profile',
			name='Timetable Therapist',
			email='timetable_profile@example.com',
			alamat='Jl. Timetable',
			kota='Jakarta Selatan',
		)

	def test_create_weekly_slot_valid(self):
		self.client.force_authenticate(user=self.admin)
		response = self.client.post(
			f'/api/admin/therapists/{self.therapist.id}/weekly-schedule/',
			{
				'day_of_week': 0,
				'start_time': '08:00:00',
				'end_time': '12:00:00',
				'is_active': True,
			},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_201_CREATED)
		self.assertEqual(TherapistWeeklyAvailability.objects.filter(therapist=self.therapist).count(), 1)

	def test_reject_weekly_overlap(self):
		TherapistWeeklyAvailability.objects.create(
			therapist=self.therapist,
			day_of_week=0,
			start_time='08:00:00',
			end_time='12:00:00',
		)
		self.client.force_authenticate(user=self.admin)

		response = self.client.post(
			f'/api/admin/therapists/{self.therapist.id}/weekly-schedule/',
			{
				'day_of_week': 0,
				'start_time': '11:00:00',
				'end_time': '14:00:00',
				'is_active': True,
			},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

	def test_create_date_override_valid(self):
		self.client.force_authenticate(user=self.admin)
		target_date = date.today() + timedelta(days=1)

		response = self.client.post(
			f'/api/admin/therapists/{self.therapist.id}/date-overrides/',
			{
				'date': target_date.isoformat(),
				'override_type': 'AVAILABLE',
				'start_time': '10:00:00',
				'end_time': '13:00:00',
				'note': 'Shift khusus',
			},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_201_CREATED)
		self.assertEqual(TherapistDateOverride.objects.filter(therapist=self.therapist).count(), 1)

	def test_reject_date_override_overlap(self):
		target_date = date.today() + timedelta(days=1)
		TherapistDateOverride.objects.create(
			therapist=self.therapist,
			date=target_date,
			override_type='AVAILABLE',
			start_time='10:00:00',
			end_time='13:00:00',
		)
		self.client.force_authenticate(user=self.admin)

		response = self.client.post(
			f'/api/admin/therapists/{self.therapist.id}/date-overrides/',
			{
				'date': target_date.isoformat(),
				'override_type': 'AVAILABLE',
				'start_time': '12:00:00',
				'end_time': '14:00:00',
			},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

	def test_unavailable_partial_override_behavior(self):
		self.client.force_authenticate(user=self.admin)
		target_date = date.today() + timedelta(days=2)

		create_response = self.client.post(
			f'/api/admin/therapists/{self.therapist.id}/date-overrides/',
			{
				'date': target_date.isoformat(),
				'override_type': 'UNAVAILABLE',
				'start_time': '13:00:00',
				'end_time': '15:00:00',
				'note': 'Absen parsial',
			},
			format='json',
		)

		timetable_response = self.client.get(
			f'/api/admin/therapists/{self.therapist.id}/timetable/?start_date={target_date.isoformat()}&end_date={target_date.isoformat()}'
		)

		self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
		self.assertEqual(timetable_response.status_code, status.HTTP_200_OK)
		result = timetable_response.data['data']['results'][0]
		self.assertEqual(result['source'], 'override')
		self.assertFalse(result['off'])
		unavailable_slots = [slot for slot in result['slots'] if slot['status'] == 'unavailable']
		self.assertEqual(len(unavailable_slots), 1)
		self.assertEqual(unavailable_slots[0]['start_time'], '13:00:00')
		self.assertEqual(unavailable_slots[0]['end_time'], '15:00:00')

	def test_resolved_timetable_fallback_default_09_19(self):
		self.client.force_authenticate(user=self.admin)
		target_date = date.today() + timedelta(days=4)

		response = self.client.get(
			f'/api/admin/therapists/{self.therapist.id}/timetable/?start_date={target_date.isoformat()}&end_date={target_date.isoformat()}'
		)

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		data = response.data['data']
		self.assertEqual(data['time_window']['grid_start'], '07:00:00')
		self.assertEqual(data['time_window']['grid_end'], '20:00:00')
		self.assertEqual(data['time_window']['default_available_start'], '09:00:00')
		self.assertEqual(data['time_window']['default_available_end'], '19:00:00')

		result = data['results'][0]
		self.assertEqual(result['source'], 'default')
		available_slots = [slot for slot in result['slots'] if slot['status'] == 'available']
		self.assertEqual(len(available_slots), 1)
		self.assertEqual(available_slots[0]['start_time'], '09:00:00')
		self.assertEqual(available_slots[0]['end_time'], '19:00:00')

	def test_resolved_timetable_weekly_only(self):
		TherapistWeeklyAvailability.objects.create(
			therapist=self.therapist,
			day_of_week=0,
			start_time='08:00:00',
			end_time='12:00:00',
			is_active=True,
		)
		self.client.force_authenticate(user=self.admin)

		start_date = date.today()
		while start_date.weekday() != 0:
			start_date += timedelta(days=1)

		response = self.client.get(
			f'/api/admin/therapists/{self.therapist.id}/timetable/?start_date={start_date.isoformat()}&end_date={start_date.isoformat()}'
		)

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		result = response.data['data']['results'][0]
		self.assertEqual(result['source'], 'weekly')
		self.assertFalse(result['off'])
		available_slots = [slot for slot in result['slots'] if slot['status'] == 'available']
		self.assertEqual(len(available_slots), 1)

	def test_resolved_timetable_override_precedence(self):
		target_date = date.today() + timedelta(days=3)
		TherapistWeeklyAvailability.objects.create(
			therapist=self.therapist,
			day_of_week=target_date.weekday(),
			start_time='09:00:00',
			end_time='19:00:00',
			is_active=True,
		)
		TherapistDateOverride.objects.create(
			therapist=self.therapist,
			date=target_date,
			override_type='UNAVAILABLE',
			start_time='13:00:00',
			end_time='15:00:00',
		)
		self.client.force_authenticate(user=self.admin)

		response = self.client.get(
			f'/api/admin/therapists/{self.therapist.id}/timetable/?start_date={target_date.isoformat()}&end_date={target_date.isoformat()}'
		)

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		result = response.data['data']['results'][0]
		self.assertEqual(result['source'], 'override')
		available_slots = [slot for slot in result['slots'] if slot['status'] == 'available']
		unavailable_slots = [slot for slot in result['slots'] if slot['status'] == 'unavailable']
		self.assertEqual(len(available_slots), 2)
		self.assertEqual(available_slots[0]['start_time'], '09:00:00')
		self.assertEqual(available_slots[0]['end_time'], '13:00:00')
		self.assertEqual(available_slots[1]['start_time'], '15:00:00')
		self.assertEqual(available_slots[1]['end_time'], '19:00:00')
		self.assertEqual(len(unavailable_slots), 1)
		self.assertEqual(unavailable_slots[0]['start_time'], '13:00:00')
		self.assertEqual(unavailable_slots[0]['end_time'], '15:00:00')

	def test_permission_admin_staff_vs_non_admin(self):
		self.client.force_authenticate(user=self.non_admin)

		response = self.client.get(
			f'/api/admin/therapists/{self.therapist.id}/weekly-schedule/'
		)

		self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
