from django.db import models


class Layanan(models.Model):
	"""Menu layanan dengan field minimal nama dan harga."""

	nama = models.CharField(max_length=255, unique=True)
	harga = models.PositiveIntegerField(help_text="Harga layanan dalam rupiah")
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ["nama"]

	def __str__(self):
		return f"{self.nama} - {self.harga}"
