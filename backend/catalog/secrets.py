import base64
import hashlib
import json

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from .models import IntegrationCredential


def _fernet() -> Fernet:
    key = settings.CREDENTIAL_ENCRYPTION_KEY
    if not key:
        if not settings.DEBUG:
            raise ImproperlyConfigured("CREDENTIAL_ENCRYPTION_KEY is required outside development")
        key = base64.urlsafe_b64encode(hashlib.sha256(settings.SECRET_KEY.encode()).digest()).decode()
    return Fernet(key.encode())


def save_credentials(service: str, payload: dict, display_label: str = "") -> IntegrationCredential:
    try:
        existing = load_credentials(service)
    except IntegrationCredential.DoesNotExist:
        existing = {}
    merged = {**existing, **{key: value for key, value in payload.items() if value is not None and value != ""}}
    encoded = _fernet().encrypt(json.dumps(merged).encode()).decode()
    credential, _ = IntegrationCredential.objects.update_or_create(
        service=service,
        defaults={"encrypted_payload": encoded, "display_label": display_label, "last_error": ""},
    )
    return credential


def load_credentials(service: str) -> dict:
    credential = IntegrationCredential.objects.get(service=service)
    try:
        return json.loads(_fernet().decrypt(credential.encrypted_payload.encode()).decode())
    except (InvalidToken, json.JSONDecodeError) as exc:
        raise ImproperlyConfigured(f"Stored {service} credentials cannot be decrypted") from exc


def masked_credentials(service: str) -> dict:
    try:
        credential = IntegrationCredential.objects.get(service=service)
        payload = load_credentials(service)
    except IntegrationCredential.DoesNotExist:
        return {"connected": False, "service": service}

    visible = {}
    for key, value in payload.items():
        if key in {
            "account_email",
            "environment",
            "redirect_uri",
            "monthly_download_limit",
            "api_base_url",
            "create_release_path",
        }:
            visible[key] = value
        elif value:
            visible[key] = f"••••{str(value)[-4:]}"
    return {
        "connected": True,
        "service": service,
        "display_label": credential.display_label,
        "last_verified_at": credential.last_verified_at,
        "last_error": credential.last_error,
        "values": visible,
    }
