from django.test import TestCase

from core.models import ActivityLog, log_activity
from core.tests.helpers import setup_tenant_user


class ActivityLogTests(TestCase):
    def test_log_activity(self):
        ctx = setup_tenant_user(username="loguser")
        entry = log_activity(
            tenant=ctx["tenant"],
            user=ctx["user"],
            action="test.create",
            model="Tenant",
            object_id=ctx["tenant"].pk,
            payload={"ok": True},
        )
        self.assertEqual(ActivityLog.objects.count(), 1)
        self.assertEqual(entry.payload["ok"], True)
