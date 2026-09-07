"""Markaziy bank (CBU) kurslari — mock bilan, tarmoqsiz."""

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.cbu import (
    CBUFetchError,
    ensure_today_cbu_rates,
    expected_cbu_business_day,
    fetch_cbu_rates_to_uzs,
    has_fresh_cbu_rates,
    rates_for_base,
    sync_cbu_rates_all_tenants,
    sync_cbu_rates_for_tenant,
)
from core.tests.helpers import setup_tenant_user
from subscriptions.models import Plan
from tenants.models import ExchangeRate, Tenant


def _cbu_payload(day=None, usd="12750.25", eur="13820.50"):
    day = day or timezone.localdate()
    d = day.strftime("%d.%m.%Y")
    return [
        {"Ccy": "USD", "Nominal": "1", "Rate": usd, "Date": d},
        {"Ccy": "EUR", "Nominal": "1", "Rate": eur, "Date": d},
        {"Ccy": "RUB", "Nominal": "1", "Rate": "140.00", "Date": d},
    ]


class CBURatesServiceTests(TestCase):
    def setUp(self):
        self.ctx = setup_tenant_user(plan_code=Plan.Code.PRO, username="cbu")
        self.tenant = self.ctx["tenant"]
        self.tenant.currency = "UZS"
        self.tenant.save(update_fields=["currency"])
        self.today = timezone.localdate()

    def test_expected_business_day_rolls_weekend(self):
        # 2026-09-06 = Sunday → Friday 2026-09-04
        self.assertEqual(expected_cbu_business_day(date(2026, 9, 6)), date(2026, 9, 4))
        self.assertEqual(expected_cbu_business_day(date(2026, 9, 5)), date(2026, 9, 4))
        self.assertEqual(expected_cbu_business_day(date(2026, 9, 4)), date(2026, 9, 4))
        self.assertEqual(expected_cbu_business_day(date(2026, 9, 7)), date(2026, 9, 7))

    @patch("core.cbu._http_get_json")
    def test_fetch_parses_usd_eur(self, mock_get):
        mock_get.return_value = _cbu_payload(self.today)
        data = fetch_cbu_rates_to_uzs()
        self.assertEqual(data["USD"]["rate"], Decimal("12750.250000"))
        self.assertEqual(data["EUR"]["rate"], Decimal("13820.500000"))
        self.assertEqual(data["USD"]["effective_on"], self.today)
        self.assertNotIn("RUB", data)

    def test_rates_for_usd_base_cross(self):
        cbu = {
            "USD": {"rate": Decimal("10000"), "effective_on": self.today},
            "EUR": {"rate": Decimal("11000"), "effective_on": self.today},
        }
        mapped = rates_for_base("USD", cbu)
        self.assertEqual(mapped["UZS"], Decimal("0.000100"))
        self.assertEqual(mapped["EUR"], Decimal("1.100000"))

    def test_rates_for_eur_base(self):
        cbu = {
            "USD": {"rate": Decimal("10000"), "effective_on": self.today},
            "EUR": {"rate": Decimal("12000"), "effective_on": self.today},
        }
        mapped = rates_for_base("EUR", cbu)
        self.assertEqual(mapped["UZS"], (Decimal("1") / Decimal("12000")).quantize(Decimal("0.000001")))
        self.assertEqual(mapped["USD"], (Decimal("10000") / Decimal("12000")).quantize(Decimal("0.000001")))

    @patch("core.cbu._http_get_json")
    def test_sync_creates_exchange_rates(self, mock_get):
        mock_get.return_value = _cbu_payload(self.today, usd="12000", eur="13000")
        info = sync_cbu_rates_for_tenant(self.tenant)
        self.assertEqual(sorted(info["created"]), ["EUR", "USD"])
        usd = ExchangeRate.objects.get(
            tenant=self.tenant, currency="USD", effective_on=self.today
        )
        self.assertEqual(usd.rate, Decimal("12000.000000"))
        self.assertIn("CBU", usd.note)

    @patch("core.cbu._http_get_json")
    def test_sync_usd_base_tenant(self, mock_get):
        self.tenant.currency = "USD"
        self.tenant.save(update_fields=["currency"])
        mock_get.return_value = _cbu_payload(self.today, usd="10000", eur="11000")
        info = sync_cbu_rates_for_tenant(self.tenant)
        self.assertEqual(info["base_currency"], "USD")
        uzs = ExchangeRate.objects.get(tenant=self.tenant, currency="UZS")
        eur = ExchangeRate.objects.get(tenant=self.tenant, currency="EUR")
        self.assertEqual(uzs.rate, Decimal("0.000100"))
        self.assertEqual(eur.rate, Decimal("1.100000"))

    @patch("core.cbu._http_get_json")
    def test_sync_skips_without_force(self, mock_get):
        mock_get.return_value = _cbu_payload(self.today)
        sync_cbu_rates_for_tenant(self.tenant)
        info = sync_cbu_rates_for_tenant(self.tenant, force=False)
        self.assertEqual(sorted(info["skipped"]), ["EUR", "USD"])
        self.assertEqual(info["created"], [])

    @patch("core.cbu._http_get_json")
    def test_sync_force_overwrites_manual(self, mock_get):
        ExchangeRate.objects.create(
            tenant=self.tenant,
            currency="USD",
            base_currency="UZS",
            rate=Decimal("1"),
            effective_on=self.today,
            note="qo‘lda",
        )
        mock_get.return_value = _cbu_payload(self.today, usd="15000", eur="16000")
        info = sync_cbu_rates_for_tenant(self.tenant, force=True)
        self.assertIn("USD", info["updated"])
        usd = ExchangeRate.objects.get(
            tenant=self.tenant, currency="USD", effective_on=self.today
        )
        self.assertEqual(usd.rate, Decimal("15000.000000"))
        self.assertIn("CBU", usd.note)

    @patch("core.cbu._http_get_json")
    def test_sync_all_tenants_one_http_call(self, mock_get):
        other = Tenant.objects.create(name="Other CBU", is_active=True, currency="UZS")
        mock_get.return_value = _cbu_payload(self.today)
        results = sync_cbu_rates_all_tenants()
        self.assertEqual(mock_get.call_count, 1)
        ok = [r for r in results if r.get("ok")]
        self.assertGreaterEqual(len(ok), 2)
        self.assertTrue(
            ExchangeRate.objects.filter(tenant=other, currency="USD").exists()
        )

    @patch("core.cbu._http_get_json")
    def test_ensure_today_fetches_once(self, mock_get):
        mock_get.return_value = _cbu_payload(self.today)
        first = ensure_today_cbu_rates(self.tenant)
        self.assertIsNotNone(first)
        self.assertEqual(mock_get.call_count, 1)
        second = ensure_today_cbu_rates(self.tenant)
        self.assertIsNone(second)
        self.assertEqual(mock_get.call_count, 1)

    @patch("core.cbu._http_get_json")
    def test_ensure_respects_weekend_cbu_date(self, mock_get):
        """Yakshanba: juma CBU kursi yetarli — qayta so‘rov yo‘q."""
        sunday = date(2026, 9, 6)
        friday = date(2026, 9, 4)
        mock_get.return_value = _cbu_payload(friday)
        with patch("core.cbu.timezone.localdate", return_value=sunday):
            ensure_today_cbu_rates(self.tenant)
            self.assertEqual(mock_get.call_count, 1)
            again = ensure_today_cbu_rates(self.tenant)
            self.assertIsNone(again)
            self.assertEqual(mock_get.call_count, 1)
            self.assertTrue(has_fresh_cbu_rates(self.tenant))

    @patch("core.cbu._http_get_json")
    def test_ensure_refetches_on_monday_after_friday(self, mock_get):
        """Dushanba: juma kursi eskirgan — yangi CBU so‘rovi."""
        friday = date(2026, 9, 4)
        monday = date(2026, 9, 7)
        ExchangeRate.objects.create(
            tenant=self.tenant,
            currency="USD",
            base_currency="UZS",
            rate=Decimal("11795"),
            effective_on=friday,
            note="Markaziy bank (CBU) · avtomatik",
        )
        ExchangeRate.objects.create(
            tenant=self.tenant,
            currency="EUR",
            base_currency="UZS",
            rate=Decimal("13698.71"),
            effective_on=friday,
            note="Markaziy bank (CBU) · avtomatik",
        )
        mock_get.return_value = _cbu_payload(monday, usd="11800", eur="13700")
        with patch("core.cbu.timezone.localdate", return_value=monday):
            self.assertFalse(has_fresh_cbu_rates(self.tenant))
            info = ensure_today_cbu_rates(self.tenant)
            self.assertIsNotNone(info)
            self.assertEqual(mock_get.call_count, 1)
            self.assertTrue(
                ExchangeRate.objects.filter(
                    tenant=self.tenant, currency="USD", effective_on=monday
                ).exists()
            )

    @patch("core.cbu._http_get_json")
    def test_ensure_marks_checked_when_cbu_date_unchanged(self, mock_get):
        """Dushanba ertalab CBU hali jumani bersa — kuniga bir marta so‘rov."""
        from datetime import datetime as dt

        friday = date(2026, 9, 4)
        monday = date(2026, 9, 7)
        monday_noon = timezone.make_aware(dt(2026, 9, 7, 12, 0, 0))
        ExchangeRate.objects.create(
            tenant=self.tenant,
            currency="USD",
            base_currency="UZS",
            rate=Decimal("11795"),
            effective_on=friday,
            note="Markaziy bank (CBU) · avtomatik",
        )
        ExchangeRate.objects.create(
            tenant=self.tenant,
            currency="EUR",
            base_currency="UZS",
            rate=Decimal("13698.71"),
            effective_on=friday,
            note="Markaziy bank (CBU) · avtomatik",
        )
        mock_get.return_value = _cbu_payload(friday)
        with patch("core.cbu.timezone.localdate", return_value=monday):
            with patch("core.cbu.timezone.now", return_value=monday_noon):
                first = ensure_today_cbu_rates(self.tenant)
                self.assertIsNotNone(first)
                self.assertEqual(sorted(first["skipped"]), ["EUR", "USD"])
                self.assertEqual(mock_get.call_count, 1)
                second = ensure_today_cbu_rates(self.tenant)
                self.assertIsNone(second)
                self.assertEqual(mock_get.call_count, 1)

    @patch("core.cbu._http_get_json")
    def test_fetch_error_empty(self, mock_get):
        mock_get.return_value = [
            {"Ccy": "RUB", "Rate": "1", "Nominal": "1", "Date": "01.01.2026"}
        ]
        with self.assertRaises(CBUFetchError):
            fetch_cbu_rates_to_uzs()

    @patch("core.cbu._http_get_json")
    def test_management_command(self, mock_get):
        mock_get.return_value = _cbu_payload(self.today)
        call_command("fetch_cbu_rates", tenant=str(self.tenant.pk))
        self.assertTrue(
            ExchangeRate.objects.filter(
                tenant=self.tenant, currency="USD", note__icontains="CBU"
            ).exists()
        )

    @patch("core.cbu._http_get_json")
    def test_synced_rate_used_by_get_rate_to_base(self, mock_get):
        from core.currency import get_rate_to_base

        mock_get.return_value = _cbu_payload(self.today, usd="11999.50", eur="13000")
        sync_cbu_rates_for_tenant(self.tenant)
        self.assertEqual(
            get_rate_to_base(self.tenant, "USD", on_date=self.today),
            Decimal("11999.500000"),
        )


