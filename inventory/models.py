from django.conf import settings
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
    usage_per_unit = models.PositiveIntegerField(
        default=1,
        help_text="Kapasitas penggunaan per 1 unit item (harus > 0).",
    )
    assignment_inactive_after_days = models.PositiveIntegerField(
        default=30,
        help_text=(
            "Batas hari dasar sebelum assignment dianggap INACTIVE. "
            "Masa aktif efektif assignment = nilai ini x quantity_assigned."
        ),
    )
    keterangan = models.TextField(blank=True, default="")
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["nama_barang"]
        verbose_name_plural = "inventories"

    def __str__(self) -> str:
        return self.nama_barang


class TherapistSupplyAssignment(models.Model):
    """
    Assignment bahan inventory ke therapist.
    Satu therapist bisa punya beberapa assignment untuk item yang sama.
    """

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        EXHAUSTED = "EXHAUSTED", "Exhausted"
        INACTIVE = "INACTIVE", "Inactive"

    item = models.ForeignKey(
        Inventory,
        on_delete=models.CASCADE,
        related_name="supply_assignments",
        help_text="Item inventory yang di-assign.",
    )
    therapist = models.ForeignKey(
        "therapist.Therapist",
        on_delete=models.CASCADE,
        related_name="supply_assignments",
        help_text="Therapist yang menerima assignment.",
    )
    quantity_assigned = models.PositiveIntegerField(
        help_text="Berapa unit item yang dibawa therapist.",
    )
    usage_per_unit = models.PositiveIntegerField(
        help_text="Snapshot usagePerUnit dari inventory saat assignment dibuat.",
    )
    total_usage = models.PositiveIntegerField(
        help_text="quantityAssigned * usagePerUnit (dihitung otomatis).",
    )
    remaining_usage = models.PositiveIntegerField(
        help_text="Sisa kapasitas penggunaan.",
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    notes = models.TextField(blank=True, default="")

    assigned_at = models.DateTimeField(auto_now_add=True)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="assignments_created",
        help_text="User yang membuat assignment.",
    )

    # Audit / soft-delete
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assignments_updated",
        help_text="User yang terakhir mengubah assignment.",
    )
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assignments_deleted",
        help_text="User yang menghapus assignment.",
    )

    class Meta:
        ordering = ["-assigned_at"]
        verbose_name = "therapist supply assignment"
        verbose_name_plural = "therapist supply assignments"
        indexes = [
            models.Index(fields=["item", "therapist"]),
            models.Index(fields=["therapist", "status"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self) -> str:
        return (
            f"Assignment #{self.pk}: {self.item.nama_barang} → "
            f"Therapist {self.therapist.name} (qty={self.quantity_assigned})"
        )


class SupplyUsageLog(models.Model):
    """
    Riwayat pemakaian item inventory oleh therapist, dicatat ketika
    status booking menjadi COMPLETED berdasarkan assignment aktif.
    """
    item = models.ForeignKey(
        Inventory,
        on_delete=models.CASCADE,
        related_name="usage_logs",
    )
    therapist = models.ForeignKey(
        "therapist.Therapist",
        on_delete=models.CASCADE,
        related_name="supply_usage_logs",
    )
    jumlah = models.PositiveIntegerField(
        help_text="Kuantitas penggunaan item."
    )
    tanggal = models.DateField(
        help_text="Tanggal pemakaian (biasanya tanggal booking treatment)."
    )
    booking = models.ForeignKey(
        "booking.Booking",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="supply_usage_logs",
        help_text="Booking terkait untuk jejak audit/idempotensi.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-tanggal", "-created_at"]
        verbose_name_plural = "supply usage logs"
        # Memastikan tidak ada double-log untuk kombinasi booking, item, dan therapist yang sama
        constraints = [
            models.UniqueConstraint(
                fields=['booking', 'item', 'therapist'],
                name='unique_booking_item_therapist_usage_log'
            )
        ]
        indexes = [
            models.Index(fields=["item", "therapist", "tanggal"]),
            models.Index(fields=["tanggal"]),
        ]

    def __str__(self) -> str:
        return f"{self.item.nama_barang} ({self.jumlah}) oleh {self.therapist.name} [{self.tanggal}]"

