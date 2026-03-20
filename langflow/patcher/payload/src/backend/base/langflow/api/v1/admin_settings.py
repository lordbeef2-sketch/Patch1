from __future__ import annotations

from http import HTTPStatus
from pathlib import Path
from typing import Any
from typing import Annotated
from urllib import error, parse, request

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


class IntegrationSettingsResponse(BaseModel):
    langflow_base_url: str
    langflow_auth_token_configured: bool
    langflow_timeout_seconds: int
    langflow_retry_count: int
    langflow_retry_backoff_seconds: int
    langflow_default_flow_id: str | None
    langflow_default_project_id: str | None
    owui_base_url: str
    owui_auth_token_configured: bool
    owui_timeout_seconds: int
    owui_retry_count: int
    owui_retry_backoff_seconds: int
    owui_failure_policy: str
    owui_sync_enabled: bool
    owui_sync_dry_run: bool
    owui_sync_verbose_logs: bool
    allowed_origins_csv: str
    enforce_host_allowlist: bool
    host_allowlist_csv: str
    restart_required: bool = True


class IntegrationSettingsUpdateRequest(BaseModel):
    langflow_base_url: str = Field(min_length=1)
    langflow_auth_token: str | None = Field(default=None)
    langflow_timeout_seconds: int = Field(ge=1, le=300)
    langflow_retry_count: int = Field(ge=0, le=10)
    langflow_retry_backoff_seconds: int = Field(ge=0, le=60)
    langflow_default_flow_id: str | None = Field(default=None)
    langflow_default_project_id: str | None = Field(default=None)
    owui_base_url: str = Field(min_length=1)
    owui_auth_token: str | None = Field(default=None)
    owui_timeout_seconds: int = Field(ge=1, le=300)
    owui_retry_count: int = Field(ge=0, le=10)
    owui_retry_backoff_seconds: int = Field(ge=0, le=60)
    owui_failure_policy: str = Field(default="queue", min_length=1)
    owui_sync_enabled: bool = Field(default=True)
    owui_sync_dry_run: bool = Field(default=False)
    owui_sync_verbose_logs: bool = Field(default=False)
    allowed_origins_csv: str = Field(default="")
    enforce_host_allowlist: bool = Field(default=False)
    host_allowlist_csv: str = Field(default="127.0.0.1,localhost")


class IntegrationConnectionCheck(BaseModel):
    target: str
    status: str
    http_status: int | None = None
    url: str
    detail: str


class IntegrationConnectionTestResponse(BaseModel):
    status: str
    checks: list[IntegrationConnectionCheck]


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


def _load_langflow_env() -> dict[str, str]:
    env_path = Path.cwd() / ".env"
    existing: dict[str, str] = {}

    if not env_path.exists():
        return existing

    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        existing[key.strip()] = value

    return existing


def _parse_bool(raw: str | None, default: bool = False) -> bool:
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _parse_int(raw: str | None, default: int) -> int:
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _normalize_url(name: str, value: str) -> str:
    normalized = value.strip().rstrip("/")
    parsed = parse.urlparse(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(status_code=400, detail=f"{name} must be a valid http(s) URL")
    return normalized


def _connectivity_check(target: str, base_url: str, timeout_seconds: int) -> IntegrationConnectionCheck:
    health_paths = (
        "/health_check",
        "/api/v1/monitor/health",
        "/api/v1/health",
    )
    for path in health_paths:
        url = f"{base_url}{path}"
        req = request.Request(url=url, method="GET")
        try:
            with request.urlopen(req, timeout=timeout_seconds) as response:  # noqa: S310
                return IntegrationConnectionCheck(
                    target=target,
                    status="PASS",
                    http_status=int(response.status),
                    url=url,
                    detail="Connection successful",
                )
        except error.HTTPError as exc:
            if exc.code < HTTPStatus.INTERNAL_SERVER_ERROR:
                return IntegrationConnectionCheck(
                    target=target,
                    status="PASS",
                    http_status=exc.code,
                    url=url,
                    detail="Endpoint reachable (non-2xx response)",
                )
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)

    return IntegrationConnectionCheck(
        target=target,
        status="FAIL",
        url=base_url,
        detail=last_error if "last_error" in locals() else "Connection failed",
    )


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


