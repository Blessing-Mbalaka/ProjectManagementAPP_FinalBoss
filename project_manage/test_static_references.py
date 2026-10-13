import re
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.contrib.staticfiles import finders
from django.test import SimpleTestCase


STATIC_TAG_PATTERN = re.compile(r"{%\s*static\s+(['\"])(?P<path>.+?)\1")


class StaticReferenceTests(SimpleTestCase):
    def test_literal_template_static_references_resolve(self):
        template_dirs = {
            Path(path)
            for backend in settings.TEMPLATES
            for path in backend.get("DIRS", [])
        }
        template_dirs.update(
            Path(config.path) / "templates"
            for config in apps.get_app_configs()
            if (Path(config.path) / "templates").is_dir()
        )

        missing = []
        for template_dir in sorted(template_dirs):
            for template_path in sorted(template_dir.rglob("*.html")):
                contents = template_path.read_text(encoding="utf-8")
                for match in STATIC_TAG_PATTERN.finditer(contents):
                    static_path = match.group("path")
                    if finders.find(static_path) is None:
                        try:
                            display_path = template_path.relative_to(settings.BASE_DIR)
                        except ValueError:
                            display_path = template_path
                        missing.append(f"{display_path}: {static_path}")

        self.assertEqual(
            [],
            missing,
            "Unresolved static references:\n" + "\n".join(missing),
        )
