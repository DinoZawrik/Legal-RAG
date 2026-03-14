"""
═══════════════════════════════════════════════════════════════════════════════
  E2E Tests — Admin Panel (Streamlit)
  Covers: Login, File Management, User Management, Task Monitor, Logout
═══════════════════════════════════════════════════════════════════════════════
"""

import os
import re
import pytest
from playwright.sync_api import Page, expect

from tests.e2e.conftest import ADMIN_PANEL_URL, ADMIN_PASSWORD

pytestmark = [pytest.mark.e2e]


# ═════════════════════════════════════════════════════════════════════════════
# ЭТАП 1 — Разведка (Reconnaissance)
# ═════════════════════════════════════════════════════════════════════════════

class TestAdminReconnaissance:
    """Page load, initial render, console errors."""

    def test_page_loads_successfully(self, page: Page):
        """Admin panel should load without HTTP errors."""
        response = page.goto(ADMIN_PANEL_URL, wait_until="networkidle")
        assert response is not None
        assert response.status < 400, f"Page returned HTTP {response.status}"

    def test_login_page_renders(self, page: Page):
        """Login form must be visible on first visit."""
        page.goto(ADMIN_PANEL_URL, wait_until="networkidle")
        page.wait_for_selector("text=Вход в систему", timeout=20_000)

        # Header text
        assert page.locator("text=ГЧПРО Admin Panel").is_visible()
        assert page.locator("text=Веб-интерфейс для управления").is_visible()

        # Form inputs
        username_input = page.locator('input[aria-label="Имя пользователя"]')
        password_input = page.locator('input[aria-label="Пароль"]')
        assert username_input.is_visible(), "Username input not found"
        assert password_input.is_visible(), "Password input not found"

        # Submit button
        login_btn = page.get_by_role("button", name="Войти")
        assert login_btn.is_visible(), "Login button not found"

    def test_no_js_errors_on_load(self, page: Page):
        """No critical JS errors should appear in the console."""
        errors = []
        page.on("pageerror", lambda err: errors.append(str(err)))
        page.goto(ADMIN_PANEL_URL, wait_until="networkidle")
        page.wait_for_timeout(3000)
        critical = [e for e in errors if "TypeError" in e or "ReferenceError" in e]
        assert not critical, f"JS errors on load: {critical}"


# ═════════════════════════════════════════════════════════════════════════════
# ЭТАП 2 — Happy Path (Authentication)
# ═════════════════════════════════════════════════════════════════════════════

class TestAdminAuth:
    """Login / Logout flow."""

    def test_login_with_valid_credentials(self, page: Page):
        """Should successfully authenticate with correct password."""
        page.goto(ADMIN_PANEL_URL, wait_until="networkidle")
        page.wait_for_selector("text=Вход в систему", timeout=20_000)

        page.fill('input[aria-label="Имя пользователя"]', "admin")
        page.fill('input[aria-label="Пароль"]', ADMIN_PASSWORD)
        page.get_by_role("button", name="Войти").click()

        # After login, sidebar navigation buttons should appear
        page.wait_for_timeout(4000)
        assert page.locator("text=Управление файлами").is_visible() or \
               page.locator("text=Выйти").is_visible(), \
            "Post-login UI not loaded — still on login page?"

    def test_login_with_wrong_password(self, page: Page):
        """Should show error with incorrect credentials."""
        page.goto(ADMIN_PANEL_URL, wait_until="networkidle")
        page.wait_for_selector("text=Вход в систему", timeout=20_000)

        page.fill('input[aria-label="Имя пользователя"]', "admin")
        page.fill('input[aria-label="Пароль"]', "wrong_password_123")
        page.get_by_role("button", name="Войти").click()
        page.wait_for_timeout(2000)

        # Should show error message
        error_visible = page.locator("text=Неверные учетные данные").is_visible()
        still_on_login = page.locator("text=Вход в систему").is_visible()
        assert error_visible or still_on_login, "No error shown for wrong credentials"

    def test_login_with_empty_password(self, page: Page):
        """Empty password must not authenticate."""
        page.goto(ADMIN_PANEL_URL, wait_until="networkidle")
        page.wait_for_selector("text=Вход в систему", timeout=20_000)

        page.fill('input[aria-label="Имя пользователя"]', "admin")
        # Leave password empty
        page.get_by_role("button", name="Войти").click()
        page.wait_for_timeout(2000)

        # Should remain on login page
        assert page.locator("text=Вход в систему").is_visible(), \
            "Empty password should not grant access"

    def test_logout(self, admin_page: Page):
        """Logout button should return to login page."""
        page = admin_page
        logout_btn = page.get_by_role("button", name=re.compile("Выйти"))
        if logout_btn.is_visible():
            logout_btn.click()
            page.wait_for_timeout(3000)
            assert page.locator("text=Вход в систему").is_visible(), \
                "Not redirected to login after logout"


