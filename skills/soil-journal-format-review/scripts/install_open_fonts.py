#!/usr/bin/env python3
"""Download verified open CJK fonts from the official Google Fonts repository.

By default files are downloaded to a task directory. Use --install-user only
after the user authorizes a per-user font installation. Proprietary fonts such
as SimSun/SimHei/Calibri are intentionally unsupported by this downloader.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
import tempfile
from pathlib import Path

GOOGLE_FONTS_COMMIT = "352f6b7d9d6cc4fa9e242b931291d31b21a6dc84"
CATALOG = {
    "noto-sans-sc": {
        "family": "Noto Sans SC",
        "file": "NotoSansSC-wght.ttf",
        "source_path": "ofl/notosanssc/NotoSansSC%5Bwght%5D.ttf",
        "git_blob_sha1": "fb0637bafbcd804fe32152370a1225990745b4bc",
        "license_path": "ofl/notosanssc/OFL.txt",
        "license_git_blob_sha1": "1c9f43281b8f216c5461fe9ac729afbade7724e4",
    },
    "noto-serif-sc": {
        "family": "Noto Serif SC",
        "file": "NotoSerifSC-wght.ttf",
        "source_path": "ofl/notoserifsc/NotoSerifSC%5Bwght%5D.ttf",
        "git_blob_sha1": "eab063faf229160a52d3760f5555150e4eb9e5bf",
        "license_path": "ofl/notoserifsc/OFL.txt",
        "license_git_blob_sha1": "94d1bf7b52481343e2983fb7751e8b7abe1ea07b",
    },
}


def git_blob_sha1(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def download(url: str, timeout: int = 180) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "soil-journal-format-review/1.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def source_url(path: str) -> str:
    return f"https://raw.githubusercontent.com/google/fonts/{GOOGLE_FONTS_COMMIT}/{path}"


def user_font_dir() -> Path:
    system = platform.system()
    if system == "Darwin":
        return Path.home() / "Library/Fonts"
    if system == "Windows":
        local = os.environ.get("LOCALAPPDATA")
        if not local:
            raise RuntimeError("LOCALAPPDATA is not set")
        return Path(local) / "Microsoft/Windows/Fonts"
    return Path.home() / ".local/share/fonts"


def register_windows_font(path: Path, family: str) -> None:
    if platform.system() != "Windows":
        return
    import ctypes
    import winreg  # type: ignore

    key_path = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts"
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
        winreg.SetValueEx(key, f"{family} (TrueType)", 0, winreg.REG_SZ, str(path))
    HWND_BROADCAST = 0xFFFF
    WM_FONTCHANGE = 0x001D
    SMTO_ABORTIFHUNG = 0x0002
    result = ctypes.c_ulong()
    ctypes.windll.user32.SendMessageTimeoutW(
        HWND_BROADCAST, WM_FONTCHANGE, 0, 0, SMTO_ABORTIFHUNG, 5000, ctypes.byref(result)
    )


def _atomic_write(path: Path, data: bytes) -> None:
    handle, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, path)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


def install_or_download(
    font_ids: list[str],
    destination: Path,
    install_user: bool,
    verify_docx: Path | None = None,
    mapping_path: Path | None = None,
) -> dict:
    destination.mkdir(parents=True, exist_ok=True)
    records = []
    for font_id in font_ids:
        item = CATALOG[font_id]
        font_url = source_url(item["source_path"])
        license_url = source_url(item["license_path"])
        font_data = download(font_url)
        license_data = download(license_url)
        actual_blob = git_blob_sha1(font_data)
        actual_license_blob = git_blob_sha1(license_data)
        if actual_blob != item["git_blob_sha1"]:
            raise RuntimeError(f"{font_id}: Git blob SHA-1 mismatch")
        if actual_license_blob != item["license_git_blob_sha1"]:
            raise RuntimeError(f"{font_id}: license Git blob SHA-1 mismatch")
        font_path = destination / item["file"]
        license_path = destination / f"{font_id}-OFL.txt"
        _atomic_write(font_path, font_data)
        _atomic_write(license_path, license_data)
        if install_user:
            register_windows_font(font_path, item["family"])
        records.append(
            {
                "font_id": font_id,
                "family": item["family"],
                "font_path": str(font_path.resolve()),
                "font_source": font_url,
                "font_git_blob_sha1": actual_blob,
                "font_sha256": hashlib.sha256(font_data).hexdigest(),
                "license": "SIL Open Font License 1.1",
                "license_path": str(license_path.resolve()),
                "license_source": license_url,
                "license_git_blob_sha1": actual_license_blob,
                "bytes": len(font_data),
            }
        )
    cache_result = None
    if install_user and shutil.which("fc-cache"):
        refresh = subprocess.run(
            [str(shutil.which("fc-cache")), "-f", str(destination)],
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
        cache_result = {
            "command": refresh.args,
            "returncode": refresh.returncode,
            "stderr": refresh.stderr.strip()[-1000:],
        }
        if refresh.returncode != 0:
            raise RuntimeError(f"fc-cache failed with exit code {refresh.returncode}")
    verification = None
    status = "PASS"
    if verify_docx:
        from audit_docx_fonts import audit

        compatibility = mapping_path or Path(__file__).resolve().parent.parent / "assets/font-compatibility.json"
        verification = audit(verify_docx, compatibility, [CATALOG[item]["family"] for item in font_ids])
        if install_user and any(
            not row["exact_installed"]
            for row in verification.get("fonts", [])
            if row["requested"] in {CATALOG[item]["family"] for item in font_ids}
        ):
            status = "WARN"
    return {
        "status": status,
        "mode": "user_install" if install_user else "download_only",
        "platform": platform.system(),
        "official_repository": "https://github.com/google/fonts",
        "pinned_commit": GOOGLE_FONTS_COMMIT,
        "destination": str(destination.resolve()),
        "fonts": records,
        "font_cache_refresh": cache_result,
        "post_install_docx_audit": verification,
        "restart_required": bool(install_user),
        "note": "Restart Word/LibreOffice after installation. This tool never downloads proprietary fonts.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--font", action="append", choices=sorted(CATALOG), required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--download-dir", type=Path)
    mode.add_argument("--install-user", action="store_true")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--verify-docx", type=Path)
    parser.add_argument("--mapping", type=Path)
    args = parser.parse_args()
    destination = user_font_dir() if args.install_user else (args.download_dir or Path.cwd() / "downloaded-fonts")
    try:
        result = install_or_download(
            args.font,
            destination,
            args.install_user,
            verify_docx=args.verify_docx,
            mapping_path=args.mapping,
        )
    except (OSError, RuntimeError, urllib.error.URLError, TimeoutError) as exc:
        result = {"status": "ERROR", "error": str(exc)}
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return {"PASS": 0, "WARN": 3}.get(result.get("status"), 2)


if __name__ == "__main__":
    sys.exit(main())
