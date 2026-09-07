from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()


def _to_decimal(value):
    if value is None or value == "":
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


@register.filter(name="money")
def money(value, places=None):
    """
    Format numbers for easy reading: 4500000 -> 4 500 000
    Optional places: {{ x|money:0 }} or {{ x|money:2 }}
    """
    num = _to_decimal(value)
    if num is None:
        return value

    if places is None:
        # Hide .00 for whole amounts; keep decimals otherwise
        if num == num.to_integral_value():
            places = 0
        else:
            places = 2
    else:
        try:
            places = int(places)
        except (TypeError, ValueError):
            places = 2

    q = Decimal("1") if places == 0 else Decimal("0." + "0" * (places - 1) + "1")
    num = num.quantize(q)

    sign = "-" if num < 0 else ""
    num = abs(num)
    as_str = f"{num:.{places}f}"
    if "." in as_str:
        whole, frac = as_str.split(".", 1)
    else:
        whole, frac = as_str, ""

    groups = []
    while whole:
        groups.append(whole[-3:])
        whole = whole[:-3]
    whole_fmt = " ".join(reversed(groups))
    if frac and places > 0:
        return f"{sign}{whole_fmt}.{frac}"
    return f"{sign}{whole_fmt}"


@register.filter(name="money_uzs")
def money_uzs(value):
    """Alias: whole amounts with spaces."""
    return money(value, 0)
