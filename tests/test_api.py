import pytest


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
