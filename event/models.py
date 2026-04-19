from django.conf import settings
from django.db import models
from django.utils import timezone

from layanan.models import Layanan
from .helpers import compute_cta_state, compute_promo_status, resolve_active_cta_label


class ActivePromoManager(models.Manager):
	"""Default manager for non-deleted promo/event records."""

	def get_queryset(self):
		return super().get_queryset().filter(deleted_at__isnull=True)


class Promo(models.Model):
	class ContentType(models.TextChoices):
		PROMO = "promo", "Promo"
		EVENT = "event", "Event"

	class BenefitType(models.TextChoices):
		FREE_SERVICE = "free_service", "Gratis Layanan"
		DISCOUNT_NOMINAL = "discount_nominal", "Potongan Rp"
		DISCOUNT_PERCENT = "discount_percent", "Potongan %"

	class PostingState(models.TextChoices):
		DRAFT = "draft", "Draft"
		PUBLISHED = "published", "Published"
		ARCHIVED = "archived", "Archived"

	class CtaType(models.TextChoices):
		USE = "use", "Use"
		REGISTER = "register", "Register"
		CLAIM = "claim", "Claim"
		CUSTOM = "custom", "Custom"

	title = models.CharField(max_length=255)
	description = models.TextField()
	image = models.URLField(blank=True, null=True)
	external_link = models.URLField(blank=True, null=True)
	content_type = models.CharField(
		max_length=20,
		choices=ContentType.choices,
		default=ContentType.PROMO,
	)
	posting_state = models.CharField(
		max_length=20,
		choices=PostingState.choices,
		default=PostingState.DRAFT,
	)
	start_date = models.DateField(blank=True, null=True)
	end_date = models.DateField(blank=True, null=True)

	# Kondisi promo (opsional)
	min_total_price = models.DecimalField(
		max_digits=15,
		decimal_places=2,
		blank=True,
		null=True,
		help_text="Minimum total harga layanan untuk berlaku promo (dalam Rp)"
	)
	applicable_services = models.ManyToManyField(
		Layanan,
		blank=True,
		related_name="applicable_promos",
		help_text="Layanan yang berlaku untuk promo ini. Kosong = semua layanan"
	)

	# Benefit promo
	benefit_type = models.CharField(
		max_length=20,
		choices=BenefitType.choices,
		blank=True,
		null=True,
		help_text="Tipe benefit promo"
	)
	benefit_free_service = models.ForeignKey(
		Layanan,
		on_delete=models.SET_NULL,
		blank=True,
		null=True,
		related_name="free_service_promos",
		help_text="Layanan gratis jika benefit_type adalah free_service"
	)
	benefit_discount_amount = models.DecimalField(
		max_digits=15,
		decimal_places=2,
		blank=True,
		null=True,
		help_text="Potongan harga dalam Rp jika benefit_type adalah discount_nominal"
	)
	benefit_discount_percent = models.IntegerField(
		blank=True,
		null=True,
		help_text="Potongan harga dalam % jika benefit_type adalah discount_percent"
	)

	# Show in booking
	show_in_booking = models.BooleanField(
		default=True,
		help_text="Tampilkan promo ini di halaman booking customer"
	)

	cta_type = models.CharField(
		max_length=20,
		choices=CtaType.choices,
		default=CtaType.USE,
	)
	cta_text = models.CharField(max_length=100, blank=True, null=True)
	created_by = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.SET_NULL,
		blank=True,
		null=True,
		related_name="created_promos",
	)
	updated_by = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.SET_NULL,
		blank=True,
		null=True,
		related_name="updated_promos",
	)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)
	deleted_at = models.DateTimeField(blank=True, null=True)

	objects = models.Manager()
	active_objects = ActivePromoManager()

	class Meta:
		ordering = ["-created_at"]

	def __str__(self):
		return f"{self.title} ({self.content_type})"

	def soft_delete(self):
		self.deleted_at = timezone.now()
		self.save(update_fields=["deleted_at", "updated_at"])

	def compute_status(self, on_date=None) -> str:
		return compute_promo_status(
			start_date=self.start_date,
			end_date=self.end_date,
			on_date=on_date,
		)

	def get_default_cta_label(self) -> str:
		return resolve_active_cta_label(
			content_type=self.content_type,
			cta_type=self.cta_type,
			cta_text=self.cta_text,
		)

	def compute_cta_state(self, computed_status: str) -> dict:
		return compute_cta_state(
			posting_state=self.posting_state,
			computed_status=computed_status,
			content_type=self.content_type,
			cta_type=self.cta_type,
			cta_text=self.cta_text,
		)