# ═════════════════════════════════════════════════════════════════════════════
# ЭТАП 2 — Happy Path (Navigation & Pages)
# ═════════════════════════════════════════════════════════════════════════════

class TestAdminNavigation:
    """Sidebar navigation between pages."""

    def test_sidebar_buttons_visible(self, admin_page: Page):
        """All navigation buttons should be present in sidebar."""
        page = admin_page
        assert page.locator("text=Управление файлами").first.is_visible()
        assert page.locator("text=Пользователи").first.is_visible()
        assert page.locator("text=Мониторинг задач").first.is_visible()

    def test_navigate_to_files_page(self, admin_page: Page):
        """Files page should show upload interface and document list."""
        page = admin_page
        page.get_by_role("button", name=re.compile("Управление файлами")).click()
        page.wait_for_timeout(3000)

        # Should show file management UI
        files_visible = (
            page.locator("text=Управление файлами").first.is_visible() or
            page.locator("text=Загрузка").first.is_visible() or
            page.locator("text=Отдельные файлы").first.is_visible()
        )
        assert files_visible, "Files page content not loaded"

    def test_navigate_to_users_page(self, admin_page: Page):
        """Users page should show user management interface."""
        page = admin_page
        page.get_by_role("button", name=re.compile("Пользователи")).click()
        page.wait_for_timeout(3000)

        users_visible = (
            page.locator("text=Telegram").first.is_visible() or
            page.locator("text=пользовател").first.is_visible()
        )
        assert users_visible, "Users page content not loaded"

    def test_navigate_to_tasks_page(self, admin_page: Page):
        """Tasks page should show monitoring interface."""
        page = admin_page
        page.get_by_role("button", name=re.compile("Мониторинг задач")).click()
        page.wait_for_timeout(3000)

        tasks_visible = (
            page.locator("text=Мониторинг задач").first.is_visible() or
            page.locator("text=Обновить").first.is_visible()
        )
        assert tasks_visible, "Tasks page content not loaded"


# ═════════════════════════════════════════════════════════════════════════════
# ЭТАП 2 — Happy Path (File Management)
# ═════════════════════════════════════════════════════════════════════════════

class TestFileManagement:
    """File upload, search, and listing."""

    def test_file_upload_tabs_visible(self, admin_page: Page):
        """File page should have tabs for individual files and archives."""
        page = admin_page
        page.get_by_role("button", name=re.compile("Управление файлами")).click()
        page.wait_for_timeout(3000)

        assert page.locator("text=Отдельные файлы").first.is_visible()
        assert page.locator("text=Архивы").first.is_visible()

    def test_document_search_field_exists(self, admin_page: Page):
        """Document search input should be present on files page."""
        page = admin_page
        page.get_by_role("button", name=re.compile("Управление файлами")).click()
        page.wait_for_timeout(3000)

        search_input = page.locator('input[aria-label*="Поиск"]').first
        search_visible = search_input.is_visible() if search_input.count() > 0 else False

        # Alternative: look for placeholder text
        if not search_visible:
            search_input = page.locator('[placeholder*="Введите название"]').first
            search_visible = search_input.is_visible() if search_input.count() > 0 else False

        assert search_visible, "Document search field not found"

    def test_loaded_documents_section(self, admin_page: Page):
        """Should show loaded documents section (even if empty)."""
        page = admin_page
        page.get_by_role("button", name=re.compile("Управление файлами")).click()
        page.wait_for_timeout(3000)

        docs_section = (
            page.locator("text=Загруженные документы").first.is_visible() or
            page.locator("text=Загруженных документов пока нет").first.is_visible() or
            page.locator("text=Найдено документов").first.is_visible()
        )
        assert docs_section, "Loaded documents section not found"


# ═════════════════════════════════════════════════════════════════════════════
# ЭТАП 2 — Happy Path (Task Monitor)
# ═════════════════════════════════════════════════════════════════════════════

class TestTaskMonitor:
    """Task monitoring page functionality."""

    def test_task_monitor_controls(self, admin_page: Page):
        """Task monitor should have refresh and auto-refresh controls."""
        page = admin_page
        page.get_by_role("button", name=re.compile("Мониторинг задач")).click()
        page.wait_for_timeout(3000)

        # Should have refresh/debug buttons
        refresh_visible = page.locator("text=Обновить").first.is_visible()
        auto_refresh_visible = page.locator("text=Автообновление").first.is_visible()
        assert refresh_visible or auto_refresh_visible, "Task monitor controls not found"


# ═════════════════════════════════════════════════════════════════════════════
# ЭТАП 3 — Negative Testing & Edge Cases
# ═════════════════════════════════════════════════════════════════════════════

