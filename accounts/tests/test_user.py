from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.models import User

UserModel = get_user_model()


class UserModelTests(TestCase):
    def test_custom_user_with_phone(self):
        user = UserModel.objects.create_user(
            username="ali", password="pass12345", phone="+998901112233"
        )
        self.assertEqual(user.phone, "+998901112233")
        self.assertTrue(isinstance(user, User))
