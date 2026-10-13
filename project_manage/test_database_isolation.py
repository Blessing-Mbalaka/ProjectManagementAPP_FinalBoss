from pathlib import Path

from django.test import SimpleTestCase

from project_manage import settings_test


class TestDatabaseIsolationTests(SimpleTestCase):
    def test_test_settings_use_workspace_test_db(self):
        database = settings_test.DATABASES["default"]
        database_path = Path(database["NAME"]).resolve()

        self.assertEqual(database["ENGINE"], "django.db.backends.sqlite3")
        self.assertEqual(database_path.name, "test.db")
        self.assertEqual(database_path.parent.name, "test_artifacts")
        self.assertTrue(database_path.is_relative_to(Path(settings_test.BASE_DIR).resolve()))
        self.assertNotEqual(str(database["NAME"]), ":memory:")
