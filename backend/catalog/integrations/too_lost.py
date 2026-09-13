from urllib.parse import urljoin

import requests
from django.conf import settings


class TooLostError(RuntimeError):
    pass


class TooLostClient:
    """Too Lost REST adapter.

    Endpoint overrides keep the beta API configurable without changing release
    orchestration code when Too Lost promotes a new version.
    """

    def __init__(self, credentials: dict, session: requests.Session | None = None):
        self.credentials = credentials
        self.session = session or requests.Session()
        self.base_url = credentials.get("api_base_url", settings.TOO_LOST_API_BASE_URL).rstrip("/") + "/"

    def _headers(self) -> dict:
        token = self.credentials.get("access_token") or self.credentials.get("api_key")
        if not token:
            raise TooLostError("Too Lost access token is required")
        return {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    def request(self, method: str, path: str, **kwargs) -> dict:
        response = self.session.request(
            method,
            urljoin(self.base_url, path.lstrip("/")),
            headers={**self._headers(), **kwargs.pop("headers", {})},
            timeout=60,
            **kwargs,
        )
        if not response.ok:
            raise TooLostError(f"Too Lost request failed ({response.status_code}): {response.text[:500]}")
        return response.json() if response.content else {}

    def releases(self) -> dict:
        return self.request("GET", self.credentials.get("releases_path", "/v1/releases"))

    def create_release(self, payload: dict) -> dict:
        return self.request("POST", self.credentials.get("create_release_path", "/v2/releases"), json=payload)

    def release(self, release_id: str) -> dict:
        path = self.credentials.get("release_detail_path", "/v2/releases/{id}").format(id=release_id)
        return self.request("GET", path)

    def take_down(self, release_id: str) -> dict:
        path = self.credentials.get("takedown_path", "/v2/releases/{id}/takedown").format(id=release_id)
        return self.request("POST", path, json={})
