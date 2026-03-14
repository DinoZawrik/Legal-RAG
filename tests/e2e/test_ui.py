"""E2E tests for Chainlit chat UI using Playwright."""

import os
import re
import pytest

# These tests require:
# 1. Chainlit running on port 8501
# 2. API Gateway running on port 8080
# pytest -m e2e tests/e2e/

pytestmark = pytest.mark.e2e


@pytest.fixture(scope="module")
def browser_context(playwright):
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context(viewport={"width": 1280, "height": 720})
    yield context
    context.close()
    browser.close()


@pytest.fixture
def page(browser_context):
    page = browser_context.new_page()
    yield page
    page.close()


class TestChainlitUI:
    """Test the Chainlit chat interface."""

    def test_page_loads(self, page):
        page.goto("http://localhost:8501")
        page.wait_for_load_state("networkidle")
        assert "LegalRAG" in page.title()

    def test_welcome_message(self, page):
        page.goto("http://localhost:8501")
        page.wait_for_selector("text=LegalRAG", timeout=15000)
        content = page.text_content("body")
        assert "AI-ассистент" in content
        assert "Гибридного поиска" in content

    def test_chat_input_visible(self, page):
        page.goto("http://localhost:8501")
        page.wait_for_selector("text=LegalRAG", timeout=15000)
        input_box = page.locator('[placeholder="Type your message here..."]')
        assert input_box.is_visible()

    def test_send_message(self, page):
        page.goto("http://localhost:8501")
        page.wait_for_selector("text=LegalRAG", timeout=15000)
        input_box = page.locator('[placeholder="Type your message here..."]')
        input_box.fill("Что такое трудовой договор?")
        input_box.press("Enter")
        # Wait for response (up to 90 seconds for LLM)
        page.wait_for_selector("text=Анализ запроса", timeout=15000)


class TestAdminPanel:
    """Test the Streamlit admin panel."""

    def test_admin_loads(self, page):
        page.goto("http://localhost:8090")
        page.wait_for_load_state("networkidle", timeout=15000)
        assert "LegalRAG" in page.title() or "Streamlit" in page.title()

    def test_login_form(self, page):
        page.goto("http://localhost:8090")
        page.wait_for_selector("text=Вход в систему", timeout=15000)
        assert page.locator("text=Имя пользователя").is_visible()
        assert page.locator("text=Пароль").is_visible()

    def test_login_success(self, page):
        page.goto("http://localhost:8090")
        page.wait_for_selector("text=Вход в систему", timeout=15000)
        page.fill('[placeholder="admin"]', "admin")
        page.fill('[placeholder="Введите пароль"]', os.getenv("ADMIN_PANEL_PASSWORD", "Admin2024_Secure!"))
        page.click("text=Войти")
        # After login the Files page loads (not "Dashboard")
        page.wait_for_selector("text=Управление файлами", timeout=15000)
