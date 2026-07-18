"""Smoke tests: every page must build its component tree without errors."""

import pytest


@pytest.fixture(scope="module", autouse=True)
def _app():
    """Import the app once (registers pages, creates tables)."""
    import observatory.observatory  # noqa: F401


def test_dashboard_builds():
    from observatory.pages.dashboard import dashboard

    assert dashboard() is not None


def test_analytics_builds():
    from observatory.pages.analytics import analytics

    assert analytics() is not None


def test_scenarios_builds():
    from observatory.pages.scenarios import scenarios

    assert scenarios() is not None


def test_settings_builds():
    from observatory.pages.settings import settings

    assert settings() is not None
