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


def safe_float(raw: str) -> float:
    cleaned = re.sub(r"[,$\s]", "", raw.strip())
    cleaned = cleaned.lstrip("-")  # remove sign, we handle direction separately
    return float(cleaned) if cleaned else 0.0
