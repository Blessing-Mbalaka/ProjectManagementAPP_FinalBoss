from pathlib import Path

from django.test import SimpleTestCase

from project_manage import settings_test


class TestDatabaseIsolationTests(SimpleTestCase):
    def test_test_settings_use_workspace_test_db(self):
        database = settings_test.DATABASES["default"]
        database_path = Path(database["NAME"]).resolve()
        demo_database_path = Path(settings_test.TEST_DB_PATH).resolve()
        test_suite_path = Path(database["TEST"]["NAME"]).resolve()

        self.assertEqual(database["ENGINE"], "django.db.backends.sqlite3")
        self.assertEqual(demo_database_path.name, "test.db")
        self.assertEqual(demo_database_path.parent.name, "test_artifacts")
        self.assertTrue(demo_database_path.is_relative_to(Path(settings_test.BASE_DIR).resolve()))
        self.assertNotEqual(str(database["NAME"]), ":memory:")
        self.assertEqual(test_suite_path.name, "test_suite.db")
        self.assertEqual(test_suite_path.parent, demo_database_path.parent)
        self.assertNotEqual(test_suite_path, demo_database_path)
        # Django swaps NAME to the suite path while tests are running.
        self.assertIn(database_path, {demo_database_path, test_suite_path})