class CBUExchangeRatesViewTests(TestCase):
    def setUp(self):
        self.ctx = setup_tenant_user(plan_code=Plan.Code.PRO, username="cbuview")
        self.tenant = self.ctx["tenant"]
        self.user = self.ctx["user"]
        self.tenant.currency = "UZS"
        self.tenant.save(update_fields=["currency"])
        self.client.force_login(self.user)
        self.url = reverse("finance:exchange_rates")

    @patch("core.cbu._http_get_json")
    def test_get_auto_syncs(self, mock_get):
        mock_get.return_value = _cbu_payload()
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(
            ExchangeRate.objects.filter(tenant=self.tenant, currency="USD").exists()
        )
        self.assertContains(resp, "Markaziy bank")

    @patch("core.cbu._http_get_json")
    def test_post_cbu_force(self, mock_get):
        mock_get.return_value = _cbu_payload(usd="11111", eur="22222")
        ExchangeRate.objects.create(
            tenant=self.tenant,
            currency="USD",
            base_currency="UZS",
            rate=Decimal("10000"),
            effective_on=timezone.localdate(),
            note="qo‘lda",
        )
        resp = self.client.post(self.url, {"form": "cbu"})
        self.assertEqual(resp.status_code, 302)
        usd = ExchangeRate.objects.get(
            tenant=self.tenant, currency="USD", effective_on=timezone.localdate()
        )
        self.assertEqual(usd.rate, Decimal("11111.000000"))
        self.assertIn("CBU", usd.note)

    @patch("core.cbu._http_get_json")
    def test_get_does_not_refetch_when_fresh(self, mock_get):
        mock_get.return_value = _cbu_payload()
        self.client.get(self.url)
        n = mock_get.call_count
        self.client.get(self.url)
        self.assertEqual(mock_get.call_count, n)
