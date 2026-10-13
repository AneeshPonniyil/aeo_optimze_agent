import asyncio
import pytest
from unittest.mock import patch
from app.core.security import SSRFSecurityValidator, URLValidationError


@pytest.mark.asyncio
async def test_valid_public_urls():
    """Verify that safe, public HTTP/HTTPS URLs pass validation and normalization."""
    valid_urls = [
        "https://example.com",
        "http://example.com/about",
        "example.com/blog?query=aeo#section",
        "https://schema.org/docs/documents.html",
    ]
    for url in valid_urls:
        normalized = await SSRFSecurityValidator.validate_and_normalize_url(url)
        assert normalized.startswith("http://") or normalized.startswith("https://")
        assert "#" not in normalized  # Fragment should be stripped


@pytest.mark.asyncio
async def test_invalid_schemes():
    """Verify that unsupported or dangerous URL schemes are rejected."""
    invalid_schemes = [
        "ftp://example.com/file.txt",
        "file:///etc/passwd",
        "gopher://127.0.0.1:70",
        "mailto:admin@example.com",
        "javascript:alert(1)",
    ]
    for url in invalid_schemes:
        with pytest.raises(URLValidationError, match="Only HTTP and HTTPS are permitted|scheme"):
            await SSRFSecurityValidator.validate_and_normalize_url(url)


@pytest.mark.asyncio
async def test_loopback_and_localhost_blocked():
    """Verify that localhost and loopback IP addresses are blocked."""
    loopback_urls = [
        "http://localhost",
        "http://localhost:8000",
        "http://sub.localhost",
        "http://127.0.0.1",
        "http://127.0.0.1:5000/admin",
        "http://[::1]",
    ]
    for url in loopback_urls:
        with pytest.raises(URLValidationError):
            await SSRFSecurityValidator.validate_and_normalize_url(url)


@pytest.mark.asyncio
async def test_private_ip_subnets_blocked():
    """Verify that private subnet IP addresses are blocked."""
    private_urls = [
        "http://10.0.0.1",
        "http://10.255.255.255/internal",
        "http://172.16.0.1",
        "http://192.168.1.1",
        "http://192.168.0.100:8080",
    ]
    for url in private_urls:
        with pytest.raises(URLValidationError, match="restricted network range"):
            await SSRFSecurityValidator.validate_and_normalize_url(url)


@pytest.mark.asyncio
async def test_cloud_metadata_blocked():
    """Verify that cloud provider metadata endpoints are blocked."""
    metadata_urls = [
        "http://169.254.169.254",
        "http://169.254.169.254/latest/meta-data/",
    ]
    for url in metadata_urls:
        with pytest.raises(URLValidationError):
            await SSRFSecurityValidator.validate_and_normalize_url(url)


@pytest.mark.asyncio
async def test_dns_rebinding_prevention():
    """Verify that a domain resolving to a private IP (DNS rebinding) is blocked."""
    with patch("socket.getaddrinfo") as mock_getaddrinfo:
        # Mock DNS resolution returning a private IP for a public-looking domain name
        mock_getaddrinfo.return_value = [
            (None, None, None, None, ("192.168.1.50", 80))
        ]
        with pytest.raises(URLValidationError, match="resolves to restricted IP address"):
            await SSRFSecurityValidator.validate_and_normalize_url("http://malicious-rebinding-domain.com")


@pytest.mark.asyncio
async def test_unresolvable_domain_rejected():
    """Verify that domains failing DNS resolution are rejected."""
    with pytest.raises(URLValidationError, match="Domain DNS resolution failed"):
        await SSRFSecurityValidator.validate_and_normalize_url("http://this-domain-definitely-does-not-exist-9988776655.com")


@pytest.mark.asyncio
async def test_async_dns_timeout_handling():
    """Verify that slow/hanging DNS resolutions trigger a timeout error."""
    async def slow_getaddrinfo(*args, **kwargs):
        await asyncio.sleep(1.0)
        return []

    loop = asyncio.get_running_loop()
    with patch.object(loop, "getaddrinfo", side_effect=slow_getaddrinfo):
        with pytest.raises(URLValidationError, match="Domain DNS resolution timed out"):
            await SSRFSecurityValidator.validate_and_normalize_url("https://slow-dns-lookup-target.org", timeout=0.01)


def test_sync_validate_and_normalize_url():
    """Verify synchronous fallback validation works as expected outside event loop."""
    normalized = SSRFSecurityValidator.validate_and_normalize_url_sync("https://example.com/path#fragment")
    assert normalized == "https://example.com/path"

    with pytest.raises(URLValidationError):
        SSRFSecurityValidator.validate_and_normalize_url_sync("http://127.0.0.1:9000")

