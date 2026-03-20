from __future__ import annotations

import argparse
import ast
import datetime as _dt
import shutil
import sys
import zipfile
from pathlib import Path


PATCH_ID = "owui-admin-console-v1"
BRAND_NAME = "IMCE AI Interface Aide"

SCRIPT_DIR = Path(__file__).resolve().parent
PATCHER_ROOT = SCRIPT_DIR.parent
PAYLOAD_DIR = PATCHER_ROOT / "payload"
BACKUPS_DIR = PATCHER_ROOT / "backups"


def _die(msg: str, code: int = 2) -> None:
    print(msg, file=sys.stderr)
    raise SystemExit(code)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def _read_bytes(path: Path) -> bytes:
    return path.read_bytes()


def _write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def _is_png(path: Path) -> bool:
    try:
        header = path.read_bytes()[:8]
    except Exception:
        return False
    return header == b"\x89PNG\r\n\x1a\n"


def _find_open_webui_dir(open_webui_dir: str | None, site_packages: str | None) -> Path:
    if open_webui_dir:
        p = Path(open_webui_dir).expanduser().resolve()
        if p.is_dir() and (p / "__init__.py").exists():
            return p
        _die(f"open_webui dir not found or invalid: {p}")

    if site_packages:
        sp = Path(site_packages).expanduser().resolve()
        cand = sp / "open_webui"
        if cand.is_dir() and (cand / "__init__.py").exists():
            return cand
        _die(f"open_webui not found under site-packages: {cand}")

    # Best path: run this from inside the target environment.
    # Do NOT import open_webui (can have side effects / fail if env config is partial).
    for entry in sys.path:
        if not entry:
            continue
        try:
            base = Path(entry).expanduser().resolve()
        except Exception:
            continue
        cand = base / "open_webui"
        if cand.is_dir() and (cand / "__init__.py").exists():
            return cand

    # Fallback: if this patcher folder is copied next to a Python env,
    # detect common site-packages layouts without relying on active interpreter.
    workspace_root = PATCHER_ROOT.parent
    fallback_candidates = [
        workspace_root / "Lib" / "site-packages" / "open_webui",  # Windows venv/conda
        workspace_root / "lib" / "site-packages" / "open_webui",  # Some Unix layouts
    ]
    fallback_candidates.extend(
        p / "site-packages" / "open_webui" for p in (workspace_root / "lib").glob("python*")
    )
    for cand in fallback_candidates:
        if cand.is_dir() and (cand / "__init__.py").exists():
            return cand

    _die(
        "Could not locate open_webui on sys.path. Run this script using the target OWUI Python env, "
        "or pass --open-webui-dir / --site-packages."
    )


def _backup_file(site_packages_dir: Path, rel_path: Path, backup_root: Path) -> None:
    src = site_packages_dir / rel_path
    if not src.exists():
        return

    dst = backup_root / rel_path
    if dst.exists():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def _restore_from_backup(site_packages_dir: Path, rel_path: Path, backup_root: Path) -> bool:
    src = backup_root / rel_path
    if not src.exists():
        return False

    dst = site_packages_dir / rel_path
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return True


def _validate_python_syntax(path: Path) -> tuple[bool, str | None]:
    try:
        ast.parse(_read_text(path), filename=str(path))
        return True, None
    except SyntaxError as ex:
        msg = ex.msg
        if ex.lineno is not None:
            msg += f" (line {ex.lineno})"
        return False, msg


def _confirm_yes(prompt: str) -> bool:
    try:
        answer = input(prompt).strip().lower()
    except EOFError:
        return False
    return answer in {"y", "yes"}


def _copy_payload_file(site_packages_dir: Path, rel_path: Path, backup_root: Path, dry_run: bool) -> None:
    payload_path = PAYLOAD_DIR / rel_path
    if not payload_path.exists():
        _die(f"Payload missing: {payload_path}")

    target_path = site_packages_dir / rel_path

    if target_path.exists():
        current = _read_text(target_path)
        desired = _read_text(payload_path)
        if current == desired:
            print(f"OK (unchanged): {rel_path.as_posix()}")
            return

    print(f"WRITE: {rel_path.as_posix()}")
    if dry_run:
        return

    _backup_file(site_packages_dir, rel_path, backup_root)
    _write_text(target_path, _read_text(payload_path))


