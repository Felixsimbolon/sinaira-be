"""
Booking utility functions.

Includes a WhatsApp chat parser that extracts booking fields from
the Sènaira reservation template without touching the database.
"""

import re
from math import radians, sin, cos, sqrt, atan2

from geopy.exc import GeocoderServiceError, GeocoderTimedOut
from geopy.geocoders import Nominatim
from django.contrib.auth import get_user_model

from therapist.models import Therapist
from therapist.utils import is_therapist_user_available_for_booking

User = get_user_model()


# ──────────────────────────────────────────────────────────────────
# LABELS
# Each key maps to a list of recognised label strings (case-insensitive).
# ──────────────────────────────────────────────────────────────────

_FIELD_LABELS: dict[str, list[str]] = {
    "nama": ["nama"],
    "alamat": ["alamat"],
    "kota": ["kota"],
    "no_hp": ["no. hp", "no hp", "no.hp", "nomor hp", "nomor handphone", "no. handphone"],
    "tgl_treatment": ["tgl treatment", "tgl. treatment", "tanggal treatment", "tanggal"],
    "jam_treatment": ["jam treatment", "jam"],
    "perawatan_pilihan": ["perawatan pilihan", "perawatan"],
    "aromatherapy_oil": [
        "aromatherapy oil pilihan",
        "aromatherapy oil",
        "aromaterapi oil pilihan",
        "aromaterapi oil",
        "aromatherapy",
        "aromaterapi",
    ],
    "kondisi_khusus": [
        "hamil/pasca lahiran/haid/kondisi medis",
        "hamil/pasca lahiran/haid/kondisi",
        "kondisi khusus",
        "kondisi medis",
        "kondisi",
    ],
    "tahu_dari": ["tahu sènaira dari", "tahu senaira dari", "tahu dari"],
}

_AROMATHERAPY_MAP: dict[str, str] = {
    "jasmine": "JASMINE",
    "lavender": "LAVENDER",
    "rose": "ROSE",
    "sandalwood": "SANDALWOOD",
}

# Lines containing any of these tokens signal the start of the Note section
_NOTE_MARKERS = ["note:", "note :", "min. reservasi", "catatan:"]


# ──────────────────────────────────────────────────────────────────
# HELPER FUNCTIONS
# ──────────────────────────────────────────────────────────────────


def sanitize_whatsapp_text(text: str) -> str:
    """
    Remove WhatsApp formatting markers (*bold*, _italic_, ~strikethrough~)
    and collapse excessive whitespace within a single line.
    """
    # Strip bold / italic / strikethrough markers
    text = re.sub(r"[*_~]", "", text)
    # Collapse multiple spaces/tabs into one
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def normalize_phone(phone: str) -> str:
    """
    Normalise a phone-number string:
    - Remove spaces, dashes, parentheses
    - Keep leading 0 as-is
    - Keep leading + sign if present
    """
    phone = re.sub(r"[\s\-().]+", "", phone).strip()
    if not phone:
        return ""
    return phone


def normalize_aromatherapy(value: str) -> str:
    """
    Map a free-text aromatherapy option to one of the canonical values:
    JASMINE | LAVENDER | ROSE | SANDALWOOD

    Returns an empty string if no match is found.
    """
    cleaned = value.lower().strip()
    # Direct match
    if cleaned in _AROMATHERAPY_MAP:
        return _AROMATHERAPY_MAP[cleaned]
    # Partial / substring match (e.g. "Jasmine/Lavender" → only first recognised)
    for key, canonical in _AROMATHERAPY_MAP.items():
        if key in cleaned:
            return canonical
    return ""


# ──────────────────────────────────────────────────────────────────
# PRIVATE PARSING HELPERS
# ──────────────────────────────────────────────────────────────────


