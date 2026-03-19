from __future__ import annotations

from pathlib import Path
from typing import Annotated

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import pkcs12
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from langflow.services.auth.utils import get_current_active_superuser
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_settings_service

router = APIRouter(tags=["Admin Settings"], prefix="/admin/settings")


class HTTPSSettingsResponse(BaseModel):
    ssl_enabled: bool
    ssl_cert_file: str | None
    ssl_key_file: str | None
    host: str
    port: int
    access_secure_cookie: bool
    refresh_secure_cookie: bool
    https_hsts_enabled: bool
    https_hsts_max_age: int
    https_hsts_include_subdomains: bool
    https_hsts_preload: bool
    restart_required: bool = True


class HTTPSSettingsUpdateRequest(BaseModel):
    ssl_enabled: bool
    ssl_cert_file: str | None = Field(default=None)
    ssl_key_file: str | None = Field(default=None)
    host: str | None = Field(default=None, min_length=1)
    port: int | None = Field(default=None, ge=1, le=65535)
    https_hsts_enabled: bool | None = Field(default=None)
    https_hsts_max_age: int | None = Field(default=None, ge=0, le=63072000)
    https_hsts_include_subdomains: bool | None = Field(default=None)
    https_hsts_preload: bool | None = Field(default=None)


class HTTPSUploadResponse(BaseModel):
    file_type: str
    file_path: str
    ssl_cert_file: str | None = None
    ssl_key_file: str | None = None


class SSOSettingsResponse(BaseModel):
    sso_enabled: bool


class SSOSettingsUpdateRequest(BaseModel):
    sso_enabled: bool


def _upsert_langflow_env(updates: dict[str, str | None]) -> None:
    env_path = Path.cwd() / ".env"
    existing: dict[str, str] = {}

    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            existing[key.strip()] = value

    for key, value in updates.items():
        if value is None or value == "":
            existing.pop(key, None)
        else:
            existing[key] = str(value)

    lines = [f"{k}={v}" for k, v in sorted(existing.items())]
    content = "\n".join(lines)
    if content:
        content += "\n"
    env_path.write_text(content, encoding="utf-8")


def _get_certs_dir() -> Path:
    settings = get_settings_service().settings
    if settings.config_dir:
        base_dir = Path(settings.config_dir).expanduser()
    else:
        base_dir = Path.home() / ".langflow"
    certs_dir = base_dir / "certs"
    certs_dir.mkdir(parents=True, exist_ok=True)
    return certs_dir


def _validate_ssl_paths(cert_file: str, key_file: str) -> tuple[str, str]:
    cert = Path(cert_file).expanduser()
    key = Path(key_file).expanduser()

    if not cert.exists() or not cert.is_file():
        raise HTTPException(status_code=400, detail=f"SSL certificate file not found: {cert}")
    if not key.exists() or not key.is_file():
        raise HTTPException(status_code=400, detail=f"SSL key file not found: {key}")

    return str(cert), str(key)


@router.get("/sso", response_model=SSOSettingsResponse)
async def get_sso_settings(
    current_user: Annotated[User, Depends(get_current_active_superuser)],
):
    _ = current_user
    auth_settings = get_settings_service().auth_settings
    return SSOSettingsResponse(sso_enabled=auth_settings.SSO_ENABLED)


@router.put("/sso", response_model=SSOSettingsResponse)
async def update_sso_settings(
    payload: SSOSettingsUpdateRequest,
    current_user: Annotated[User, Depends(get_current_active_superuser)],
):
    _ = current_user
    auth_settings = get_settings_service().auth_settings
    # Keep this mutable from admin settings so SSO can be toggled without env edits.
    auth_settings.SSO_ENABLED = payload.sso_enabled
    return SSOSettingsResponse(sso_enabled=auth_settings.SSO_ENABLED)


@router.get("/https", response_model=HTTPSSettingsResponse)
async def get_https_settings(
    current_user: Annotated[User, Depends(get_current_active_superuser)],
):
    _ = current_user
    settings_service = get_settings_service()
    settings = settings_service.settings
    auth_settings = settings_service.auth_settings

    ssl_enabled = bool(settings.ssl_cert_file and settings.ssl_key_file)
    return HTTPSSettingsResponse(
        ssl_enabled=ssl_enabled,
        ssl_cert_file=settings.ssl_cert_file,
        ssl_key_file=settings.ssl_key_file,
        host=settings.host,
        port=settings.port,
        access_secure_cookie=auth_settings.ACCESS_SECURE,
        refresh_secure_cookie=auth_settings.REFRESH_SECURE,
        https_hsts_enabled=settings.https_hsts_enabled,
        https_hsts_max_age=settings.https_hsts_max_age,
        https_hsts_include_subdomains=settings.https_hsts_include_subdomains,
        https_hsts_preload=settings.https_hsts_preload,
    )