def _replace_binary_file(
    *,
    site_packages_dir: Path,
    rel_path: Path,
    source_bytes: bytes,
    backup_root: Path,
    dry_run: bool,
) -> None:
    target_path = site_packages_dir / rel_path
    if not target_path.exists():
        return

    current = _read_bytes(target_path)
    if current == source_bytes:
        print(f"OK (unchanged): {rel_path.as_posix()}")
        return

    print(f"WRITE: {rel_path.as_posix()}")
    if dry_run:
        return

    _backup_file(site_packages_dir, rel_path, backup_root)
    _write_bytes(target_path, source_bytes)


def _patch_logo_assets(pkg_dir: Path, image_path: Path, backup_root: Path, dry_run: bool) -> None:
    if not image_path.exists() or not image_path.is_file():
        _die(f"Logo image not found: {image_path}")

    if not _is_png(image_path):
        _die("Logo image must be a PNG file.")

    source_bytes = _read_bytes(image_path)
    site_packages_dir = pkg_dir.parent

    target_rel_paths = [
        Path("open_webui/static/logo.png"),
        Path("open_webui/frontend/static/logo.png"),
        Path("open_webui/static/favicon.png"),
        Path("open_webui/frontend/static/favicon.png"),
        Path("open_webui/static/favicon-dark.png"),
        Path("open_webui/frontend/static/favicon-dark.png"),
        Path("open_webui/static/favicon-96x96.png"),
        Path("open_webui/frontend/static/favicon-96x96.png"),
        Path("open_webui/static/apple-touch-icon.png"),
        Path("open_webui/frontend/static/apple-touch-icon.png"),
        Path("open_webui/static/web-app-manifest-192x192.png"),
        Path("open_webui/frontend/static/web-app-manifest-192x192.png"),
        Path("open_webui/static/web-app-manifest-512x512.png"),
        Path("open_webui/frontend/static/web-app-manifest-512x512.png"),
        Path("open_webui/static/splash.png"),
        Path("open_webui/frontend/static/splash.png"),
        Path("open_webui/static/splash-dark.png"),
        Path("open_webui/frontend/static/splash-dark.png"),
    ]

    found_any = False
    for rel_path in target_rel_paths:
        target_path = site_packages_dir / rel_path
        if target_path.exists():
            found_any = True
            _replace_binary_file(
                site_packages_dir=site_packages_dir,
                rel_path=rel_path,
                source_bytes=source_bytes,
                backup_root=backup_root,
                dry_run=dry_run,
            )

    if not found_any:
        print("WARN: No known logo assets were found to replace.")


def _load_logo_pack_assets(pack_path: Path) -> dict[str, bytes]:
    if not pack_path.exists():
        _die(f"Logo pack not found: {pack_path}")

    assets: dict[str, bytes] = {}

    if pack_path.is_dir():
        for file in pack_path.rglob("*"):
            if not file.is_file():
                continue
            assets[file.name.lower()] = _read_bytes(file)
        return assets

    if pack_path.suffix.lower() != ".zip":
        _die("Logo pack must be a directory or a .zip file.")

    with zipfile.ZipFile(pack_path, "r") as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            name = Path(info.filename).name.lower()
            if not name:
                continue
            assets[name] = zf.read(info)

    return assets


