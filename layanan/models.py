from django.db import models
from django.utils import timezone
from uuid import uuid4


def generate_kategori_id() -> str:
	return f"KTG-{uuid4().hex[:8].upper()}"


def generate_layanan_id() -> str:
	return f"LYN-{uuid4().hex[:8].upper()}"


class ActiveLayananManager(models.Manager):
	def get_queryset(self):
		return super().get_queryset().filter(is_deleted=False)


class LayananKategori(models.Model):
	"""Kategori layanan untuk kebutuhan dropdown di frontend."""

	kategori_id = models.CharField(max_length=20, unique=True, default=generate_kategori_id, editable=False)
	nama = models.CharField(max_length=100, unique=True)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ["nama"]

	def __str__(self):
		return self.nama


class Layanan(models.Model):
	"""Menu layanan dengan kategori, durasi, dan soft delete."""

	layanan_id = models.CharField(max_length=20, unique=True, default=generate_layanan_id, editable=False)
	kategori = models.ForeignKey(
		LayananKategori,
		on_delete=models.PROTECT,
		related_name="layanans",
		null=True,
		blank=True,
	)
	nama = models.CharField(max_length=255)
	durasi_menit = models.PositiveIntegerField(default=60, help_text="Durasi layanan dalam menit")
	deskripsi = models.TextField(blank=True, null=True)
	harga = models.PositiveIntegerField(help_text="Harga layanan dalam rupiah")
	is_active = models.BooleanField(default=True)
	is_deleted = models.BooleanField(default=False)
	deleted_at = models.DateTimeField(blank=True, null=True)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	objects = models.Manager()
	active_objects = ActiveLayananManager()

	class Meta:
		ordering = ["kategori__nama", "nama"]
		constraints = [
			models.UniqueConstraint(fields=["kategori", "nama"], condition=models.Q(is_deleted=False), name="unique_active_layanan_per_kategori")
		]

	def soft_delete(self):
		self.is_deleted = True
		self.deleted_at = timezone.now()
		self.save(update_fields=["is_deleted", "deleted_at", "updated_at"])

	def __str__(self):
		kategori_nama = self.kategori.nama if self.kategori else "Tanpa Kategori"
		return f"{self.nama} ({kategori_nama}) - {self.harga}"
