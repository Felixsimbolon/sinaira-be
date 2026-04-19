import random
from collections import Counter

from django.db.models import Count
from django.utils import timezone

from booking.models import Booking
from layanan.models import Layanan

from .models import Promo
from .repositories import PromoRepository

MIN_REPEATING_COMPLETED_BOOKINGS = 3
MAX_FAVORITE_LAYANAN_PER_CUSTOMER = 3
FALLBACK_PROMO_SUGGESTION_COUNT = 2

# Treat a booking as "treatment delivered" once the customer has been checked out.
# This covers both CHECKED_OUT (treatment finished, admin hasn't promoted yet) and
# COMPLETED (fully closed). Keeping both avoids missing repeating customers just
# because staff haven't flipped CHECKED_OUT → COMPLETED.
TREATMENT_DELIVERED_STATUSES = (
    Booking.BookingStatus.CHECKED_OUT,
    Booking.BookingStatus.COMPLETED,
)


class PromoService:
    """Service layer for promo/event business workflow."""

    def __init__(self, repository: PromoRepository | None = None):
        self.repository = repository or PromoRepository()

    def create_promo(self, *, validated_data: dict, user) -> Promo:
        applicable_services = validated_data.pop("applicable_services", None)
        now = timezone.now()
        promo = self.repository.create(
            **validated_data,
            created_by=user,
            updated_by=user,
            created_at=now,
            updated_at=now,
        )
        if applicable_services is not None:
            promo.applicable_services.set(applicable_services)
        return promo

    def update_promo(self, *, promo: Promo, validated_data: dict, user) -> Promo:
        applicable_services = validated_data.pop("applicable_services", None)
        for key, value in validated_data.items():
            setattr(promo, key, value)
        promo.updated_by = user
        self.repository.save(promo)
        if applicable_services is not None:
            promo.applicable_services.set(applicable_services)
        return promo

    def archive_promo(self, *, promo: Promo, user) -> Promo:
        promo.posting_state = Promo.PostingState.ARCHIVED
        promo.updated_by = user
        self.repository.save(promo, update_fields=["posting_state", "updated_by", "updated_at"])
        return promo

    def unarchive_promo(self, *, promo: Promo, user) -> Promo:
        promo.posting_state = Promo.PostingState.DRAFT
        promo.updated_by = user
        self.repository.save(promo, update_fields=["posting_state", "updated_by", "updated_at"])
        return promo

    def soft_delete(self, *, promo: Promo, user) -> Promo:
        promo.updated_by = user
        promo.deleted_at = timezone.now()
        self.repository.save(promo, update_fields=["updated_by", "deleted_at", "updated_at"])
        return promo


def _split_layanan_names(perawatan_pilihan: str) -> list[str]:
    if not perawatan_pilihan:
        return []
    return [part.strip() for part in perawatan_pilihan.split(",") if part.strip()]


def _promo_is_active_today(promo: Promo, today) -> bool:
    """A promo is 'active' when it's published AND its date window (if any) covers today."""
    if promo.deleted_at is not None:
        return False
    if promo.posting_state != Promo.PostingState.PUBLISHED:
        return False
    if promo.start_date and today < promo.start_date:
        return False
    if promo.end_date and today > promo.end_date:
        return False
    return True


def _match_promos_to_favorites(active_promos: list[Promo], favorite_names: list[str]) -> list[Promo]:
    """Return promos whose title or description contains any favorite layanan name (case-insensitive)."""
    if not favorite_names:
        return []
    lowered_favorites = [name.lower() for name in favorite_names if name]
    matched: list[Promo] = []
    for promo in active_promos:
        haystack = f"{promo.title} {promo.description}".lower()
        if any(fav in haystack for fav in lowered_favorites):
            matched.append(promo)
    return matched