def _patch_logo_pack_assets(pkg_dir: Path, pack_path: Path, backup_root: Path, dry_run: bool) -> None:
    assets = _load_logo_pack_assets(pack_path)
    if not assets:
        _die("Logo pack is empty.")

    site_packages_dir = pkg_dir.parent

    file_candidates: dict[Path, list[str]] = {
        Path("open_webui/static/logo.png"): ["logo.png", "logo-512.png", "logo-256.png", "logo-128.png"],
        Path("open_webui/frontend/static/logo.png"): ["logo.png", "logo-512.png", "logo-256.png", "logo-128.png"],
        Path("open_webui/static/favicon.png"): ["favicon.png", "logo-64.png", "logo-32.png", "logo-128.png"],
        Path("open_webui/frontend/static/favicon.png"): ["favicon.png", "logo-64.png", "logo-32.png", "logo-128.png"],
        Path("open_webui/frontend/favicon.png"): ["favicon.png", "logo-64.png", "logo-32.png", "logo-128.png"],
        Path("open_webui/static/swagger-ui/favicon.png"): ["favicon.png", "logo-64.png", "logo-32.png", "logo-128.png"],
        Path("open_webui/static/favicon-dark.png"): ["favicon-dark.png", "favicon.png", "logo-64.png", "logo-32.png"],
        Path("open_webui/frontend/static/favicon-dark.png"): ["favicon-dark.png", "favicon.png", "logo-64.png", "logo-32.png"],
        Path("open_webui/static/favicon-96x96.png"): ["favicon-96x96.png", "logo-128.png", "logo-96.png", "logo-64.png"],
        Path("open_webui/frontend/static/favicon-96x96.png"): ["favicon-96x96.png", "logo-128.png", "logo-96.png", "logo-64.png"],
        Path("open_webui/static/apple-touch-icon.png"): ["apple-touch-icon.png", "logo-256.png", "logo-512.png", "logo-128.png"],
        Path("open_webui/frontend/static/apple-touch-icon.png"): ["apple-touch-icon.png", "logo-256.png", "logo-512.png", "logo-128.png"],
        Path("open_webui/static/web-app-manifest-192x192.png"): ["web-app-manifest-192x192.png", "logo-256.png", "logo-128.png"],
        Path("open_webui/frontend/static/web-app-manifest-192x192.png"): ["web-app-manifest-192x192.png", "logo-256.png", "logo-128.png"],
        Path("open_webui/static/web-app-manifest-512x512.png"): ["web-app-manifest-512x512.png", "logo-512.png", "logo-256.png"],
        Path("open_webui/frontend/static/web-app-manifest-512x512.png"): ["web-app-manifest-512x512.png", "logo-512.png", "logo-256.png"],
        Path("open_webui/static/splash.png"): ["splash.png", "logo-512.png", "logo-256.png"],
        Path("open_webui/frontend/static/splash.png"): ["splash.png", "logo-512.png", "logo-256.png"],
        Path("open_webui/static/splash-dark.png"): ["splash-dark.png", "splash.png", "logo-512.png", "logo-256.png"],
        Path("open_webui/frontend/static/splash-dark.png"): ["splash-dark.png", "splash.png", "logo-512.png", "logo-256.png"],
        Path("open_webui/static/favicon.ico"): ["favicon.ico"],
        Path("open_webui/frontend/static/favicon.ico"): ["favicon.ico"],
        Path("open_webui/static/favicon.svg"): ["favicon.svg"],
        Path("open_webui/frontend/static/favicon.svg"): ["favicon.svg"],
    }

    found_any = False
    wrote_any = False

    for rel_path, candidates in file_candidates.items():
        target_path = site_packages_dir / rel_path
        if not target_path.exists():
            continue

        found_any = True
        source_bytes = None
        for name in candidates:
            source_bytes = assets.get(name.lower())
            if source_bytes is not None:
                break

        if source_bytes is None:
            continue

        wrote_any = True
        _replace_binary_file(
            site_packages_dir=site_packages_dir,
            rel_path=rel_path,
            source_bytes=source_bytes,
            backup_root=backup_root,
            dry_run=dry_run,
        )

    if not found_any:
        print("WARN: No known logo assets were found to replace.")
    elif not wrote_any:
        print("WARN: No matching image names found in pack. Expected names like logo-512.png and favicon.ico.")


