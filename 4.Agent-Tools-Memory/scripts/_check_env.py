"""Check whether a local server and/or python playwright are usable."""

from __future__ import annotations

import socket
import urllib.request
from pathlib import Path

lines: list[str] = []


def check_server() -> None:
    try:
        with urllib.request.urlopen(
            "http://127.0.0.1:8765/form_payload_all.json", timeout=4
        ) as response:
            body = response.read()
        lines.append(f"server: OK {response.status} bytes={len(body)}")
    except Exception as error:  # noqa: BLE001
        lines.append(f"server: FAIL {type(error).__name__}: {error}")

    sock = socket.socket()
    sock.settimeout(2)
    try:
        sock.connect(("127.0.0.1", 8765))
        lines.append("port 8765: open")
    except Exception as error:  # noqa: BLE001
        lines.append(f"port 8765: closed ({type(error).__name__})")
    finally:
        sock.close()


def check_playwright() -> None:
    try:
        import playwright  # noqa: F401

        lines.append("python playwright: INSTALLED")
    except ImportError:
        lines.append("python playwright: MISSING")


check_server()
check_playwright()
Path("scripts/_env_check.txt").write_text("\n".join(lines), encoding="utf-8")
print("written")
