import time
from collections.abc import Iterator
from urllib.parse import urljoin

import requests
from django.conf import settings


class SunoError(RuntimeError):
    pass


class SunoClient:
    """Low-volume adapter for Suno's private web API.

    Keep every reverse-engineered detail in this module. Callers consume tolerant,
    normalized dictionaries and do not depend on upstream response shapes.
    """

    clerk_version = "5.117.0"

    def __init__(self, credentials: dict, session: requests.Session | None = None):
        self.credentials = credentials
        self.session = session or requests.Session()
        self.base_url = settings.SUNO_API_BASE_URL.rstrip("/") + "/"
        self.auth_url = settings.SUNO_AUTH_BASE_URL.rstrip("/") + "/"
        self.jwt = credentials.get("access_token", "")

    def _exchange_token(self) -> str:
        session_id = self.credentials.get("session_id")
        cookie = self.credentials.get("cookie")
        if not session_id or not cookie:
            raise SunoError("Suno session ID and cookie are required")
        url = urljoin(
            self.auth_url,
            f"v1/client/sessions/{session_id}/tokens?_clerk_js_version={self.clerk_version}",
        )
        response = self.session.post(
            url,
            headers={"Cookie": cookie, "Content-Type": "application/x-www-form-urlencoded"},
            timeout=30,
        )
        if not response.ok:
            raise SunoError(f"Suno session refresh failed ({response.status_code})")
        self.jwt = response.json().get("jwt", "")
        if not self.jwt:
            raise SunoError("Suno session refresh returned no token")
        return self.jwt

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        if not self.jwt:
            self._exchange_token()
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {self.jwt}"
        headers.setdefault("Accept", "application/json")
        url = urljoin(self.base_url, path.lstrip("/"))
        response = self.session.request(method, url, headers=headers, timeout=45, **kwargs)
        if response.status_code == 401:
            headers["Authorization"] = f"Bearer {self._exchange_token()}"
            response = self.session.request(method, url, headers=headers, timeout=45, **kwargs)
        if not response.ok:
            detail = response.text[:300]
            raise SunoError(f"Suno request failed ({response.status_code}): {detail}")
        return response

    def account(self) -> dict:
        response = self._request("GET", "/api/billing/info/")
        data = response.json()
        return {
            "credits_left": data.get("total_credits_left", data.get("credits_left")),
            "monthly_limit": data.get("monthly_limit"),
            "monthly_usage": data.get("monthly_usage"),
            "period": data.get("period", ""),
            "active": data.get("is_active"),
            "raw": data,
        }

    def playlists(self) -> Iterator[dict]:
        page = 1
        while True:
            response = self._request(
                "GET",
                "/api/playlist/me",
                params={"page": page, "trashed": "false", "share_list": "false"},
            )
            data = response.json()
            playlists = data.get("playlists", data if isinstance(data, list) else [])
            if not playlists:
                break
            yield from playlists
            next_cursor = data.get("next_cursor") if isinstance(data, dict) else None
            if not next_cursor and len(playlists) < 20:
                break
            page += 1
            time.sleep(0.65)

    def playlist(self, playlist_id: str) -> dict:
        return self._request("GET", f"/api/playlist/{playlist_id}/").json()

    def clips(self) -> Iterator[dict]:
        page = 1
        while True:
            data = self._request("GET", "/api/feed/v2", params={"page": page}).json()
            clips = data.get("clips", data if isinstance(data, list) else [])
            if not clips:
                break
            yield from clips
            page += 1
            time.sleep(0.65)

    def aligned_lyrics(self, clip_id: str) -> dict:
        return self._request("GET", f"/api/gen/{clip_id}/aligned_lyrics/v2/").json()

    def wav_url(self, clip_id: str) -> str:
        data = self._request("GET", f"/api/gen/{clip_id}/wav_file/").json()
        url = data.get("url") or data.get("wav_file_url") or data.get("audio_url")
        if not url:
            raise SunoError("Suno did not return a WAV download URL")
        return url

    def download(self, url: str) -> tuple[bytes, str]:
        response = self.session.get(url, timeout=180)
        if not response.ok:
            raise SunoError(f"Audio download failed ({response.status_code})")
        return response.content, response.headers.get("Content-Type", "application/octet-stream")
