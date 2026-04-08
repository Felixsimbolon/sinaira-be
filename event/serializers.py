from rest_framework import serializers

from .models import Promo


class PromoWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Promo
        fields = [
            "title",
            "description",
            "image",
            "external_link",
            "start_date",
            "end_date",
            "content_type",
            "posting_state",
            "cta_type",
            "cta_text",
        ]
        extra_kwargs = {
            "title": {"required": True},
            "description": {"required": True},
            "image": {"required": False, "allow_null": True, "allow_blank": True},
            "external_link": {"required": False, "allow_null": True, "allow_blank": True},
            "start_date": {"required": False, "allow_null": True},
            "end_date": {"required": False, "allow_null": True},
            "content_type": {"required": False},
            "posting_state": {"required": False},
            "cta_type": {"required": False},
            "cta_text": {"required": False, "allow_null": True, "allow_blank": True},
        }

    def validate(self, attrs):
        start_date = attrs.get("start_date")
        end_date = attrs.get("end_date")

        # Keep old dates on partial updates for validation continuity.
        instance = getattr(self, "instance", None)
        if instance is not None:
            start_date = start_date if "start_date" in attrs else instance.start_date
            end_date = end_date if "end_date" in attrs else instance.end_date

        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError(
                {"end_date": "end_date harus sama atau lebih besar dari start_date."}
            )

        cta_type = attrs.get("cta_type")
        cta_text = attrs.get("cta_text")
        if cta_type == Promo.CtaType.CUSTOM and not cta_text:
            raise serializers.ValidationError(
                {"cta_text": "cta_text wajib diisi jika cta_type adalah custom."}
            )

        return attrs


class PromoReadSerializer(serializers.ModelSerializer):
    computed_status = serializers.SerializerMethodField()
    cta_enabled = serializers.SerializerMethodField()
    cta_label = serializers.SerializerMethodField()
    availability_status = serializers.SerializerMethodField()
    period = serializers.SerializerMethodField()

    class Meta:
        model = Promo
        fields = [
            "id",
            "title",
            "description",
            "image",
            "external_link",
            "content_type",
            "posting_state",
            "start_date",
            "end_date",
            "period",
            "computed_status",
            "cta_enabled",
            "cta_label",
            "availability_status",
            "created_at",
            "updated_at",
        ]

    def _cta_state(self, obj: Promo):
        return obj.compute_cta_state(obj.compute_status())

    def get_computed_status(self, obj: Promo):
        return obj.compute_status()

    def get_cta_enabled(self, obj: Promo):
        return self._cta_state(obj)["cta_enabled"]

    def get_cta_label(self, obj: Promo):
        return self._cta_state(obj)["cta_label"]

    def get_availability_status(self, obj: Promo):
        return self._cta_state(obj)["availability_status"]

    def get_period(self, obj: Promo):
        if not obj.start_date and not obj.end_date:
            return None
        return {
            "start_date": obj.start_date,
            "end_date": obj.end_date,
        }


class PromoAdminListSerializer(PromoReadSerializer):
    action = serializers.SerializerMethodField()

    class Meta(PromoReadSerializer.Meta):
        fields = PromoReadSerializer.Meta.fields + ["action"]

    def get_action(self, obj: Promo):
        return {
            "can_edit": obj.deleted_at is None,
            "can_archive": obj.posting_state != Promo.PostingState.ARCHIVED and obj.deleted_at is None,
            "can_unarchive": obj.posting_state == Promo.PostingState.ARCHIVED and obj.deleted_at is None,
            "can_delete": obj.deleted_at is None,
        }
