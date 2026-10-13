from django.test.runner import DiscoverRunner


class ApplicationDiscoverRunner(DiscoverRunner):
    """Discover Django application tests without importing root-level utility scripts."""

    application_labels = ['adminpanel', 'manager', 'projects', 'users', 'project_manage']

    def build_suite(self, test_labels=None, **kwargs):
        return super().build_suite(test_labels or self.application_labels, **kwargs)
