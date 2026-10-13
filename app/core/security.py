import ipaddress
import socket
import asyncio
from typing import List
from urllib.parse import urlparse, urlunparse


class URLValidationError(ValueError):
    """Raised when a URL fails safety or formatting validation."""
    pass


class SSRFSecurityValidator:
    """
    Security validator enforcing SSRF prevention, async DNS resolution,
    and safe public web destination rules.
    """
    ALLOWED_SCHEMES = {"http", "https"}

    @classmethod
    def is_ip_restricted(cls, ip_str: str) -> bool:
        """
        Check whether an IP address belongs to a restricted range
        (private, loopback, link-local, cloud metadata, multicast, reserved).
        """
        try:
            ip = ipaddress.ip_address(ip_str)
            return (
                ip.is_private
                or ip.is_loopback
                or ip.is_link_local
                or ip.is_multicast
                or ip.is_reserved
                or ip.is_unspecified
                or str(ip) == "169.254.169.254"
            )
        except ValueError:
            return False

    @classmethod
    async def resolve_hostname_ips_async(cls, hostname: str, timeout: float = 5.0) -> List[str]:
        """
        Asynchronously resolve domain hostname to IP addresses via DNS in an executor thread.
        Protects the event loop from blocking and enforces a strict DNS resolution timeout.
        """
        try:
            loop = asyncio.get_running_loop()
            addr_info = await asyncio.wait_for(
                loop.getaddrinfo(hostname, None, family=socket.AF_UNSPEC, type=socket.SOCK_STREAM),
                timeout=timeout
            )
            ips = list(set([item[4][0] for item in addr_info]))
            return ips
        except asyncio.TimeoutError:
            raise URLValidationError(f"Domain DNS resolution timed out for '{hostname}'.")
        except socket.gaierror as e:
            raise URLValidationError(f"Domain DNS resolution failed for '{hostname}': {str(e)}")

    @classmethod
    def resolve_hostname_ips(cls, hostname: str) -> List[str]:
        """
        Synchronous fallback for domain hostname resolution via DNS.
        """
        try:
            addr_info = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
            ips = list(set([item[4][0] for item in addr_info]))
            return ips
        except socket.gaierror as e:
            raise URLValidationError(f"Domain DNS resolution failed for '{hostname}': {str(e)}")

    @classmethod
    def _validate_components(cls, url: str) -> tuple:
        """
        Validate URL scheme and hostname syntax, returning (scheme, hostname, port_part, parsed).
        """
        if not url or not isinstance(url, str):
            raise URLValidationError("URL must be a non-empty string.")

        url_str = url.strip()
        parsed_initial = urlparse(url_str)
        if not parsed_initial.scheme:
            url_str = "https://" + url_str
            parsed = urlparse(url_str)
        else:
            parsed = parsed_initial

        # 1. Validate Scheme
        scheme = parsed.scheme.lower() if parsed.scheme else ""
        if scheme not in cls.ALLOWED_SCHEMES:
            raise URLValidationError(f"Invalid URL scheme '{parsed.scheme}'. Only HTTP and HTTPS are permitted.")

        # 2. Validate Hostname
        hostname = parsed.hostname
        if not hostname:
            raise URLValidationError("URL missing a valid domain hostname or IP address.")

        hostname = hostname.lower()

        # Block localhost explicit check
        if hostname == "localhost" or hostname.endswith(".localhost"):
            raise URLValidationError("Access to localhost is strictly prohibited.")

        # 3. Check direct IP literal
        if cls.is_ip_restricted(hostname):
            raise URLValidationError(f"Target IP address '{hostname}' is in a restricted network range.")

        port_part = f":{parsed.port}" if parsed.port and parsed.port not in (80, 443) else ""
        return scheme, hostname, port_part, parsed

    @classmethod
    def _assemble_normalized_url(cls, scheme: str, hostname: str, port_part: str, parsed) -> str:
        netloc = f"{hostname}{port_part}"
        path = parsed.path if parsed.path else "/"
        return urlunparse((
            scheme,
            netloc,
            path,
            parsed.params,
            parsed.query,
            ""  # Strip fragment
        ))

    @classmethod
    async def validate_and_normalize_url(cls, url: str, timeout: float = 5.0) -> str:
        """
        Asynchronously validate URL for SSRF security, correct scheme, and resolve host IP safety.
        Returns normalized URL if safe, or raises URLValidationError.
        """
        scheme, hostname, port_part, parsed = cls._validate_components(url)

        # 4. Asynchronously resolve DNS and check resolved IP addresses (prevents DNS Rebinding)
        resolved_ips = await cls.resolve_hostname_ips_async(hostname, timeout=timeout)
        if not resolved_ips:
            raise URLValidationError(f"Could not resolve any IP address for domain '{hostname}'.")

        for ip in resolved_ips:
            if cls.is_ip_restricted(ip):
                raise URLValidationError(
                    f"Domain '{hostname}' resolves to restricted IP address '{ip}'."
                )

        # 5. Normalize URL (strip credentials and fragments)
        return cls._assemble_normalized_url(scheme, hostname, port_part, parsed)

    @classmethod
    def validate_and_normalize_url_sync(cls, url: str) -> str:
        """
        Synchronous validation helper for non-async execution contexts.
        """
        scheme, hostname, port_part, parsed = cls._validate_components(url)

        # 4. Synchronously resolve DNS and check resolved IP addresses
        resolved_ips = cls.resolve_hostname_ips(hostname)
        if not resolved_ips:
            raise URLValidationError(f"Could not resolve any IP address for domain '{hostname}'.")

        for ip in resolved_ips:
            if cls.is_ip_restricted(ip):
                raise URLValidationError(
                    f"Domain '{hostname}' resolves to restricted IP address '{ip}'."
                )

        # 5. Normalize URL
        return cls._assemble_normalized_url(scheme, hostname, port_part, parsed)


# Alias for explicit async naming
SSRFSecurityValidator.validate_and_normalize_url_async = SSRFSecurityValidator.validate_and_normalize_url

