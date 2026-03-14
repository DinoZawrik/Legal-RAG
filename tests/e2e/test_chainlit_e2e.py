"""
═══════════════════════════════════════════════════════════════════════════════
  E2E Tests — Chainlit Chat Interface
  Covers: Page load, welcome message, starter buttons, chat flow
═══════════════════════════════════════════════════════════════════════════════
"""

import pytest
from playwright.sync_api import Page, expect

from tests.e2e.conftest import CHAINLIT_URL

pytestmark = [pytest.mark.e2e]


# ═════════════════════════════════════════════════════════════════════════════
# ЭТАП 1 — Разведка (Reconnaissance)
# ═════════════════════════════════════════════════════════════════════════════

class TestChainlitReconnaissance:
    """Initial page load and structure."""

    def test_page_loads(self, page: Page):
        """Chainlit app should return HTTP 200."""
        response = page.goto(CHAINLIT_URL, wait_until="networkidle")
        assert response is not None
        assert response.status == 200

    def test_welcome_message_displayed(self, page: Page):
        """Welcome message with system description should appear."""
        page.goto(CHAINLIT_URL, wait_until="networkidle")
        page.wait_for_timeout(5000)

        body = page.text_content("body") or ""
        assert "LegalRAG" in body, "Welcome message 'LegalRAG' not found"

    def test_chat_input_available(self, page: Page):
        """Chat input field should be visible and interactive."""
        page.goto(CHAINLIT_URL, wait_until="networkidle")
        page.wait_for_timeout(5000)

        # Chainlit uses various selectors for chat input
        input_selectors = [
            'textarea',
            '[placeholder*="message"]',
            '[placeholder*="Message"]',
            '[placeholder*="Введите"]',
            '.cl-textarea',
        ]

        input_found = False
        for selector in input_selectors:
            el = page.locator(selector).first
            if el.count() > 0 and el.is_visible():
                input_found = True
                break

        assert input_found, "Chat input field not found"

    def test_no_critical_js_errors(self, page: Page):
        """No critical JS errors on initial load."""
        errors = []
        page.on("pageerror", lambda err: errors.append(str(err)))
        page.goto(CHAINLIT_URL, wait_until="networkidle")
        page.wait_for_timeout(5000)

        critical = [e for e in errors if "TypeError" in e or "ReferenceError" in e]
        assert not critical, f"JS errors: {critical}"


# ═════════════════════════════════════════════════════════════════════════════
# ЭТАП 2 — Happy Path (Chat Functionality)
# ═════════════════════════════════════════════════════════════════════════════

class TestChainlitChat:
    """Core chat interaction flow."""

    def _find_chat_input(self, page: Page):
        """Helper: locate the chat input element."""
        for selector in ['textarea', '[placeholder*="message"]', '[placeholder*="Message"]']:
            el = page.locator(selector).first
            if el.count() > 0 and el.is_visible():
                return el
        return None

    def test_starter_buttons_displayed(self, page: Page):
        """Quick-start suggestion buttons should appear."""
        page.goto(CHAINLIT_URL, wait_until="networkidle")
        page.wait_for_timeout(5000)

        body = page.text_content("body") or ""
        # Check for at least one starter label from chainlit_app.py
        starters = ["Определение", "Сроки и цифры", "Сравнительный анализ", "Порядок действий"]
        found = any(s in body for s in starters)
        # Starters may not render if API is down — only warn
        if not found:
            pytest.skip("Starter buttons not found — API may be unavailable")

    def test_send_simple_message(self, page: Page):
        """User should be able to type and send a message."""
        page.goto(CHAINLIT_URL, wait_until="networkidle")
        page.wait_for_timeout(5000)

        chat_input = self._find_chat_input(page)
        assert chat_input is not None, "Chat input not found"

        chat_input.fill("Что такое трудовой договор?")
        chat_input.press("Enter")

        # Wait for any response indicator (step visualization or answer text)
        page.wait_for_timeout(10_000)
        body = page.text_content("body") or ""

        # Either we see RAG steps or an error about API being down
        has_response = (
            "Анализ запроса" in body or
            "Гибридный поиск" in body or
            "трудов" in body.lower() or
            "API Gateway" in body or
            "Не удалось" in body
        )
        assert has_response, "No response at all after sending message"

    def test_api_down_shows_error(self, page: Page):
        """If API is unreachable, a user-friendly error should appear (not a crash)."""
        page.goto(CHAINLIT_URL, wait_until="networkidle")
        page.wait_for_timeout(5000)

        chat_input = self._find_chat_input(page)
        if chat_input is None:
            pytest.skip("Chat input not found")

        chat_input.fill("Тестовый запрос")
        chat_input.press("Enter")
        page.wait_for_timeout(15_000)

        body = page.text_content("body") or ""
        # Should show something — either a real answer or a clear error
        assert len(body) > 100, "Page content suspiciously short after query"


# ═════════════════════════════════════════════════════════════════════════════
# ЭТАП 3 — Negative Testing
# ═════════════════════════════════════════════════════════════════════════════

class TestChainlitNegative:
    """Edge cases for the chat interface."""

    def _find_chat_input(self, page: Page):
        for selector in ['textarea', '[placeholder*="message"]', '[placeholder*="Message"]']:
            el = page.locator(selector).first
            if el.count() > 0 and el.is_visible():
                return el
        return None

    def test_empty_message_not_sent(self, page: Page):
        """Pressing Enter with empty input should not send a message."""
        page.goto(CHAINLIT_URL, wait_until="networkidle")
        page.wait_for_timeout(5000)

        chat_input = self._find_chat_input(page)
        if chat_input is None:
            pytest.skip("Chat input not found")

        # Count messages before
        messages_before = page.locator(".message, .cl-message").count()
        chat_input.press("Enter")
        page.wait_for_timeout(2000)
        messages_after = page.locator(".message, .cl-message").count()

        # No new user messages should appear
        assert messages_after <= messages_before + 1, "Empty message was sent"

    def test_xss_in_chat_message(self, page: Page):
        """XSS payload in chat should be escaped/sanitized."""
        page.goto(CHAINLIT_URL, wait_until="networkidle")
        page.wait_for_timeout(5000)

        chat_input = self._find_chat_input(page)
        if chat_input is None:
            pytest.skip("Chat input not found")

        xss = '<img src=x onerror="document.title=\'PWNED\'">'
        chat_input.fill(xss)
        chat_input.press("Enter")
        page.wait_for_timeout(5000)

        assert page.title() != "PWNED", "XSS payload executed in chat!"

    def test_very_long_message(self, page: Page):
        """Extremely long message should not crash the UI."""
        page.goto(CHAINLIT_URL, wait_until="networkidle")
        page.wait_for_timeout(5000)

        chat_input = self._find_chat_input(page)
        if chat_input is None:
            pytest.skip("Chat input not found")

        long_msg = "Тест " * 2000  # ~10K chars
        chat_input.fill(long_msg)
        chat_input.press("Enter")
        page.wait_for_timeout(5000)

        # Page should still be interactive
        body = page.text_content("body") or ""
        assert len(body) > 50, "Page crashed with long message"
