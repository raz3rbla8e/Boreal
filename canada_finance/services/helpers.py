import re
from datetime import datetime


def parse_date(raw: str) -> str:
    raw = raw.strip().replace("/", "-")
    for fmt in (
        "%m-%d-%Y", "%Y-%m-%d", "%d-%m-%Y", "%b %d %Y",
        "%B %d %Y", "%d %b %Y", "%Y%m%d",
    ):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    raise ValueError(f"Cannot parse date: {raw!r}")


def safe_abs_float(raw: str) -> float:
    """Parse a numeric string and return its absolute value.

    Sign is stripped intentionally — callers (csv_parser) determine
    debit/credit direction from separate columns.
    """
    cleaned = raw.strip()
    # Normalize Unicode minus signs to ASCII
    cleaned = cleaned.replace("\u2212", "-").replace("\u2013", "-").replace("\u2014", "-")
    cleaned = re.sub(r"[,$\s]", "", cleaned)
    cleaned = cleaned.lstrip("-")
    return float(cleaned) if cleaned else 0.0
