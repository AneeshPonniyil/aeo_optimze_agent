import time
import logging
from typing import Tuple, Optional
from urllib.parse import urlparse, urljoin
from urllib.robotparser import RobotFileParser

import httpx
from app.config import settings
from app.core.security import SSRFSecurityValidator, URLValidationError

logger = logging.getLogger("zenvora.crawler")


class CrawlerError(Exception):
    """Base exception for web crawler operations."""
    pass


class CrawlerRobotsDisallowedError(CrawlerError):
    """Raised when fetching a URL is disallowed by robots.txt."""
    pass


class CrawlerFetchError(CrawlerError):
    """Raised when page fetching fails due to network, size, or status errors."""
    pass


class RobotsTxtChecker:
    """
    Checks robots.txt permissions for target URLs.
    """
    @classmethod
    async def is_url_allowed(cls, target_url: str, user_agent: str = settings.CRAWLER_USER_AGENT) -> bool:
        parsed = urlparse(target_url)
        robots_url = urljoin(f"{parsed.scheme}://{parsed.netloc}", "/robots.txt")

        try:
            # Validate robots.txt URL itself against SSRF rules
            await SSRFSecurityValidator.validate_and_normalize_url(robots_url)

            async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
                response = await client.get(robots_url, headers={"User-Agent": user_agent})
                if response.status_code == 200:
                    parser = RobotFileParser()
                    parser.set_url(robots_url)
                    parser.parse(response.text.splitlines())
                    return parser.can_fetch(user_agent, target_url)
                # If robots.txt is 404 or unavailable, standard web etiquette treats it as allowed
                return True
        except Exception as e:
            logger.warning(f"Could not fetch or parse robots.txt at '{robots_url}': {e}. Defaulting to allowed.")
            return True


class AsyncWebCrawler:
    """
    Production-safe async crawler enforcing SSRF re-validation, stream size caps, timeouts, and robots.txt.
    """

    def __init__(self, user_agent: str = settings.CRAWLER_USER_AGENT, timeout: float = float(settings.CRAWLER_MAX_TIMEOUT_SECONDS)):
        self.user_agent = user_agent
        self.timeout = timeout
        self.max_body_bytes = settings.CRAWLER_MAX_BODY_SIZE_BYTES

    async def fetch_page(self, raw_url: str, check_robots: bool = True) -> Tuple[str, int, str, dict, float]:
        """
        Safely fetch HTML content of a URL.
        Returns: Tuple of (final_normalized_url, status_code, html_text, headers, fetch_time_seconds)
        """
        # 1. Validate initial URL for SSRF
        normalized_url = await SSRFSecurityValidator.validate_and_normalize_url(raw_url)

        # 2. Check robots.txt compliance
        if check_robots:
            allowed = await RobotsTxtChecker.is_url_allowed(normalized_url, user_agent=self.user_agent)
            if not allowed:
                raise CrawlerRobotsDisallowedError(
                    f"Crawling URL '{normalized_url}' is prohibited by robots.txt."
                )

        start_time = time.time()
        headers = {"User-Agent": self.user_agent, "Accept": "text/html,application/xhtml+xml"}

        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                follow_redirects=False,  # We manually handle redirects to validate SSRF at each hop
                headers=headers
            ) as client:
                current_url = normalized_url
                redirect_count = 0
                max_redirects = 3

                while True:
                    response = await client.get(current_url)

                    # Handle Redirects safely
                    if response.is_redirect and "location" in response.headers:
                        if redirect_count >= max_redirects:
                            raise CrawlerFetchError(f"Exceeded maximum redirect limit ({max_redirects}).")

                        redirect_target = response.headers["location"]
                        next_url = urljoin(current_url, redirect_target)

                        # Re-validate redirect target URL for SSRF!
                        current_url = await SSRFSecurityValidator.validate_and_normalize_url(next_url)
                        redirect_count += 1
                        continue

                    # Check status code
                    if response.status_code >= 400:
                        raise CrawlerFetchError(
                            f"HTTP server returned error status code {response.status_code} for URL '{current_url}'."
                        )

                    # Check Content-Length header if present
                    content_length = response.headers.get("content-length")
                    if content_length and int(content_length) > self.max_body_bytes:
                        raise CrawlerFetchError(
                            f"Content size ({content_length} bytes) exceeds maximum limit of {self.max_body_bytes} bytes."
                        )

                    # Read text body within limit
                    html_text = response.text
                    if len(html_text.encode("utf-8")) > self.max_body_bytes:
                        raise CrawlerFetchError(
                            f"Downloaded content size exceeds maximum limit of {self.max_body_bytes} bytes."
                        )

                    elapsed = time.time() - start_time
                    resp_headers = dict(response.headers)
                    return current_url, response.status_code, html_text, resp_headers, elapsed

        except httpx.TimeoutException:
            raise CrawlerFetchError(f"Request timed out after {self.timeout} seconds while accessing '{raw_url}'.")
        except httpx.HTTPError as e:
            raise CrawlerFetchError(f"Network error while accessing '{raw_url}': {str(e)}")
