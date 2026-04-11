from django.utils import timezone


def compute_promo_status(*, start_date, end_date, on_date=None) -> str:
    """Compute promo status by date window."""
    current_date = on_date or timezone.localdate()

    if start_date and current_date < start_date:
        return "scheduled"
    if end_date and current_date > end_date:
        return "expired"
    return "active"


def resolve_active_cta_label(*, content_type: str, cta_type: str, cta_text: str | None) -> str:
    if cta_type == "custom" and cta_text:
        return cta_text
    if cta_type == "register":
        return "Register"
    if cta_type == "claim":
        return "Claim"
    if cta_type == "use":
        return "Use Now"

    if content_type == "event":
        return "Register"
    return "Use Now"


def compute_cta_state(*, posting_state: str, computed_status: str, content_type: str, cta_type: str, cta_text: str | None) -> dict:
    """Compute CTA enablement and label based on workflow and date status."""
    if posting_state != "published":
        return {
            "cta_enabled": False,
            "cta_label": "Closed",
            "availability_status": "closed",
        }

    if computed_status == "scheduled":
        return {
            "cta_enabled": False,
            "cta_label": "Coming Soon",
            "availability_status": "coming_soon",
        }

    if computed_status == "expired":
        expired_label = "Registration Closed" if content_type == "event" else "Expired"
        return {
            "cta_enabled": False,
            "cta_label": expired_label,
            "availability_status": "closed",
        }

    return {
        "cta_enabled": True,
        "cta_label": resolve_active_cta_label(
            content_type=content_type,
            cta_type=cta_type,
            cta_text=cta_text,
        ),
        "availability_status": "available",
    }
