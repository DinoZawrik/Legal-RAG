"""Integration tests for the API Gateway endpoints."""

import os
import sys
import pytest
import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

API_BASE = os.getenv("API_GATEWAY_URL", "http://localhost:8080")


class TestHealthEndpoints:
    """Test API health and info endpoints."""

    def test_health(self):
        resp = httpx.get(f"{API_BASE}/health", timeout=10)
        assert resp.status_code == 200

    def test_info(self):
        resp = httpx.get(f"{API_BASE}/info", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "LegalRAG"
        assert data["architecture"] == "microservices"

    def test_services_list(self):
        resp = httpx.get(f"{API_BASE}/services", timeout=10)
        assert resp.status_code == 200


class TestQueryEndpoint:
    """Test the main /api/query endpoint."""

    def test_query_requires_body(self):
        resp = httpx.post(f"{API_BASE}/api/query", json={}, timeout=30)
        # Should return 400 because query is missing
        assert resp.status_code == 400

    def test_query_with_text(self):
        resp = httpx.post(
            f"{API_BASE}/api/query",
            json={"query": "Что такое трудовой договор?", "max_results": 5},
            timeout=90,
        )
        # If search service is up, should return 200; otherwise 503
        assert resp.status_code in (200, 503)
        if resp.status_code == 200:
            data = resp.json()
            assert "answer" in data or "query" in data


class TestUploadEndpoint:
    """Test document upload endpoint."""

    def test_upload_requires_file(self):
        resp = httpx.post(
            f"{API_BASE}/api/upload",
            data={"original_filename": "test.txt", "document_type": "regulatory"},
            timeout=30,
        )
        # Should fail without file
        assert resp.status_code in (422, 400, 500)


class TestRateLimiting:
    """Test rate limiting functionality."""

    def test_many_requests_accepted(self):
        """Normal volume of requests should pass."""
        for _ in range(5):
            resp = httpx.get(f"{API_BASE}/health", timeout=5)
            assert resp.status_code == 200
