from io import StringIO
from unittest.mock import patch

from django.contrib.auth import authenticate, get_user_model
from django.core.management import call_command, CommandError
from django.test import TestCase


class SyncAdminTests(TestCase):
    password = "a-long-test-password-for-admin"

    def sync(self, username="private-editor", **extra):
        values = {"ADMIN_USERNAME": username, "ADMIN_PASSWORD": self.password, **extra}
        output = StringIO()
        with patch("webapp.management.commands.sync_admin.setting",
                   side_effect=lambda key, default="": values.get(key, default)):
            call_command("sync_admin", stdout=output)
        self.assertNotIn(username, output.getvalue())
        return get_user_model().objects.get(username=username)

    def test_custom_account_and_repeat_startup(self):
        user = self.sync()
        self.assertTrue(user.is_superuser and user.is_staff)
        self.assertEqual(self.sync().password, user.password)
        self.assertFalse(get_user_model().objects.filter(username="admin").exists())
        self.assertIsNotNone(authenticate(username=user.username, password=self.password))

    def test_legacy_rename_preserves_identity_and_invalidates_session(self):
        old = get_user_model().objects.create_superuser("admin", password=self.password)
        self.client.force_login(old)
        user = self.sync()
        self.assertEqual(user.pk, old.pk)
        self.assertNotEqual(user.password, old.password)
        self.assertIsNone(authenticate(username="admin", password=self.password))
        self.assertEqual(self.client.get("/admin/library/").status_code, 302)

    def test_later_rename(self):
        old = self.sync()
        user = self.sync("another-editor", ADMIN_PREVIOUS_USERNAME=old.username)
        self.assertEqual(user.pk, old.pk)
        self.assertFalse(get_user_model().objects.filter(username=old.username).exists())

    def test_missing_default_or_invalid_username_rejected(self):
        for username in ("", "admin", "ADMIN", "bad name", "x" * 151):
            with self.subTest(username=username), self.assertRaises(CommandError):
                self.sync(username)
        self.assertEqual(get_user_model().objects.count(), 0)

    def test_existing_regular_user_not_promoted(self):
        user = get_user_model().objects.create_user("private-editor")
        with self.assertRaises(CommandError):
            self.sync()
        user.refresh_from_db()
        self.assertFalse(user.is_staff or user.is_superuser)

    def test_rename_collision_leaves_accounts_unchanged(self):
        old = get_user_model().objects.create_superuser("admin", password=self.password)
        get_user_model().objects.create_superuser("private-editor", password=self.password)
        with self.assertRaises(CommandError):
            self.sync()
        old.refresh_from_db()
        self.assertEqual(old.username, "admin")