def build_promo_recommendations() -> list[dict]:
    """
    Build personalized promo recommendations for repeating customers.

    A repeating customer is a `no_hp` with ≥ MIN_REPEATING_COMPLETED_BOOKINGS completed bookings.
    Their favorite layanan are the most-frequent layanan names parsed from `perawatan_pilihan`
    across their completed bookings. Recommended promos are active (published AND within date
    window) promos whose title/description mention any favorite layanan.
    """
    repeating_groups = list(
        Booking.objects.filter(status__in=TREATMENT_DELIVERED_STATUSES)
        .values("no_hp")
        .annotate(total=Count("id"))
        .filter(total__gte=MIN_REPEATING_COMPLETED_BOOKINGS, no_hp__isnull=False)
        .exclude(no_hp="")
        .order_by("-total", "no_hp")
    )

    if not repeating_groups:
        return []

    repeating_phones = [row["no_hp"] for row in repeating_groups]

    completed_bookings = (
        Booking.objects.filter(
            no_hp__in=repeating_phones,
            status__in=TREATMENT_DELIVERED_STATUSES,
        )
        .only("id", "no_hp", "nama", "booking_id", "perawatan_pilihan", "tgl_treatment", "jam_treatment")
    )

    bookings_by_phone: dict[str, list[Booking]] = {}
    for booking in completed_bookings:
        bookings_by_phone.setdefault(booking.no_hp, []).append(booking)

    known_layanan_names = set(
        Layanan.active_objects.filter(is_active=True).values_list("nama", flat=True)
    )

    today = timezone.localdate()
    published_promos = list(
        Promo.active_objects.filter(posting_state=Promo.PostingState.PUBLISHED)
    )
    active_promos = [promo for promo in published_promos if _promo_is_active_today(promo, today)]

    # Fallback pool includes currently-active promos first, then upcoming/scheduled ones
    # (published but end_date still in the future or missing). Expired promos are excluded.
    def _fallback_candidate(promo: Promo) -> bool:
        if promo.end_date and promo.end_date < today:
            return False
        return True

    fallback_promos = active_promos or [
        promo for promo in published_promos if _fallback_candidate(promo)
    ]

    results: list[dict] = []
    for row in repeating_groups:
        phone = row["no_hp"]
        total = row["total"]
        customer_bookings = bookings_by_phone.get(phone, [])
        if not customer_bookings:
            continue

        latest = max(
            customer_bookings,
            key=lambda b: (b.tgl_treatment or timezone.localdate(), b.jam_treatment or timezone.now().time()),
        )

        name_counter: Counter[str] = Counter()
        for booking in customer_bookings:
            for name in _split_layanan_names(booking.perawatan_pilihan):
                if not known_layanan_names or name in known_layanan_names:
                    name_counter[name] += 1

        favorite_layanan_names = [
            name for name, _count in name_counter.most_common(MAX_FAVORITE_LAYANAN_PER_CUSTOMER)
        ]

        matched_promos = _match_promos_to_favorites(active_promos, favorite_layanan_names)
        is_fallback = False

        # Fallback: when no layanan-specific match is found, still suggest a few random
        # promos/events that are published and not yet expired so the admin always has
        # *something* to send over WhatsApp.
        if not matched_promos and fallback_promos:
            sample_size = min(FALLBACK_PROMO_SUGGESTION_COUNT, len(fallback_promos))
            matched_promos = random.sample(fallback_promos, sample_size)
            is_fallback = True

        results.append(
            {
                "customerId": latest.booking_id,
                "namaCustomer": latest.nama,
                "nomorTelepon": phone,
                "totalBooking": total,
                "layananFavorit": favorite_layanan_names,
                "rekomendasiPromo": [
                    {
                        "id": promo.id,
                        "title": promo.title,
                        "deskripsi": promo.description,
                        "contentType": promo.content_type,
                    }
                    for promo in matched_promos
                ],
                "rekomendasiType": "fallback" if is_fallback else "personalized",
            }
        )

    return results