def _patch_insert_once(
    *,
    file_path: Path,
    marker_begin: str,
    marker_end: str,
    insert_after_substring: str,
    block: str,
    backup_root: Path,
    dry_run: bool,
) -> bool:
    """Insert a block once after a substring.

    Returns True if modified.
    """

    original = _read_text(file_path)
    if marker_begin in original and marker_end in original:
        print(f"OK (already patched): {file_path.name}")
        return False

    idx = original.find(insert_after_substring)
    if idx < 0:
        print(f"WARN: Could not find insertion point in {file_path.name}: {insert_after_substring!r}")
        return False

    insert_pos = idx + len(insert_after_substring)
    patched = (
        original[:insert_pos]
        + "\n\n"
        + marker_begin
        + "\n"
        + block.rstrip("\n")
        + "\n"
        + marker_end
        + "\n"
        + original[insert_pos:]
    )

    print(f"PATCH: {file_path.name}")
    if dry_run:
        return True

    # Backup relative to site-packages root
    site_packages_dir = file_path.parents[1]
    rel = file_path.relative_to(site_packages_dir)
    _backup_file(site_packages_dir, rel, backup_root)
    _write_text(file_path, patched)
    return True


def _patch_insert_once_any(
    *,
    file_path: Path,
    marker_begin: str,
    marker_end: str,
    insert_after_candidates: list[str],
    block: str,
    backup_root: Path,
    dry_run: bool,
) -> bool:
    for cand in insert_after_candidates:
        if _patch_insert_once(
            file_path=file_path,
            marker_begin=marker_begin,
            marker_end=marker_end,
            insert_after_substring=cand,
            block=block,
            backup_root=backup_root,
            dry_run=dry_run,
        ):
            return True
    return False


