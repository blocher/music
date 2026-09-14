import requests
from django.conf import settings


class MusixmatchError(RuntimeError):
    pass


class MusixmatchPartnerAccessRequired(MusixmatchError):
    pass


class MusixmatchClient:
    """Read API verification plus an opt-in partner write hook.

    Musixmatch does not publish a general artist-write API. The write hook is
    disabled unless Musixmatch supplies a partner endpoint for the account.
    """

    def __init__(self, credentials: dict):
        self.credentials = credentials
        self.base_url = (credentials.get("api_base_url") or settings.MUSIXMATCH_API_BASE_URL).rstrip("/")

    def verify(self):
        api_key = self.credentials.get("api_key")
        if not api_key:
            raise MusixmatchError("An API key is required to verify Musixmatch access.")
        response = requests.get(
            f"{self.base_url}/track.search",
            params={"apikey": api_key, "q_track": "test", "page_size": 1},
            timeout=30,
        )
        if not response.ok:
            raise MusixmatchError(f"Musixmatch verification failed ({response.status_code}).")
        header = response.json().get("message", {}).get("header", {})
        if int(header.get("status_code", 0)) != 200:
            raise MusixmatchError(f"Musixmatch verification failed ({header.get('status_code', 'unknown')}).")
        return {"verified": True, "artist_id": self.credentials.get("artist_id", "")}

    def publish_synced_lyrics(self, payload: dict) -> dict:
        publish_path = self.credentials.get("publish_path", "").strip()
        partner_token = self.credentials.get("partner_token", "").strip()
        if not publish_path or not partner_token:
            raise MusixmatchPartnerAccessRequired(
                "Musixmatch partner write access is not configured. The timed lyric package is ready for Musixmatch Pro."
            )
        url = publish_path if publish_path.startswith("https://") else f"{self.base_url}/{publish_path.lstrip('/')}"
        response = requests.post(
            url,
            headers={"Authorization": f"Bearer {partner_token}", "Content-Type": "application/json"},
            json=payload,
            timeout=60,
        )
        if not response.ok:
            raise MusixmatchError(f"Musixmatch delivery failed ({response.status_code}): {response.text[:500]}")
        return response.json()
