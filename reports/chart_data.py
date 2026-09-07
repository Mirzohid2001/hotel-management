"""Chart.js uchun JSON-serializable ma'lumotlar."""

from datetime import date, timedelta
from decimal import Decimal

from django.utils.translation import gettext as _

from .operations import occupancy_stats, revenue_trend, room_status_summary


def _f(value) -> float:
    if isinstance(value, Decimal):
        return float(value)
    return float(value or 0)


def occupancy_trend(tenant, end_day: date, *, days: int = 7, hotel=None) -> list[dict]:
    start = end_day - timedelta(days=days - 1)
    rows = []
    for i in range(days):
        d = start + timedelta(days=i)
        stats = occupancy_stats(tenant, d, hotel=hotel)
        rows.append(
            {
                "label": d.strftime("%d.%m"),
                "pct": _f(stats["occupancy_percent"]),
                "is_today": d == end_day,
            }
        )
    return rows


def dashboard_charts(tenant, day: date, *, hotel=None, currency: str = "UZS") -> dict:
    trend = revenue_trend(tenant, day, hotel=hotel)
    occ = occupancy_trend(tenant, day, hotel=hotel)
    rooms = room_status_summary(tenant, hotel=hotel)
    active_rooms = [r for r in rooms if r["count"]]
    return {
        "currency": currency,
        "revenueTrend": {
            "labels": [r["label"] for r in trend],
            "revenue": [_f(r["amount"]) for r in trend],
            "occupancy": [r["pct"] for r in occ],
        },
        "roomStatus": {
            "labels": [r["label"] for r in active_rooms],
            "values": [r["count"] for r in active_rooms],
            "statuses": [r["status"] for r in active_rooms],
        },
    }


def pnl_charts(report: dict, *, currency: str = "UZS") -> dict:
    revenue_rows = report.get("revenue_breakdown") or []
    expense_rows = report.get("expenses_breakdown") or []
    return {
        "currency": currency,
        "revenueDonut": {
            "labels": [r["label"] for r in revenue_rows],
            "values": [_f(r["amount"]) for r in revenue_rows],
        },
        "expenseDonut": {
            "labels": [r["label"] for r in expense_rows],
            "values": [_f(r["amount"]) for r in expense_rows],
        },
        "summaryBar": {
            "labels": [
                _("Tushum"),
                _("Rasxod"),
                _("Oylik"),
                _("Avans"),
                _("Komissiya"),
                _("Ombor"),
                _("E-mehmon farq"),
                _("Sof"),
            ],
            "values": [
                _f(report.get("revenue_total")),
                _f(report.get("expenses_total")),
                _f(report.get("payroll")),
                _f(report.get("advances")),
                _f(report.get("commission")),
                _f(report.get("inventory_cost")),
                _f(report.get("emehmon_shortfall")),
                _f(report.get("net")),
            ],
        },
    }


def flash_charts(flash: dict, *, currency: str = "UZS") -> dict:
    payment_rows = flash.get("payments", {}).get("rows") or []
    guest_rows = (flash.get("guest_ar") or {}).get("rows") or []
    mtd = flash.get("mtd") or {}
    return {
        "currency": currency,
        "paymentMethods": {
            "labels": [r["label"] for r in payment_rows],
            "in": [_f(r["in"]) for r in payment_rows],
            "out": [_f(r["out"]) for r in payment_rows],
        },
        "revenueDay": {
            "labels": [_("Naqd tushum"), _("Hisoblangan"), _("Rasxod")],
            "values": [
                _f(flash.get("revenue_cash")),
                _f(flash.get("revenue_accrual")),
                _f(flash.get("expenses_today")),
            ],
        },
        "mtdBar": {
            "labels": [_("Tushum"), _("Xarajat"), _("Sof")],
            "values": [
                _f(mtd.get("revenue")),
                _f(mtd.get("operating_costs") or (
                    (mtd.get("expenses") or 0)
                    + (mtd.get("payroll") or 0)
                    + (mtd.get("advances") or 0)
                    + (mtd.get("commission") or 0)
                    + (mtd.get("inventory_cost") or 0)
                )),
                _f(mtd.get("net")),
            ],
        },
        "guestAr": {
            "labels": [r["code"] for r in guest_rows[:8]],
            "values": [_f(r["balance"]) for r in guest_rows[:8]],
        },
    }


def cash_shift_charts(report: dict | None, history_rows: list[dict], *, currency: str = "UZS") -> dict:
    data: dict = {"currency": currency}
    if report:
        payments = report["payments"]
        shift = report["shift"]
        cash_out = report["cash_out"]
        data["paymentMix"] = {
            "labels": [_("Naqd"), _("Karta"), _("O'tkazish")],
            "values": [
                _f(payments["cash_in"]),
                _f(payments["card_total"]),
                _f(payments.get("transfer_total")),
            ],
        }
        movements = report.get("movements") or {}
        data["cashFlow"] = {
            "labels": [
                _("Boshlang'ich"),
                _("Naqd kirim"),
                _("Kassa kirim"),
                _("Chiqim"),
                _("Kutilgan"),
            ],
            "values": [
                _f(shift.opening_float),
                _f(payments["cash_in"]),
                _f(movements.get("pay_in")),
                -(_f(cash_out["total"]) + _f(movements.get("pay_out"))),
                _f(report["expected_cash"]),
            ],
        }
    if history_rows:
        data["varianceHistory"] = {
            "labels": [r["label"] for r in history_rows],
            "values": [_f(r["variance"]) for r in history_rows],
        }
    return data