def _identify_field(label_text: str) -> str | None:
    """
    Given a sanitised label string, return the matching field key or None.
    Matching is done case-insensitively; longer labels are checked first to
    avoid partial matches (e.g. "no hp" matching before "no. hp").
    """
    label_lower = label_text.lower().strip()
    # Sort candidates longest-first so more specific labels win
    candidates = sorted(
        ((field, lbl) for field, labels in _FIELD_LABELS.items() for lbl in labels),
        key=lambda x: len(x[1]),
        reverse=True,
    )
    for field, lbl in candidates:
        if lbl in label_lower or label_lower == lbl:
            return field
    return None


def _is_note_line(line: str) -> bool:
    """Return True if the line marks the beginning of the Note section."""
    lower = line.lower()
    return any(marker in lower for marker in _NOTE_MARKERS)


def _split_label_value(line: str) -> tuple[str, str]:
    """
    Split a line at the first colon separator.
    Returns (label_part, value_part).  If no colon is found returns ("", line).
    """
    colon_idx = line.find(":")
    if colon_idx == -1:
        return ("", line.strip())
    label = line[:colon_idx]
    value = line[colon_idx + 1:]
    return label.strip(), value.strip()


# ──────────────────────────────────────────────────────────────────
# MAIN EXTRACTOR
# ──────────────────────────────────────────────────────────────────


def extract_booking_from_whatsapp_message(message: str) -> dict:
    """
    Extract booking fields from a Sènaira WhatsApp reservation message.

    Parameters
    ----------
    message : str
        Raw WhatsApp message text (may include formatting markers).

    Returns
    -------
    dict
        ``{
            "nama": str,
            "alamat": str,
            "kota": str,
            "no_hp": str,
            "tgl_treatment": str,
            "jam_treatment": str,
            "perawatan_pilihan": str,
            "aromatherapy_oil": str,
            "kondisi_khusus": str,
            "tahu_dari": str,
        }``
        Empty string for any field not found.
    """
    result: dict[str, str] = {
        "nama": "",
        "alamat": "",
        "kota": "",
        "no_hp": "",
        "tgl_treatment": "",
        "jam_treatment": "",
        "perawatan_pilihan": "",
        "aromatherapy_oil": "",
        "kondisi_khusus": "",
        "tahu_dari": "",
    }

    lines = message.splitlines()

    current_field: str | None = None
    value_parts: list[str] = []

    def _flush(field: str | None, parts: list[str]) -> None:
        """Commit accumulated value parts to result."""
        if field is None:
            return
        joined = " ".join(p for p in parts if p).strip()
        if field == "no_hp":
            joined = normalize_phone(joined)
        elif field == "aromatherapy_oil":
            joined = normalize_aromatherapy(joined)
        if joined:
            result[field] = joined

    for raw_line in lines:
        sanitized = sanitize_whatsapp_text(raw_line)

        # Stop parsing when we hit the Note section
        if _is_note_line(sanitized):
            break

        # Skip empty lines and template header lines (no colon at all and no
        # current field context)
        if not sanitized:
            continue

        # Lines with a colon might introduce a new field
        if ":" in sanitized:
            label_part, value_part = _split_label_value(sanitized)
            detected_field = _identify_field(label_part)

            if detected_field is not None:
                # Flush the previous field before starting a new one
                _flush(current_field, value_parts)
                current_field = detected_field
                value_parts = [value_part] if value_part else []
                continue

        # Lines without a recognised label are continuation lines for the
        # current field (e.g. multi-line alamat) — but only if we already
        # have a current field in context.
        if current_field is not None:
            value_parts.append(sanitized)

    # Flush the last accumulated field
    _flush(current_field, value_parts)

    return result


def _build_address_query(*parts: str) -> str:
    """Build a compact geocoding query from non-empty address parts."""
    return ", ".join(part.strip() for part in parts if part and str(part).strip())


