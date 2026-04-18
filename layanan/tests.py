from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from inventory.models import Inventory
from layanan.models import Layanan, LayananKategori, LayananSupplyConfig


class LayananSupplyConfigTest(APITestCase):
    def setUp(self):
        # Create users
        self.owner = User.objects.create_user(
            username="test_owner", email="owner@test.com", password="pwd", role=User.Role.OWNER
        )
        self.therapist = User.objects.create_user(
            username="test_therapist", email="therapist@test.com", password="pwd", role=User.Role.THERAPIST
        )

        # Create Kategori
        self.kategori = LayananKategori.objects.create(nama="Kategori Test")

        # Create Items
        self.item1 = Inventory.objects.create(
            nama_barang="Minyak Pijat",
            kategori=Inventory.Kategori.BAHAN_BODY_MASSAGE,
            jumlah_stok=100,
            threshold_minimum=10,
            usage_per_unit=5,
        )
        self.item2 = Inventory.objects.create(
            nama_barang="Scrub",
            kategori=Inventory.Kategori.BAHAN_SCRUB,
            jumlah_stok=50,
            threshold_minimum=5,
            usage_per_unit=2,
        )

        self.layanan_url = "/api/layanan/"

    def test_unauthenticated_returns_401(self):
        response = self.client.post(self.layanan_url, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_permission_therapist_returns_403(self):
        self.client.force_authenticate(user=self.therapist)
        response = self.client.post(self.layanan_url, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_layanan_tanpa_kebutuhan_bahan(self):
        self.client.force_authenticate(user=self.owner)
        payload = {
            "kategori_id": self.kategori.kategori_id,
            "nama": "Pijat Biasa",
            "durasi_menit": 60,
            "harga": 150000,
            "is_active": True,
        }
        res = self.client.post(self.layanan_url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["kebutuhan_bahan"], [])

    def test_create_layanan_dengan_kebutuhan_bahan_valid(self):
        self.client.force_authenticate(user=self.owner)
        payload = {
            "kategori_id": self.kategori.kategori_id,
            "nama": "Pijat Plus Lulur",
            "durasi_menit": 90,
            "harga": 250000,
            "is_active": True,
            "kebutuhan_bahan": [
                {"item_id": self.item1.id, "jumlah_per_use": 2},
                {"item_id": self.item2.id, "jumlah_per_use": 1},
            ],
        }
        res = self.client.post(self.layanan_url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(res.data["kebutuhan_bahan"]), 2)
        
        configs = LayananSupplyConfig.objects.filter(layanan__layanan_id=res.data["id"])
        self.assertEqual(configs.count(), 2)

    def test_update_layanan_tambah_dan_ubah_mapping(self):
        self.client.force_authenticate(user=self.owner)
        layanan = Layanan.objects.create(kategori=self.kategori, nama="Pijat Lulur", durasi_menit=90, harga=200000)
        config1 = LayananSupplyConfig.objects.create(layanan=layanan, item=self.item1, jumlah_per_use=1)

        url = f"{self.layanan_url}{layanan.layanan_id}/"
        payload = {
            "kebutuhan_bahan": [
                {"item_id": self.item1.id, "jumlah_per_use": 3},  # Ubah quantity
                {"item_id": self.item2.id, "jumlah_per_use": 2},  # Tambah baru
            ]
        }
        res = self.client.patch(url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data["kebutuhan_bahan"]), 2)

        config1.refresh_from_db()
        self.assertEqual(config1.jumlah_per_use, 3)
        self.assertEqual(config1.is_deleted, False)
        
        configs = LayananSupplyConfig.objects.filter(layanan=layanan, is_deleted=False)
        self.assertEqual(configs.count(), 2)

    def test_update_layanan_hapus_mapping(self):
        self.client.force_authenticate(user=self.owner)
        layanan = Layanan.objects.create(kategori=self.kategori, nama="Layanan X", durasi_menit=60, harga=100000)
        config1 = LayananSupplyConfig.objects.create(layanan=layanan, item=self.item1, jumlah_per_use=1)
        config2 = LayananSupplyConfig.objects.create(layanan=layanan, item=self.item2, jumlah_per_use=2)

        url = f"{self.layanan_url}{layanan.layanan_id}/"
        # Hanya kirim item1, item2 harusnya tersoft-delete
        payload = {
            "kebutuhan_bahan": [
                {"item_id": self.item1.id, "jumlah_per_use": 1},
            ]
        }
        res = self.client.patch(url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        
        config2.refresh_from_db()
        self.assertTrue(config2.is_deleted)
        self.assertIsNotNone(config2.deleted_at)

    def test_update_layanan_kebutuhan_kosong(self):
        self.client.force_authenticate(user=self.owner)
        layanan = Layanan.objects.create(kategori=self.kategori, nama="Layanan Kosong", durasi_menit=30, harga=50000)
        config1 = LayananSupplyConfig.objects.create(layanan=layanan, item=self.item1, jumlah_per_use=1)

        url = f"{self.layanan_url}{layanan.layanan_id}/"
        payload = {"kebutuhan_bahan": []}  # Kosongkan
        res = self.client.patch(url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data["kebutuhan_bahan"]), 0)
        
        config1.refresh_from_db()
        self.assertTrue(config1.is_deleted)

    def test_update_layanan_tanpa_field_kebutuhan(self):
        self.client.force_authenticate(user=self.owner)
        layanan = Layanan.objects.create(kategori=self.kategori, nama="Layanan Y", durasi_menit=60, harga=100000)
        config1 = LayananSupplyConfig.objects.create(layanan=layanan, item=self.item1, jumlah_per_use=1)

        url = f"{self.layanan_url}{layanan.layanan_id}/"
        payload = {"harga": 150000}  # Tidak kirim kebutuhan_bahan
        res = self.client.patch(url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        
        config1.refresh_from_db()
        self.assertFalse(config1.is_deleted)  # Tidak berubah
        self.assertEqual(len(res.data["kebutuhan_bahan"]), 1)

    def test_validasi_jumlah_per_use_harus_positif(self):
        self.client.force_authenticate(user=self.owner)
        payload = {
            "kategori_id": self.kategori.kategori_id,
            "nama": "Pijat 2",
            "durasi_menit": 60,
            "harga": 100000,
            "kebutuhan_bahan": [
                {"item_id": self.item1.id, "jumlah_per_use": 0},
            ],
        }
        res = self.client.post(self.layanan_url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("kebutuhan_bahan", res.data)

    def test_validasi_item_invalid_atau_dihapus(self):
        self.item2.is_deleted = True
        self.item2.save()
        
        self.client.force_authenticate(user=self.owner)
        payload = {
            "kategori_id": self.kategori.kategori_id,
            "nama": "Pijat 3",
            "durasi_menit": 60,
            "harga": 100000,
            "kebutuhan_bahan": [
                {"item_id": self.item2.id, "jumlah_per_use": 1},
                {"item_id": 999, "jumlah_per_use": 1},
            ],
        }
        res = self.client.post(self.layanan_url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_validasi_item_duplikat(self):
        self.client.force_authenticate(user=self.owner)
        payload = {
            "kategori_id": self.kategori.kategori_id,
            "nama": "Pijat 4",
            "durasi_menit": 60,
            "harga": 100000,
            "kebutuhan_bahan": [
                {"item_id": self.item1.id, "jumlah_per_use": 1},
                {"item_id": self.item1.id, "jumlah_per_use": 2},
            ],
        }
        res = self.client.post(self.layanan_url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