def _patch_main_py(pkg_dir: Path, backup_root: Path, dry_run: bool) -> None:
    main_py = pkg_dir / "main.py"
    if not main_py.exists():
        print("WARN: open_webui/main.py not found; skipping main patch")
        return

    text = _read_text(main_py)
    site_packages_dir = pkg_dir.parent

    legacy_block = (
        "# BEGIN OWUI ADMIN CONSOLE STREAM HOOK\n"
        "# Broadcast server logs to the admin console SSE stream.\n"
        "from open_webui.utils.console_stream import (\n"
        "    attach_console_stream_handler,\n"
        "    attach_console_stream_stdio,\n"
        ")\n\n"
        "attach_console_stream_handler()\n"
        "attach_console_stream_stdio()\n"
        "# END OWUI ADMIN CONSOLE STREAM HOOK"
    )
    fixed_block = (
        "    # BEGIN OWUI ADMIN CONSOLE STREAM HOOK\n"
        "    # Broadcast server logs to the admin console SSE stream.\n"
        "    from open_webui.utils.console_stream import (\n"
        "        attach_console_stream_handler,\n"
        "        attach_console_stream_stdio,\n"
        "    )\n\n"
        "    attach_console_stream_handler()\n"
        "    attach_console_stream_stdio()\n"
        "    # END OWUI ADMIN CONSOLE STREAM HOOK"
    )
    if legacy_block in text:
        print("PATCH: main.py (fix legacy stream hook indentation)")
        if not dry_run:
            _backup_file(site_packages_dir, Path("open_webui/main.py"), backup_root)
            _write_text(main_py, text.replace(legacy_block, fixed_block))
        text = text.replace(legacy_block, fixed_block)

    # 1) Ensure routers import includes admin_console
    if "admin_console" not in text:
        # Try to inject into the routers import tuple.
        needle = "from open_webui.routers import ("
        pos = text.find(needle)
        if pos >= 0:
            end = text.find(")\n\n", pos)
            if end > pos:
                block = text[pos:end]
                if "admin_console" not in block:
                    if "scim," in block:
                        block2 = block.replace("    scim,\n", "    admin_console,\n    scim,\n")
                    else:
                        block2 = block.replace(")", "    admin_console,\n)")
                    text2 = text[:pos] + block2 + text[end:]
                    print("PATCH: main.py (routers import)")
                    if not dry_run:
                        _backup_file(site_packages_dir, Path("open_webui/main.py"), backup_root)
                        _write_text(main_py, text2)
                    text = text2
                else:
                    print("OK: main.py routers import already includes admin_console")
            else:
                print("WARN: Could not parse routers import block in main.py")
        else:
            print("WARN: Could not find routers import block in main.py")
    else:
        print("OK: main.py already references admin_console")

    # Reload after possible change
    text = _read_text(main_py)

    # 2) Ensure include_router for admin_console
    if "include_router(admin_console.router" not in text:
        marker_begin = "# BEGIN OWUI ADMIN CONSOLE PATCH"
        marker_end = "# END OWUI ADMIN CONSOLE PATCH"
        block = "# Admin console log streaming (HTML + SSE)\napp.include_router(admin_console.router, tags=[\"admin-console\"])"

        # Try common anchor points first.
        inserted = _patch_insert_once_any(
            file_path=main_py,
            marker_begin=marker_begin,
            marker_end=marker_end,
            insert_after_candidates=[
                "app.include_router(utils.router, prefix=\"/api/v1/utils\", tags=[\"utils\"])\n",
                "# SCIM 2.0 API for identity management\n",
            ],
            block=block,
            backup_root=backup_root,
            dry_run=dry_run,
        )

        # Fallback: insert after the last include_router(...) line.
        if not inserted:
            lines = _read_text(main_py).splitlines(True)
            last_idx = None
            for i, line in enumerate(lines):
                if "app.include_router(" in line:
                    last_idx = i
            if last_idx is not None:
                marker_block = (
                    "\n" + marker_begin + "\n" + block.rstrip("\n") + "\n" + marker_end + "\n"
                )
                patched = "".join(lines[: last_idx + 1]) + marker_block + "".join(lines[last_idx + 1 :])
                print("PATCH: main.py (router include fallback)")
                if not dry_run:
                    _backup_file(site_packages_dir, Path("open_webui/main.py"), backup_root)
                    _write_text(main_py, patched)
    else:
        print("OK: main.py already includes admin_console.router")

    # 3) Ensure lifespan attaches log stream
    if "attach_console_stream_handler" not in text:
        marker_begin = "    # BEGIN OWUI ADMIN CONSOLE STREAM HOOK"
        marker_end = "    # END OWUI ADMIN CONSOLE STREAM HOOK"
        block = (
            "    # Broadcast server logs to the admin console SSE stream.\n"
            "    from open_webui.utils.console_stream import (\n"
            "        attach_console_stream_handler,\n"
            "        attach_console_stream_stdio,\n"
            "    )\n\n"
            "    attach_console_stream_handler()\n"
            "    attach_console_stream_stdio()"
        )
        _patch_insert_once(
            file_path=main_py,
            marker_begin=marker_begin,
            marker_end=marker_end,
            insert_after_substring="    start_logger()\n",
            block=block,
            backup_root=backup_root,
            dry_run=dry_run,
        )
    else:
        print("OK: main.py already attaches console stream")

    if not dry_run:
        ok, error = _validate_python_syntax(main_py)
        if not ok:
            print(f"ERROR: main.py syntax validation failed after patch: {error}")
            restored = _restore_from_backup(
                site_packages_dir, Path("open_webui/main.py"), backup_root
            )
            if restored:
                _die("Aborted: invalid main.py produced by patch; restored original from backup.")
            _die("Aborted: invalid main.py produced by patch and no backup was available to restore.")


