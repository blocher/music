import base64
import mimetypes
from pathlib import Path

import requests
from django.conf import settings


class OpenAIError(RuntimeError):
    pass


class OpenAIClient:
    def __init__(self, credentials: dict):
        self.credentials = credentials
        self.base_url = credentials.get("api_base_url") or settings.OPENAI_API_BASE_URL

    @property
    def headers(self):
        headers = {"Authorization": f"Bearer {self.credentials.get('api_key', '')}"}
        if self.credentials.get("organization"):
            headers["OpenAI-Organization"] = self.credentials["organization"]
        if self.credentials.get("project"):
            headers["OpenAI-Project"] = self.credentials["project"]
        return headers

    def _raise(self, response):
        if response.ok:
            return
        try:
            detail = response.json().get("error", {}).get("message") or response.text
        except ValueError:
            detail = response.text
        raise OpenAIError(f"OpenAI request failed ({response.status_code}): {detail[:500]}")

    def verify(self):
        response = requests.get(f"{self.base_url.rstrip('/')}/models", headers=self.headers, timeout=30)
        self._raise(response)
        return {"models_available": len(response.json().get("data", []))}

    def generate_description(self, *, title: str, lyrics: str, style: str, existing: str = "") -> str:
        prompt = (
            "Write a warm, casual 2-4 sentence music description. Do not invent credits, people, "
            "release facts, or claims. Use the lyrics and style notes as evidence. If an existing description "
            "is supplied, preserve useful facts while improving it. Return only the finished description.\n\n"
            f"Title: {title}\nStyle notes: {style or 'Not supplied'}\n"
            f"Existing description: {existing or 'Not supplied'}\nLyrics:\n{lyrics[:16000]}"
        )
        response = requests.post(
            f"{self.base_url.rstrip('/')}/responses",
            headers={**self.headers, "Content-Type": "application/json"},
            json={"model": self.credentials.get("text_model", "gpt-5-mini"), "input": prompt},
            timeout=120,
        )
        self._raise(response)
        payload = response.json()
        if payload.get("output_text"):
            return payload["output_text"].strip()
        for item in payload.get("output", []):
            for content in item.get("content", []):
                if content.get("type") == "output_text" and content.get("text"):
                    return content["text"].strip()
        raise OpenAIError("OpenAI returned no description text.")

    def transcribe(self, file_field, *, lyrics: str = "") -> dict:
        file_field.open("rb")
        try:
            response = requests.post(
                f"{self.base_url.rstrip('/')}/audio/transcriptions",
                headers=self.headers,
                data={
                    "model": self.credentials.get("transcription_model", "whisper-1"),
                    "response_format": "verbose_json",
                    "timestamp_granularities[]": "word",
                    "prompt": lyrics[:2000],
                },
                files={"file": (Path(file_field.name).name, file_field.file, mimetypes.guess_type(file_field.name)[0] or "application/octet-stream")},
                timeout=600,
            )
        finally:
            file_field.close()
        self._raise(response)
        return response.json()

    def generate_image(self, *, prompt: str, source_image=None) -> tuple[bytes, str]:
        model = self.credentials.get("image_model", "gpt-image-2")
        full_prompt = (
            "Create square album artwork suitable for a family-friendly music catalog. "
            "Do not add artist or song text unless explicitly requested. " + prompt
        )
        if source_image:
            source_image.seek(0)
            response = requests.post(
                f"{self.base_url.rstrip('/')}/images/edits",
                headers=self.headers,
                data={"model": model, "prompt": full_prompt, "size": "1024x1024", "quality": "medium"},
                files={"image": (source_image.name, source_image, source_image.content_type)},
                timeout=600,
            )
        else:
            response = requests.post(
                f"{self.base_url.rstrip('/')}/images/generations",
                headers={**self.headers, "Content-Type": "application/json"},
                json={"model": model, "prompt": full_prompt, "size": "1024x1024", "quality": "medium"},
                timeout=600,
            )
        self._raise(response)
        image = (response.json().get("data") or [{}])[0]
        if image.get("b64_json"):
            return base64.b64decode(image["b64_json"]), "png"
        if image.get("url"):
            download = requests.get(image["url"], timeout=120)
            self._raise(download)
            return download.content, "png"
        raise OpenAIError("OpenAI returned no image.")