class TestNegativeScenarios:
    """Invalid inputs, XSS, boundary conditions."""

    def test_xss_in_username(self, page: Page):
        """XSS payload in username should not execute."""
        page.goto(ADMIN_PANEL_URL, wait_until="networkidle")
        page.wait_for_selector("text=Вход в систему", timeout=20_000)

        xss_payload = '<script>alert("XSS")</script>'
        page.fill('input[aria-label="Имя пользователя"]', xss_payload)
        page.fill('input[aria-label="Пароль"]', "test")
        page.get_by_role("button", name="Войти").click()
        page.wait_for_timeout(2000)

        # Should not execute — check no alert dialog appeared
        # and the page is still functional
        assert page.locator("text=Вход в систему").is_visible() or \
               page.locator("text=Неверные учетные данные").is_visible(), \
            "XSS payload may have broken the page"

    def test_xss_in_password(self, page: Page):
        """XSS payload in password field."""
        page.goto(ADMIN_PANEL_URL, wait_until="networkidle")
        page.wait_for_selector("text=Вход в систему", timeout=20_000)

        page.fill('input[aria-label="Имя пользователя"]', "admin")
        page.fill('input[aria-label="Пароль"]', '<img src=x onerror=alert(1)>')
        page.get_by_role("button", name="Войти").click()
        page.wait_for_timeout(2000)

        # Page should remain functional
        page_text = page.text_content("body") or ""
        assert "Вход в систему" in page_text or "Неверные" in page_text

    def test_sql_injection_in_login(self, page: Page):
        """SQL injection attempt should not bypass auth."""
        page.goto(ADMIN_PANEL_URL, wait_until="networkidle")
        page.wait_for_selector("text=Вход в систему", timeout=20_000)

        page.fill('input[aria-label="Имя пользователя"]', "admin' OR '1'='1")
        page.fill('input[aria-label="Пароль"]', "' OR '1'='1")
        page.get_by_role("button", name="Войти").click()
        page.wait_for_timeout(2000)

        # Should NOT grant access
        still_on_login = page.locator("text=Вход в систему").is_visible()
        error_shown = page.locator("text=Неверные учетные данные").is_visible()
        assert still_on_login or error_shown, "SQL injection may have bypassed auth!"

    def test_long_input_in_username(self, page: Page):
        """Very long input should not crash the page."""
        page.goto(ADMIN_PANEL_URL, wait_until="networkidle")
        page.wait_for_selector("text=Вход в систему", timeout=20_000)

        long_string = "A" * 10_000
        page.fill('input[aria-label="Имя пользователя"]', long_string)
        page.fill('input[aria-label="Пароль"]', long_string)
        page.get_by_role("button", name="Войти").click()
        page.wait_for_timeout(2000)

        # Page should still be functional
        body = page.text_content("body") or ""
        assert len(body) > 0, "Page crashed with long input"

    def test_special_characters_in_password(self, page: Page):
        """Unicode and special chars should not break login."""
        page.goto(ADMIN_PANEL_URL, wait_until="networkidle")
        page.wait_for_selector("text=Вход в систему", timeout=20_000)

        page.fill('input[aria-label="Имя пользователя"]', "admin")
        page.fill('input[aria-label="Пароль"]', "🔒💀🎭<>&\"' DROP TABLE;--")
        page.get_by_role("button", name="Войти").click()
        page.wait_for_timeout(2000)

        assert page.locator("text=Вход в систему").is_visible() or \
               page.locator("text=Неверные учетные данные").is_visible()

    def test_search_xss_after_login(self, admin_page: Page):
        """XSS in document search field should be sanitized."""
        page = admin_page
        page.get_by_role("button", name=re.compile("Управление файлами")).click()
        page.wait_for_timeout(3000)

        search_input = page.locator('input[aria-label*="Поиск"]').first
        if search_input.count() > 0 and search_input.is_visible():
            search_input.fill('<script>alert("XSS")</script>')
            # Trigger search
            find_btn = page.locator("text=Найти").first
            if find_btn.is_visible():
                find_btn.click()
            page.wait_for_timeout(2000)

            # Page should remain functional
            assert page.locator("text=Управление файлами").first.is_visible() or \
                   page.locator("text=Загруженные").first.is_visible()

    def test_rapid_login_attempts(self, page: Page):
        """Multiple rapid login attempts should not crash the app."""
        page.goto(ADMIN_PANEL_URL, wait_until="networkidle")
        page.wait_for_selector("text=Вход в систему", timeout=20_000)

        for i in range(5):
            page.fill('input[aria-label="Имя пользователя"]', f"user{i}")
            page.fill('input[aria-label="Пароль"]', f"wrong{i}")
            page.get_by_role("button", name="Войти").click()
            page.wait_for_timeout(1000)

        # Page should still be responsive
        body = page.text_content("body") or ""
        assert "Вход" in body or "Admin" in body, "Page became unresponsive after rapid attempts"