def _patch_env_py(pkg_dir: Path, backup_root: Path, dry_run: bool) -> None:
    env_py = pkg_dir / "env.py"
    if not env_py.exists():
        print("WARN: open_webui/env.py not found; skipping env patch")
        return

    text = _read_text(env_py)
    if "DATA_DIR.mkdir(parents=True, exist_ok=True)" in text:
        print("OK: env.py already ensures DATA_DIR exists")
        return

    marker_begin = "# BEGIN OWUI DATA_DIR PATCH"
    marker_end = "# END OWUI DATA_DIR PATCH"
    block = "# Ensure the default data directory exists so SQLite can create/open the database.\nDATA_DIR.mkdir(parents=True, exist_ok=True)"

    # Prefer the exact known line, but fall back to any line that starts with DATA_DIR =
    exact = "DATA_DIR = Path(os.getenv(\"DATA_DIR\", BACKEND_DIR / \"data\")).resolve()\n"
    modified = _patch_insert_once(
        file_path=env_py,
        marker_begin=marker_begin,
        marker_end=marker_end,
        insert_after_substring=exact,
        block=block,
        backup_root=backup_root,
        dry_run=dry_run,
    )

    if not modified:
        lines = _read_text(env_py).splitlines(True)
        for i, line in enumerate(lines):
            if line.strip().startswith("DATA_DIR ="):
                marker_block = (
                    "\n" + marker_begin + "\n" + block.rstrip("\n") + "\n" + marker_end + "\n"
                )
                patched = "".join(lines[: i + 1]) + marker_block + "".join(lines[i + 1 :])
                print("PATCH: env.py (fallback)")
                if not dry_run:
                    site_packages_dir = pkg_dir.parent
                    _backup_file(site_packages_dir, Path("open_webui/env.py"), backup_root)
                    _write_text(env_py, patched)
                return

        print("WARN: env.py was not modified (insertion point not found).")


def _patch_branding(pkg_dir: Path, backup_root: Path, dry_run: bool) -> None:
    site_packages_dir = pkg_dir.parent

    env_py = pkg_dir / "env.py"
    if env_py.exists():
        text = _read_text(env_py)
        updated = text

        legacy_block = (
            "WEBUI_NAME = os.environ.get(\"WEBUI_NAME\", \"Open WebUI\")\n"
            "if WEBUI_NAME != \"Open WebUI\":\n"
            "    WEBUI_NAME += \" (Open WebUI)\""
        )
        branded_line = f'WEBUI_NAME = os.environ.get("WEBUI_NAME", "{BRAND_NAME}")'

        if legacy_block in updated:
            updated = updated.replace(legacy_block, branded_line)
        else:
            updated = updated.replace(
                'WEBUI_NAME = os.environ.get("WEBUI_NAME", "Open WebUI")',
                branded_line,
            )
            updated = updated.replace(
                'if WEBUI_NAME != "Open WebUI":\n    WEBUI_NAME += " (Open WebUI)"\n',
                "",
            )
            updated = updated.replace(
                'if WEBUI_NAME != "Open WebUI":\n    WEBUI_NAME += " (Open WebUI)"',
                "",
            )

        if updated != text:
            print("PATCH: env.py (branding)")
            if not dry_run:
                _backup_file(site_packages_dir, Path("open_webui/env.py"), backup_root)
                _write_text(env_py, updated)
        else:
            print("OK: env.py branding already applied")
    else:
        print("WARN: open_webui/env.py not found; skipping branding patch")

    main_py = pkg_dir / "main.py"
    if main_py.exists():
        text = _read_text(main_py)
        updated = text.replace('title="Open WebUI"', f'title="{BRAND_NAME}"')
        if updated != text:
            print("PATCH: main.py (branding title)")
            if not dry_run:
                _backup_file(site_packages_dir, Path("open_webui/main.py"), backup_root)
                _write_text(main_py, updated)
        else:
            print("OK: main.py branding title already applied")
    else:
        print("WARN: open_webui/main.py not found; skipping branding patch")


def cmd_status(args: argparse.Namespace) -> None:
    pkg_dir = _find_open_webui_dir(args.open_webui_dir, args.site_packages)
    sp = pkg_dir.parent

    checks: dict[str, bool] = {}

    checks["payload admin_console installed"] = (sp / "open_webui/routers/admin_console.py").exists()
    checks["payload console_stream installed"] = (sp / "open_webui/utils/console_stream.py").exists()

    main_py = pkg_dir / "main.py"
    env_py = pkg_dir / "env.py"

    if main_py.exists():
        t = _read_text(main_py)
        checks["main router include"] = "include_router(admin_console.router" in t
        checks["main lifespan hook"] = "attach_console_stream_handler" in t
    else:
        checks["main.py exists"] = False

    if env_py.exists():
        t = _read_text(env_py)
        checks["env DATA_DIR mkdir"] = "DATA_DIR.mkdir(parents=True, exist_ok=True)" in t
    else:
        checks["env.py exists"] = False

    print(f"open_webui dir: {pkg_dir}")
    for k, v in checks.items():
        print(f"- {k}: {'YES' if v else 'NO'}")


