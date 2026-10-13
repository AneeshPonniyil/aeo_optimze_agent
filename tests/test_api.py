import pytest
from app.config import Settings, settings
from app.core.rate_limiter import audit_rate_limiter


@pytest.mark.asyncio
async def test_health_endpoint(async_client):
    response = await async_client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert "service" in data
    assert "llm_provider" in data


@pytest.mark.asyncio
async def test_validate_url_endpoint_valid(async_client):
    response = await async_client.post(
        "/api/v1/validate-url",
        json={"url": "https://example.com"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["is_valid"] is True
    assert data["normalized_url"] == "https://example.com/"


@pytest.mark.asyncio
async def test_validate_url_endpoint_blocked_ip(async_client):
    response = await async_client.post(
        "/api/v1/validate-url",
        json={"url": "http://127.0.0.1:8000"}
    )
    assert response.status_code == 400
    data = response.json()
    assert "detail" in data


@pytest.mark.asyncio
async def test_root_serves_frontend(async_client):
    response = await async_client.get("/")
    assert response.status_code == 200
    assert "Zenvora AI" in response.text


# =====================================================================
# Milestone 5 Security Regression Tests
# =====================================================================

# 1. Configuration & Secret Hardening Tests

def test_config_development_defaults():
    dev_settings = Settings(ENVIRONMENT="development")
    assert dev_settings.SECRET_KEY is not None
    assert dev_settings.AUDIT_API_KEY is not None
    assert dev_settings.DEBUG is True


def test_config_production_fails_when_secret_key_missing():
    with pytest.raises(ValueError, match="SECRET_KEY must be securely configured"):
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY=None,
            AUDIT_API_KEY="secure-production-api-key-here",
            ALLOWED_ORIGINS=["https://zenvora.ai"],
            DEBUG=False,
        )


def test_config_production_fails_with_development_secret_fallback():
    with pytest.raises(ValueError, match="SECRET_KEY must be securely configured"):
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="dev_secret_key_change_in_production",
            AUDIT_API_KEY="secure-production-api-key-here",
            ALLOWED_ORIGINS=["https://zenvora.ai"],
            DEBUG=False,
        )


def test_config_production_fails_with_short_secret_key():
    with pytest.raises(ValueError, match="at least 32 characters"):
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="too-short-secret",
            AUDIT_API_KEY="secure-production-api-key-here",
            ALLOWED_ORIGINS=["https://zenvora.ai"],
            DEBUG=False,
        )


def test_config_production_fails_when_debug_enabled():
    with pytest.raises(ValueError, match="DEBUG mode must be disabled in production"):
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="a" * 32,
            AUDIT_API_KEY="secure-production-api-key-here",
            ALLOWED_ORIGINS=["https://zenvora.ai"],
            DEBUG=True,
        )


def test_config_production_fails_when_audit_api_key_missing():
    with pytest.raises(ValueError, match="AUDIT_API_KEY must be securely configured"):
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="a" * 32,
            AUDIT_API_KEY=None,
            ALLOWED_ORIGINS=["https://zenvora.ai"],
            DEBUG=False,
        )


def test_config_production_fails_with_wildcard_cors():
    with pytest.raises(ValueError, match=r"Wildcard origin '\*' is forbidden"):
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="a" * 32,
            AUDIT_API_KEY="secure-production-api-key-here",
            ALLOWED_ORIGINS=["*"],
            DEBUG=False,
        )


def test_config_cors_string_parsing():
    parsed_settings = Settings(
        ENVIRONMENT="development",
        ALLOWED_ORIGINS="https://app.zenvora.ai, https://admin.zenvora.ai",
    )
    assert parsed_settings.ALLOWED_ORIGINS == [
        "https://app.zenvora.ai",
        "https://admin.zenvora.ai",
    ]


def test_config_production_valid():
    prod_settings = Settings(
        ENVIRONMENT="production",
        SECRET_KEY="a" * 32,
        AUDIT_API_KEY="secure-production-api-key-here",
        ALLOWED_ORIGINS=["https://zenvora.ai"],
        DEBUG=False,
    )
    assert prod_settings.ENVIRONMENT == "production"
    assert prod_settings.DEBUG is False
    assert prod_settings.ALLOWED_ORIGINS == ["https://zenvora.ai"]


# 2. CORS Allowed and Rejected Origin Tests

@pytest.mark.asyncio
async def test_cors_allowed_origin(async_client):
    headers = {
        "Origin": "http://localhost:3000",
        "Access-Control-Request-Method": "GET",
    }
    response = await async_client.options("/api/v1/health", headers=headers)
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"


@pytest.mark.asyncio
async def test_cors_rejected_origin(async_client):
    headers = {
        "Origin": "https://unauthorized-malicious-site.example",
        "Access-Control-Request-Method": "GET",
    }
    response = await async_client.options("/api/v1/health", headers=headers)
    assert "access-control-allow-origin" not in response.headers


# 3. Authentication Regression Tests

@pytest.mark.asyncio
async def test_audit_creation_unauthenticated_rejected(async_client):
    response = await async_client.post(
        "/api/v1/audits",
        json={"url": "https://example.com"}
    )
    assert response.status_code == 401
    assert "X-API-Key" in response.json()["detail"]


@pytest.mark.asyncio
async def test_audit_creation_invalid_api_key_rejected(async_client):
    response = await async_client.post(
        "/api/v1/audits",
        json={"url": "https://example.com"},
        headers={"X-API-Key": "invalid-bogus-key"},
    )
    assert response.status_code == 401
    assert "Invalid API key" in response.json()["detail"]


@pytest.mark.asyncio
async def test_audit_delete_unauthenticated_rejected(async_client):
    response = await async_client.delete("/api/v1/audits/nonexistent-audit-id")
    assert response.status_code == 401


# 4. Rate Limiting Abuse Protection Tests

@pytest.mark.asyncio
async def test_audit_creation_rate_limiting_enforcement(async_client, monkeypatch):
    audit_rate_limiter.reset()
    monkeypatch.setattr(settings, "AUDIT_RATE_LIMIT_PER_MINUTE", 2)

    headers = {"X-API-Key": settings.AUDIT_API_KEY}
    # Send request with invalid URL to trigger early validation while hitting the rate limit dependency
    payload = {"url": "http://127.0.0.1:8000/blocked"}

    # Request 1: Passed through rate limiter (rejected by SSRF validator with 400)
    resp1 = await async_client.post("/api/v1/audits", json=payload, headers=headers)
    assert resp1.status_code == 400

    # Request 2: Passed through rate limiter
    resp2 = await async_client.post("/api/v1/audits", json=payload, headers=headers)
    assert resp2.status_code == 400

    # Request 3: Exceeds limit (2 per minute) -> triggers 429 Too Many Requests
    resp3 = await async_client.post("/api/v1/audits", json=payload, headers=headers)
    assert resp3.status_code == 429
    assert "Rate limit exceeded" in resp3.json()["detail"]
    assert "Retry-After" in resp3.headers

    audit_rate_limiter.reset()
