"""
E2E Test Configuration & Fixtures
Provides browser setup, authentication helpers, and URL constants.
"""

import os
import pytest
from playwright.sync_api import Playwright, Browser, BrowserContext, Page


# ── URL Constants ──────────────────────────────────────────────────────────
ADMIN_PANEL_URL = os.getenv("ADMIN_PANEL_URL", "http://localhost:8090")
CHAINLIT_URL = os.getenv("CHAINLIT_URL", "http://localhost:8501")
API_GATEWAY_URL = os.getenv("API_GATEWAY_URL", "http://localhost:8080")
ADMIN_PASSWORD = os.getenv("ADMIN_PANEL_PASSWORD", "Admin2024_Secure!")


# ── Browser Fixtures ──────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def browser(playwright: Playwright) -> Browser:
    """Launch a shared Chromium instance for the whole test session."""
    browser = playwright.chromium.launch(
        headless=os.getenv("HEADLESS", "true").lower() == "true",
        slow_mo=int(os.getenv("SLOW_MO", "0")),
    )
    yield browser
    browser.close()


@pytest.fixture(scope="function")
def context(browser: Browser) -> BrowserContext:
    """Fresh browser context per test (isolated cookies/state)."""
    ctx = browser.new_context(
        viewport={"width": 1280, "height": 800},
        locale="ru-RU",
    )
    ctx.set_default_timeout(15_000)
    yield ctx
    ctx.close()


@pytest.fixture(scope="function")
def page(context: BrowserContext) -> Page:
    """Fresh page per test."""
    p = context.new_page()
    yield p
    p.close()


# ── Authentication Helper ─────────────────────────────────────────────────

@pytest.fixture
def admin_page(page: Page) -> Page:
    """Page already authenticated in the Admin Panel."""
    _login_admin(page)
    return page


def _login_admin(page: Page):
    """Perform login flow on the Streamlit admin panel."""
    page.goto(ADMIN_PANEL_URL, wait_until="networkidle")
    page.wait_for_selector("text=Вход в систему", timeout=20_000)

    # Streamlit renders inputs inside iframes sometimes; target placeholders
    page.fill('input[aria-label="Имя пользователя"]', "admin")
    page.fill('input[aria-label="Пароль"]', ADMIN_PASSWORD)

    # Click "Войти" button inside the form
    page.get_by_role("button", name="Войти").click()

    # Wait for post-login navigation
    page.wait_for_timeout(3000)
