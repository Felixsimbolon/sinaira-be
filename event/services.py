from django.utils import timezone

from .models import Promo
from .repositories import PromoRepository


class PromoService:
    """Service layer for promo/event business workflow."""

    def __init__(self, repository: PromoRepository | None = None):
        self.repository = repository or PromoRepository()

    def create_promo(self, *, validated_data: dict, user) -> Promo:
        now = timezone.now()
        return self.repository.create(
            **validated_data,
            created_by=user,
            updated_by=user,
            created_at=now,
            updated_at=now,
        )

    def update_promo(self, *, promo: Promo, validated_data: dict, user) -> Promo:
        for key, value in validated_data.items():
            setattr(promo, key, value)
        promo.updated_by = user
        self.repository.save(promo)
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
