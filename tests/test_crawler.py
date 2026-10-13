import pytest
import respx
from httpx import Response
from app.core.crawler import (
    AsyncWebCrawler,
    RobotsTxtChecker,
    CrawlerFetchError,
    CrawlerRobotsDisallowedError,
)
from app.core.security import URLValidationError


@pytest.mark.asyncio
async def test_robots_txt_allowed():
    with respx.mock:
        respx.get("https://example.com/robots.txt").mock(
            return_value=Response(200, text="User-agent: *\nDisallow: /admin/")
        )
        allowed = await RobotsTxtChecker.is_url_allowed("https://example.com/about")
        assert allowed is True

        disallowed = await RobotsTxtChecker.is_url_allowed("https://example.com/admin/settings")
        assert disallowed is False


@pytest.mark.asyncio
async def test_crawler_fetch_success():
    crawler = AsyncWebCrawler()
    mock_html = "<html><head><title>Test Page</title></head><body><h1>Hello World</h1></body></html>"

    with respx.mock:
        respx.get("https://example.com/test").mock(
            return_value=Response(200, text=mock_html, headers={"Content-Type": "text/html"})
        )
        url, status_code, html, headers, elapsed = await crawler.fetch_page("https://example.com/test", check_robots=False)

        assert url == "https://example.com/test"
        assert status_code == 200
        assert "Hello World" in html
        assert elapsed >= 0.0


@pytest.mark.asyncio
async def test_crawler_rejects_ssrf_ip():
    crawler = AsyncWebCrawler()
    with pytest.raises(URLValidationError):
        await crawler.fetch_page("http://127.0.0.1:8000/secret", check_robots=False)


@pytest.mark.asyncio
async def test_crawler_handles_http_error():
    crawler = AsyncWebCrawler()
    with respx.mock:
        respx.get("https://example.com/404").mock(return_value=Response(404))
        with pytest.raises(CrawlerFetchError, match="error status code 404"):
            await crawler.fetch_page("https://example.com/404", check_robots=False)


@pytest.mark.asyncio
async def test_crawler_handles_robots_disallowed():
    crawler = AsyncWebCrawler()
    with respx.mock:
        respx.get("https://example.com/robots.txt").mock(
            return_value=Response(200, text="User-agent: *\nDisallow: /private/")
        )
        with pytest.raises(CrawlerRobotsDisallowedError):
            await crawler.fetch_page("https://example.com/private/page", check_robots=True)


@pytest.mark.asyncio
async def test_crawler_rejects_redirect_to_private_ip():
    """Verify regression protection: crawler must block redirects leading to private IPs (SSRF)."""
    crawler = AsyncWebCrawler()
    with respx.mock:
        respx.get("https://example.com/redirect-to-private").mock(
            return_value=Response(302, headers={"Location": "http://127.0.0.1:8000/admin"})
        )
        with pytest.raises(URLValidationError, match="Access to localhost is strictly prohibited|restricted"):
            await crawler.fetch_page("https://example.com/redirect-to-private", check_robots=False)


@pytest.mark.asyncio
async def test_crawler_rejects_redirect_to_cloud_metadata():
    """Verify regression protection: crawler must block redirects to cloud metadata (169.254.169.254)."""
    crawler = AsyncWebCrawler()
    with respx.mock:
        respx.get("https://example.com/redirect-to-meta").mock(
            return_value=Response(302, headers={"Location": "http://169.254.169.254/latest/meta-data/"})
        )
        with pytest.raises(URLValidationError, match="restricted network range"):
            await crawler.fetch_page("https://example.com/redirect-to-meta", check_robots=False)


@pytest.mark.asyncio
async def test_crawler_follows_valid_redirect():
    """Verify that safe HTTP 301/302 redirects are followed and content retrieved."""
    crawler = AsyncWebCrawler()
    mock_new_html = "<html><body><h1>Redirected Page</h1></body></html>"
    with respx.mock:
        respx.get("https://example.com/old-page").mock(
            return_value=Response(301, headers={"Location": "https://example.com/new-page"})
        )
        respx.get("https://example.com/new-page").mock(
            return_value=Response(200, text=mock_new_html, headers={"Content-Type": "text/html"})
        )
        final_url, status_code, html, headers, elapsed = await crawler.fetch_page(
            "https://example.com/old-page", check_robots=False
        )
        assert final_url == "https://example.com/new-page"
        assert status_code == 200
        assert "Redirected Page" in html


@pytest.mark.asyncio
async def test_crawler_exceeds_max_redirects():
    """Verify that excessive redirect chains are rejected with CrawlerFetchError."""
    crawler = AsyncWebCrawler()
    with respx.mock:
        respx.get("https://example.com/hop0").mock(
            return_value=Response(302, headers={"Location": "https://example.com/hop1"})
        )
        respx.get("https://example.com/hop1").mock(
            return_value=Response(302, headers={"Location": "https://example.com/hop2"})
        )
        respx.get("https://example.com/hop2").mock(
            return_value=Response(302, headers={"Location": "https://example.com/hop3"})
        )
        respx.get("https://example.com/hop3").mock(
            return_value=Response(302, headers={"Location": "https://example.com/hop4"})
        )
        with pytest.raises(CrawlerFetchError, match="Exceeded maximum redirect limit"):
            await crawler.fetch_page("https://example.com/hop0", check_robots=False)

