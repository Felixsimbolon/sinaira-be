from django.db.models import QuerySet

from .models import Promo


class PromoRepository:
    """Repository layer for Promo persistence and query composition."""

    def admin_queryset(self) -> QuerySet[Promo]:
        return Promo.active_objects.select_related("created_by", "updated_by")

    def public_queryset(self) -> QuerySet[Promo]:
        return Promo.active_objects.filter(posting_state=Promo.PostingState.PUBLISHED)

    def get_admin_by_id(self, pk: int) -> Promo:
        return self.admin_queryset().get(pk=pk)

    def get_public_by_id(self, pk: int) -> Promo:
        return self.public_queryset().get(pk=pk)

    def create(self, **kwargs) -> Promo:
        return Promo.objects.create(**kwargs)

    def save(self, promo: Promo, update_fields=None):
        if update_fields is None:
            promo.save()
        else:
            promo.save(update_fields=update_fields)
        return promo
