"""
═══════════════════════════════════════════════════════════════════════════════
  E2E Tests — API Gateway HTTP Checks
  Uses Playwright to verify API health endpoints and error handling.
═══════════════════════════════════════════════════════════════════════════════
"""

import json
import pytest
from playwright.sync_api import Page, APIRequestContext

from tests.e2e.conftest import API_GATEWAY_URL

pytestmark = [pytest.mark.e2e]


class TestAPIHealth:
    """API Gateway availability and health endpoints."""

    def test_health_endpoint(self, page: Page):
        """GET /health should return 200."""
        response = page.goto(f"{API_GATEWAY_URL}/health")
        if response is None:
            pytest.skip("API Gateway not reachable")
        assert response.status == 200, f"/health returned {response.status}"

    def test_info_endpoint(self, page: Page):
        """GET /info should return JSON with service info."""
        response = page.goto(f"{API_GATEWAY_URL}/info")
        if response is None:
            pytest.skip("API Gateway not reachable")
        assert response.status == 200
        body = page.text_content("body") or ""
        # Should be valid JSON
        try:
            data = json.loads(body)
            assert "services" in data or "version" in data or "status" in data
        except json.JSONDecodeError:
            pytest.fail(f"/info did not return valid JSON: {body[:200]}")

    def test_health_all_endpoint(self, page: Page):
        """GET /health/all should report all service statuses."""
        response = page.goto(f"{API_GATEWAY_URL}/health/all")
        if response is None:
            pytest.skip("API Gateway not reachable")
        # Accept 200 or 503 (degraded)
        assert response.status in (200, 503), f"/health/all returned {response.status}"


class TestAPI404:
    """Non-existent routes should return proper 404."""

    def test_nonexistent_route(self, page: Page):
        """GET /this-page-does-not-exist should return 404 or similar."""
        response = page.goto(f"{API_GATEWAY_URL}/this-page-does-not-exist")
        if response is None:
            pytest.skip("API Gateway not reachable")
        assert response.status in (404, 405), \
            f"Expected 404 for non-existent route, got {response.status}"

    def test_nonexistent_api_route(self, page: Page):
        """GET /api/nonexistent should return 404."""
        response = page.goto(f"{API_GATEWAY_URL}/api/nonexistent")
        if response is None:
            pytest.skip("API Gateway not reachable")
        assert response.status in (404, 405), \
            f"Expected 404, got {response.status}"


class TestAdminPanel404:
    """Admin panel non-existent routes."""

    def test_admin_nonexistent_page(self, page: Page):
        """Streamlit handles all routes internally — should not crash."""
        from tests.e2e.conftest import ADMIN_PANEL_URL
        response = page.goto(f"{ADMIN_PANEL_URL}/this-page-does-not-exist")
        if response is None:
            pytest.skip("Admin panel not reachable")
        # Streamlit returns 200 for all routes (SPA), check page is functional
        assert response.status in (200, 404)
        body = page.text_content("body") or ""
        assert len(body) > 0, "Empty page on non-existent route"
