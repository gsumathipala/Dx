"""Test runner that accounts for the append-only audit protection.

``TransactionTestCase`` resets the database with TRUNCATE between tests, which
the audit triggers correctly refuse. The runner therefore drops the triggers on
the *test* database once it is built; the tests that assert the protection
install them for the duration of their own case.
"""
from __future__ import annotations

from django.test.runner import DiscoverRunner


class DxTestRunner(DiscoverRunner):
    def setup_test_environment(self, **kwargs):
        """Serve static files straight from disk during tests.

        Production uses WhiteNoise's manifest storage, which requires
        ``collectstatic`` to have been run. Requiring that before the test
        suite would make every template test depend on a build step.
        """
        from django.conf import settings

        super().setup_test_environment(**kwargs)
        settings.STORAGES = {
            **settings.STORAGES,
            "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
        }

    def setup_databases(self, **kwargs):
        config = super().setup_databases(**kwargs)

        from django.db import connection

        from apps.audit import protection

        protection.remove(connection)
        return config