def cmd_apply(args: argparse.Namespace) -> None:
    pkg_dir = _find_open_webui_dir(args.open_webui_dir, args.site_packages)
    sp = pkg_dir.parent

    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_root = BACKUPS_DIR / f"{stamp}-{PATCH_ID}"

    print(f"Target open_webui dir: {pkg_dir}")
    print(f"Site-packages dir: {sp}")
    print(f"Backup dir: {backup_root}")

    if not args.dry_run and not args.yes:
        if not _confirm_yes("Proceed with apply? This may overwrite patched files if they differ. [y/N]: "):
            print("Apply canceled.")
            return

    # Install/overwrite our two new modules.
    _copy_payload_file(sp, Path("open_webui/routers/admin_console.py"), backup_root, args.dry_run)
    _copy_payload_file(sp, Path("open_webui/utils/console_stream.py"), backup_root, args.dry_run)

    # Patch core files in-place (idempotent, best-effort).
    _patch_main_py(pkg_dir, backup_root, args.dry_run)
    _patch_env_py(pkg_dir, backup_root, args.dry_run)

    if args.dry_run:
        print("DRY RUN complete (no files were written).")
    else:
        print("Apply complete.")


def cmd_logo(args: argparse.Namespace) -> None:
    pkg_dir = _find_open_webui_dir(args.open_webui_dir, args.site_packages)
    sp = pkg_dir.parent

    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_root = BACKUPS_DIR / f"{stamp}-{PATCH_ID}-logo"

    image_path = Path(args.image).expanduser().resolve() if args.image else None
    pack_path = Path(args.pack).expanduser().resolve() if args.pack else None

    print(f"Target open_webui dir: {pkg_dir}")
    print(f"Site-packages dir: {sp}")
    print(f"Backup dir: {backup_root}")
    if image_path:
        print(f"Logo source: {image_path}")
        _patch_logo_assets(pkg_dir, image_path, backup_root, args.dry_run)
    else:
        print(f"Logo pack source: {pack_path}")
        _patch_logo_pack_assets(pkg_dir, pack_path, backup_root, args.dry_run)

    _patch_branding(pkg_dir, backup_root, args.dry_run)

    if args.dry_run:
        print("DRY RUN complete (no files were written).")
    else:
        print("Logo replacement complete.")


def main() -> None:
    p = argparse.ArgumentParser(
        description=(
            "Patch Open WebUI to add an admin-only browser console at /admin/console "
            "that streams server logs in real time."
        )
    )

    p.add_argument(
        "--open-webui-dir",
        help="Path to the open_webui package directory (contains __init__.py)",
    )
    p.add_argument(
        "--site-packages",
        help="Path to site-packages containing open_webui/",
    )

    sub = p.add_subparsers(dest="cmd", required=True)

    ps = sub.add_parser("status", help="Show whether the patch appears to be installed")
    ps.set_defaults(func=cmd_status)

    pa = sub.add_parser("apply", help="Apply the patch")
    pa.add_argument("--dry-run", action="store_true", help="Print actions without writing")
    pa.add_argument("--yes", action="store_true", help="Skip y/n confirmation prompt")
    pa.set_defaults(func=cmd_apply)

    pl = sub.add_parser(
        "logo",
        help="Replace Open WebUI logo/branding image assets with a custom PNG",
    )
    logo_source = pl.add_mutually_exclusive_group(required=True)
    logo_source.add_argument("--image", help="Path to a PNG image")
    logo_source.add_argument("--pack", help="Path to a logo pack directory or .zip")
    pl.add_argument("--dry-run", action="store_true", help="Print actions without writing")
    pl.set_defaults(func=cmd_logo)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
