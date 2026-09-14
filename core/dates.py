"""Parse dates typed by staff (ISO or dd.mm.yyyy)."""

from datetime import date, datetime

MIN_YEAR = 1900
MAX_YEAR = 2100


def parse_user_date(value: str | None) -> date | None:
    value = (value or "").strip()
    if not value:
        return None
    parsed = None
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        for fmt in ("%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y"):
            try:
                parsed = datetime.strptime(value, fmt).date()
                break
            except ValueError:
                continue
    if parsed is None:
        return None
    if parsed.year < MIN_YEAR or parsed.year > MAX_YEAR:
        return None
    return parsed