@router.get("/integrations", response_model=IntegrationSettingsResponse)
async def get_integration_settings(
    current_user: Annotated[User, Depends(get_current_active_superuser)],
):
    _ = current_user
    env = _load_langflow_env()
    settings = get_settings_service().settings

    default_langflow_url = f"http://{settings.host}:{settings.port}"
    return IntegrationSettingsResponse(
        langflow_base_url=env.get("LANGFLOW_PUBLIC_BASE_URL", default_langflow_url),
        langflow_auth_token_configured=bool(env.get("LANGFLOW_API_TOKEN")),
        langflow_timeout_seconds=_parse_int(env.get("LANGFLOW_REQUEST_TIMEOUT_SECONDS"), 30),
        langflow_retry_count=_parse_int(env.get("LANGFLOW_RETRY_COUNT"), 2),
        langflow_retry_backoff_seconds=_parse_int(env.get("LANGFLOW_RETRY_BACKOFF_SECONDS"), 1),
        langflow_default_flow_id=env.get("LANGFLOW_DEFAULT_FLOW_ID"),
        langflow_default_project_id=env.get("LANGFLOW_DEFAULT_PROJECT_ID"),
        owui_base_url=env.get("OWUI_BASE_URL", "http://127.0.0.1:8081"),
        owui_auth_token_configured=bool(env.get("OWUI_API_TOKEN")),
        owui_timeout_seconds=_parse_int(env.get("OWUI_TIMEOUT_SECONDS"), 30),
        owui_retry_count=_parse_int(env.get("OWUI_RETRY_COUNT"), 2),
        owui_retry_backoff_seconds=_parse_int(env.get("OWUI_RETRY_BACKOFF_SECONDS"), 1),
        owui_failure_policy=env.get("OWUI_FAILURE_POLICY", "queue"),
        owui_sync_enabled=_parse_bool(env.get("OWUI_SYNC_ENABLED"), True),
        owui_sync_dry_run=_parse_bool(env.get("OWUI_SYNC_DRY_RUN"), False),
        owui_sync_verbose_logs=_parse_bool(env.get("OWUI_SYNC_VERBOSE_LOGS"), False),
        allowed_origins_csv=env.get("INTEGRATION_ALLOWED_ORIGINS", ""),
        enforce_host_allowlist=_parse_bool(env.get("INTEGRATION_ENFORCE_HOST_ALLOWLIST"), False),
        host_allowlist_csv=env.get("INTEGRATION_HOST_ALLOWLIST", "127.0.0.1,localhost"),
    )


@router.put("/integrations", response_model=IntegrationSettingsResponse)
async def update_integration_settings(
    payload: IntegrationSettingsUpdateRequest,
    current_user: Annotated[User, Depends(get_current_active_superuser)],
):
    _ = current_user
    langflow_base_url = _normalize_url("langflow_base_url", payload.langflow_base_url)
    owui_base_url = _normalize_url("owui_base_url", payload.owui_base_url)

    _upsert_langflow_env(
        {
            "LANGFLOW_PUBLIC_BASE_URL": langflow_base_url,
            "LANGFLOW_API_TOKEN": payload.langflow_auth_token,
            "LANGFLOW_REQUEST_TIMEOUT_SECONDS": str(payload.langflow_timeout_seconds),
            "LANGFLOW_RETRY_COUNT": str(payload.langflow_retry_count),
            "LANGFLOW_RETRY_BACKOFF_SECONDS": str(payload.langflow_retry_backoff_seconds),
            "LANGFLOW_DEFAULT_FLOW_ID": payload.langflow_default_flow_id,
            "LANGFLOW_DEFAULT_PROJECT_ID": payload.langflow_default_project_id,
            "OWUI_BASE_URL": owui_base_url,
            "OWUI_API_TOKEN": payload.owui_auth_token,
            "OWUI_TIMEOUT_SECONDS": str(payload.owui_timeout_seconds),
            "OWUI_RETRY_COUNT": str(payload.owui_retry_count),
            "OWUI_RETRY_BACKOFF_SECONDS": str(payload.owui_retry_backoff_seconds),
            "OWUI_FAILURE_POLICY": payload.owui_failure_policy,
            "OWUI_SYNC_ENABLED": str(payload.owui_sync_enabled).lower(),
            "OWUI_SYNC_DRY_RUN": str(payload.owui_sync_dry_run).lower(),
            "OWUI_SYNC_VERBOSE_LOGS": str(payload.owui_sync_verbose_logs).lower(),
            "INTEGRATION_ALLOWED_ORIGINS": payload.allowed_origins_csv,
            "INTEGRATION_ENFORCE_HOST_ALLOWLIST": str(payload.enforce_host_allowlist).lower(),
            "INTEGRATION_HOST_ALLOWLIST": payload.host_allowlist_csv,
        }
    )

    return await get_integration_settings(current_user)


@router.post("/integrations/test", response_model=IntegrationConnectionTestResponse)
async def test_integration_settings(
    current_user: Annotated[User, Depends(get_current_active_superuser)],
):
    _ = current_user
    settings = await get_integration_settings(current_user)
    checks = [
        _connectivity_check("langflow", settings.langflow_base_url, settings.langflow_timeout_seconds),
        _connectivity_check("owui", settings.owui_base_url, settings.owui_timeout_seconds),
    ]
    status = "PASS" if all(check.status == "PASS" for check in checks) else "FAIL"
    return IntegrationConnectionTestResponse(status=status, checks=checks)


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
