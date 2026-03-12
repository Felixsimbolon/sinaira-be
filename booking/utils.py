"""
Booking utility functions.

Includes a WhatsApp chat parser that extracts booking fields from
the Sènaira reservation template without touching the database.
"""

import re


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
    - Convert leading 0 to +62 (Indonesian convention)
    - Keep leading + sign if present, otherwise keep digits only
    """
    phone = re.sub(r"[\s\-().]+", "", phone).strip()
    if not phone:
        return ""
    if phone.startswith("0"):
        phone = "+62" + phone[1:]
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
