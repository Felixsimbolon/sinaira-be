from django.db import models


class Inventory(models.Model):
    """
    Satu baris = satu item fisik (mis. satu jenis minyak, satu alat).
    status_stok dihitung di serializer, tidak disimpan di DB.
    """

    class Kategori(models.TextChoices):
        STICKER = "Sticker", "Sticker"
        BAHAN_BODY_MASSAGE = "Bahan Body Massage", "Bahan Body Massage"
        BAHAN_SCRUB = "Bahan Scrub", "Bahan Scrub"
        BAHAN_MASKER = "Bahan Masker", "Bahan Masker"
        BAHAN_CREAMBATH = "Bahan Creambath", "Bahan Creambath"
        BAHAN_TOTOK_WAJAH = (
            "Bahan Totok Wajah & Natural Facial",
            "Bahan Totok Wajah & Natural Facial",
        )
        BAHAN_FOOT_REFLEXY = "Bahan Foot Reflexy", "Bahan Foot Reflexy"
        BAHAN_LAINNYA = "Bahan Lainnya", "Bahan Lainnya"
        ALAT_PERAWATAN = "Alat-Alat Perawatan", "Alat-Alat Perawatan"
        SERAGAM_BATIK = "Seragam Batik", "Seragam Batik"
        KETERANGAN_TAMBAHAN = "Keterangan Tambahan", "Keterangan Tambahan"

    class Lokasi(models.TextChoices):
        CILEGON = "CILEGON", "CILEGON"
        SERANG = "SERANG", "SERANG"
        BATAM = "BATAM", "BATAM"

    nama_barang = models.CharField(max_length=255)
    kategori = models.CharField(max_length=80, choices=Kategori.choices)
    lokasi = models.CharField(max_length=20, choices=Lokasi.choices, default=Lokasi.CILEGON)
    jumlah_stok = models.PositiveIntegerField()
    threshold_minimum = models.PositiveIntegerField()
    keterangan = models.TextField(blank=True, default="")
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["nama_barang"]
        verbose_name_plural = "inventories"

    def __str__(self) -> str:
        return self.nama_barang