def geocode_location_from_address(
    alamat: str = "",
    kelurahan: str = "",
    kecamatan: str = "",
    kota: str = "",
    country: str = "Indonesia",
) -> tuple[float | None, float | None]:
    """
    Resolve latitude/longitude using OSM Nominatim.

    Lookup order:
    1) Full address query: alamat + kelurahan + kecamatan + kota + country
    2) Fallback query: kelurahan + kota + country
    """
    geolocator = Nominatim(user_agent="senairabe-backend-geocoder")

    full_query = _build_address_query(alamat, kelurahan, kecamatan, kota, country)
    fallback_query = _build_address_query(kelurahan, kota, country)

    for query in [full_query, fallback_query]:
        if not query:
            continue

        try:
            location = geolocator.geocode(query, timeout=10)
        except (GeocoderTimedOut, GeocoderServiceError):
            continue

        if location:
            return location.latitude, location.longitude

    return None, None


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great-circle distance (km) between two latitude/longitude points."""
    radius = 6371.0

    d_lat = radians(lat2 - lat1)
    d_lon = radians(lon2 - lon1)
    a = (
        sin(d_lat / 2) ** 2
        + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lon / 2) ** 2
    )
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return radius * c


def get_distances_to_therapists_in_same_city(booking) -> list[dict]:
    """
    Return sorted distances from a booking to all therapists in the same city.

    Output item format:
    {
        "id": int,
        "name": str,
        "distance_km": float,
    }
    """
    if booking.latitude is None or booking.longitude is None:
        raise ValueError("Booking latitude/longitude is required to calculate therapist distances.")

    therapists = Therapist.objects.filter(kota=booking.kota)
    results: list[dict] = []

    for therapist in therapists:
        if therapist.latitude is None or therapist.longitude is None:
            continue

        distance_km = haversine_distance_km(
            booking.latitude,
            booking.longitude,
            therapist.latitude,
            therapist.longitude,
        )
        results.append(
            {
                "id": therapist.id,
                "name": therapist.name,
                "distance_km": round(distance_km, 2),
            }
        )

    results.sort(key=lambda item: item["distance_km"])
    return results


def get_assignable_therapists_by_distance(booking) -> list[dict]:
    """
    Return sorted therapist candidates by distance for booking assignment.

    Therapist identity is sourced from accounts.User (role=THERAPIST) so that
    returned ids are directly usable by booking assign endpoint.
    Coordinates are sourced from therapist.Therapist profile via username mapping.
    Candidates remain visible even when distance cannot be calculated.
    """
    if booking.latitude is None or booking.longitude is None:
        raise ValueError("Booking latitude/longitude is required to calculate therapist distances.")

    therapist_users = User.objects.filter(role='THERAPIST', is_active=True)
    usernames = [user.username for user in therapist_users]

    profiles = Therapist.objects.filter(username__in=usernames)
    profile_by_username = {profile.username: profile for profile in profiles}

    results: list[dict] = []
    for user in therapist_users:
        profile = profile_by_username.get(user.username)
        distance_km = None
        if (
            profile is not None
            and profile.latitude is not None
            and profile.longitude is not None
        ):
            distance_km = round(
                haversine_distance_km(
                    booking.latitude,
                    booking.longitude,
                    profile.latitude,
                    profile.longitude,
                ),
                2,
            )

        is_available = is_therapist_user_available_for_booking(
            user,
            booking.tgl_treatment,
            booking.jam_treatment,
        )

        results.append(
            {
                "id": user.id,
                "name": user.name,
                "username": user.username,
                "kota": profile.kota if profile else None,
                "kelurahan": profile.kelurahan if profile else None,
                "kecamatan": profile.kecamatan if profile else None,
                "distance_km": distance_km,
                "is_available": is_available,
                "availability_label": "Tersedia" if is_available else "Jadwal tidak tersedia",
                "availability_reason": (
                    None
                    if is_available
                    else "Therapist tidak tersedia pada jam booking."
                ),
            }
        )

    results.sort(
        key=lambda item: (
            item["distance_km"] is None,
            item["distance_km"] if item["distance_km"] is not None else 0,
        )
    )
    return results
