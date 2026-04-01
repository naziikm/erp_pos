import httpx
import logging
from app.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()


class ERPConnectionError(Exception):
    """ERP server is unreachable."""
    pass


class ERPAuthError(Exception):
    """ERP credentials rejected."""
    pass


class ERPTimeoutError(Exception):
    """ERP API call timed out."""
    pass


class ERPServerError(Exception):
    """ERP returned a 5xx error."""
    def __init__(self, status_code: int, detail: str = ""):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"ERP server error {status_code}: {detail}")


class ERPClient:
    """HTTP client for communicating with ERPNext/Frappe REST API."""

    MAX_RETRIES = 3
    BACKOFF_FACTORS = [1, 2, 4]  # seconds

    def __init__(self):
        self.base_url = settings.ERP_BASE_URL.rstrip("/")
        self.timeout = settings.ERP_REQUEST_TIMEOUT_SECONDS
        self.headers = {
            "Authorization": f"token {settings.ERP_API_KEY}:{settings.ERP_API_SECRET}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _get_client(self) -> httpx.Client:
        return httpx.Client(
            base_url=self.base_url,
            headers=self.headers,
            timeout=self.timeout,
        )

    def _request_with_retry(self, method: str, url: str, **kwargs) -> httpx.Response:
        """Execute an HTTP request with retry on 5xx and timeout errors."""
        last_exception = None

        for attempt in range(self.MAX_RETRIES):
            try:
                with self._get_client() as client:
                    response = client.request(method, url, **kwargs)

                logger.debug(
                    "ERP %s %s → %s (attempt %d)",
                    method, url, response.status_code, attempt + 1
                )

                if response.status_code == 401 or response.status_code == 403:
                    raise ERPAuthError(
                        f"ERP authentication failed: {response.status_code} - {response.text[:200]}"
                    )

                if response.status_code >= 500:
                    last_exception = ERPServerError(response.status_code, response.text[:500])
                    if attempt < self.MAX_RETRIES - 1:
                        import time
                        time.sleep(self.BACKOFF_FACTORS[attempt])
                        continue
                    raise last_exception

                return response

            except httpx.ConnectError as e:
                last_exception = ERPConnectionError(f"Cannot connect to ERP: {e}")
                if attempt < self.MAX_RETRIES - 1:
                    import time
                    time.sleep(self.BACKOFF_FACTORS[attempt])
                    continue
                raise last_exception from e

            except httpx.TimeoutException as e:
                last_exception = ERPTimeoutError(f"ERP request timed out: {e}")
                if attempt < self.MAX_RETRIES - 1:
                    import time
                    time.sleep(self.BACKOFF_FACTORS[attempt])
                    continue
                raise last_exception from e

            except (ERPAuthError, ERPServerError):
                raise

        raise last_exception  # type: ignore

    def get(self, url: str, params: dict | None = None) -> httpx.Response:
        return self._request_with_retry("GET", url, params=params)

    def post(self, url: str, json: dict | None = None) -> httpx.Response:
        return self._request_with_retry("POST", url, json=json)

    def put(self, url: str, json: dict | None = None) -> httpx.Response:
        return self._request_with_retry("PUT", url, json=json)

    def head(self, url: str) -> httpx.Response:
        return self._request_with_retry("HEAD", url)

    def check_connectivity(self) -> bool:
        """Quick health check — HEAD request with short timeout."""
        try:
            with httpx.Client(
                base_url=self.base_url,
                headers=self.headers,
                timeout=5,
            ) as client:
                response = client.head("/")
            return response.status_code < 500
        except Exception:
            return False


def get_erp_client() -> ERPClient:
    return ERPClient()
