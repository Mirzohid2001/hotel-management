from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from core.tests.helpers import setup_tenant_user


def _png():
    return SimpleUploadedFile(
        "logo.png",
        (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
            b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
            b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
            b"\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
        ),
        content_type="image/png",
    )


class TenantLogoTests(TestCase):
    def setUp(self):
        self.ctx = setup_tenant_user(username="logo-staff")
        self.client.force_login(self.ctx["user"])

    def test_default_logo_when_empty(self):
        resp = self.client.get(reverse("accounts:profile"))
        self.assertContains(resp, "img/rivoj-logo.png")
        self.assertNotContains(resp, "brand-logo is-custom")

    def test_custom_logo_replaces_rivoj(self):
        tenant = self.ctx["tenant"]
        tenant.logo = _png()
        tenant.save()
        resp = self.client.get(reverse("accounts:profile"))
        self.assertContains(resp, "brand-logo is-custom")
        self.assertContains(resp, tenant.logo.url)
        self.assertNotContains(resp, "img/rivoj-logo.png")