@router.put("/https", response_model=HTTPSSettingsResponse)
async def update_https_settings(
    payload: HTTPSSettingsUpdateRequest,
    current_user: Annotated[User, Depends(get_current_active_superuser)],
):
    _ = current_user
    settings_service = get_settings_service()
    settings = settings_service.settings
    auth_settings = settings_service.auth_settings

    next_host = payload.host if payload.host is not None else settings.host
    next_port = payload.port if payload.port is not None else settings.port

    cert_file = payload.ssl_cert_file or settings.ssl_cert_file
    key_file = payload.ssl_key_file or settings.ssl_key_file

    if payload.ssl_enabled:
        if not cert_file or not key_file:
            raise HTTPException(
                status_code=400,
                detail="Enabling HTTPS requires both ssl_cert_file and ssl_key_file.",
            )
        cert_file, key_file = _validate_ssl_paths(cert_file, key_file)
        settings.update_settings(
            ssl_cert_file=cert_file,
            ssl_key_file=key_file,
            host=next_host,
            port=next_port,
        )
        # Ensure auth cookies are marked secure when HTTPS is enabled.
        auth_settings.set("ACCESS_SECURE", True)
        auth_settings.set("REFRESH_SECURE", True)
    else:
        settings.update_settings(
            ssl_cert_file=None,
            ssl_key_file=None,
            host=next_host,
            port=next_port,
        )
        # Keep behavior consistent for non-TLS local runs.
        auth_settings.set("ACCESS_SECURE", False)
        auth_settings.set("REFRESH_SECURE", False)

    settings.update_settings(
        https_hsts_enabled=(
            payload.https_hsts_enabled
            if payload.https_hsts_enabled is not None
            else settings.https_hsts_enabled
        ),
        https_hsts_max_age=(
            payload.https_hsts_max_age
            if payload.https_hsts_max_age is not None
            else settings.https_hsts_max_age
        ),
        https_hsts_include_subdomains=(
            payload.https_hsts_include_subdomains
            if payload.https_hsts_include_subdomains is not None
            else settings.https_hsts_include_subdomains
        ),
        https_hsts_preload=(
            payload.https_hsts_preload
            if payload.https_hsts_preload is not None
            else settings.https_hsts_preload
        ),
    )

    _upsert_langflow_env(
        {
            "LANGFLOW_SSL_CERT_FILE": settings.ssl_cert_file,
            "LANGFLOW_SSL_KEY_FILE": settings.ssl_key_file,
            "LANGFLOW_HOST": settings.host,
            "LANGFLOW_PORT": str(settings.port),
            "LANGFLOW_HTTPS_HSTS_ENABLED": str(settings.https_hsts_enabled).lower(),
            "LANGFLOW_HTTPS_HSTS_MAX_AGE": str(settings.https_hsts_max_age),
            "LANGFLOW_HTTPS_HSTS_INCLUDE_SUBDOMAINS": str(settings.https_hsts_include_subdomains).lower(),
            "LANGFLOW_HTTPS_HSTS_PRELOAD": str(settings.https_hsts_preload).lower(),
        }
    )

    return HTTPSSettingsResponse(
        ssl_enabled=payload.ssl_enabled,
        ssl_cert_file=settings.ssl_cert_file,
        ssl_key_file=settings.ssl_key_file,
        host=settings.host,
        port=settings.port,
        access_secure_cookie=auth_settings.ACCESS_SECURE,
        refresh_secure_cookie=auth_settings.REFRESH_SECURE,
        https_hsts_enabled=settings.https_hsts_enabled,
        https_hsts_max_age=settings.https_hsts_max_age,
        https_hsts_include_subdomains=settings.https_hsts_include_subdomains,
        https_hsts_preload=settings.https_hsts_preload,
    )


@router.post("/https/upload", response_model=HTTPSUploadResponse)
async def upload_https_file(
    current_user: Annotated[User, Depends(get_current_active_superuser)],
    file_type: Annotated[str, Form()],
    password: Annotated[str | None, Form()] = None,
    file: UploadFile = File(...),
):
    _ = current_user
    if file_type != "p12":
        raise HTTPException(status_code=400, detail="file_type must be 'p12'")

    certs_dir = _get_certs_dir()
    # 2 MB hard limit for certificate uploads.
    max_size = 2 * 1024 * 1024
    file.file.seek(0, 2)
    size = file.file.tell()
    file.file.seek(0)
    if size > max_size:
        raise HTTPException(status_code=400, detail="Uploaded file exceeds 2 MB")

    p12_bytes = file.file.read()
    if not p12_bytes:
        raise HTTPException(status_code=400, detail="Uploaded PKCS#12 file is empty")

    password_bytes = password.encode("utf-8") if password else None
    try:
        private_key, certificate, additional_certificates = pkcs12.load_key_and_certificates(
            p12_bytes,
            password_bytes,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail="Unable to parse PKCS#12 file. Check file format, password, and that the bundle includes your server certificate chain.",
        ) from exc

    if certificate is None or private_key is None:
        raise HTTPException(
            status_code=400,
            detail="PKCS#12 must contain both the server certificate and its private key. A CA certificate bundle alone is not sufficient.",
        )

    cert_path = certs_dir / "langflow-cert-from-p12.pem"
    key_path = certs_dir / "langflow-key-from-p12.pem"

    cert_bytes = certificate.public_bytes(serialization.Encoding.PEM)
    if additional_certificates:
        for ca_cert in additional_certificates:
            cert_bytes += ca_cert.public_bytes(serialization.Encoding.PEM)

    key_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )

    cert_path.write_bytes(cert_bytes)
    key_path.write_bytes(key_bytes)

    settings = get_settings_service().settings
    settings.update_settings(
        ssl_cert_file=str(cert_path),
        ssl_key_file=str(key_path),
    )

    _upsert_langflow_env(
        {
            "LANGFLOW_SSL_CERT_FILE": str(cert_path),
            "LANGFLOW_SSL_KEY_FILE": str(key_path),
        }
    )

    return HTTPSUploadResponse(
        file_type=file_type,
        file_path=str(cert_path),
        ssl_cert_file=str(cert_path),
        ssl_key_file=str(key_path),
    )
