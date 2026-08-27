"""Loopback HTTP transport for the isolated AVPE control-test process."""

import http.client
import json
import urllib.error
import urllib.request


def read_status(port: int) -> dict[str, str] | None:
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/status", timeout=0.5
        ) as response:
            body = json.loads(response.read())
    except (
        OSError,
        UnicodeError,
        ValueError,
        http.client.HTTPException,
        urllib.error.URLError,
        json.JSONDecodeError,
    ):
        return None
    return body if isinstance(body, dict) else None


def request_shutdown(port: int) -> bool:
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/shutdown",
        data=b"{}",
        method="POST",
        headers={"Content-Type": "application/json", "Connection": "close"},
    )
    try:
        with urllib.request.urlopen(request, timeout=2) as response:
            return response.status == 202
    except (OSError, http.client.HTTPException, urllib.error.URLError):
        return False


def request_bytes(
    port: int,
    method: str,
    path: str,
    payload: dict[str, object] | None = None,
    timeout: float = 2.0,
) -> tuple[int, bytes]:
    body = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=body,
        method=method,
        headers={"Content-Type": "application/json", "Connection": "close"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()
    except (OSError, http.client.HTTPException, urllib.error.URLError) as error:
        raise RuntimeError(f"{method} {path} failed: {error}") from error


def request_json(
    port: int,
    method: str,
    path: str,
    payload: dict[str, object],
) -> tuple[int, dict[str, object] | None, str]:
    status, body = request_bytes(port, method, path, payload)
    detail = body.decode(errors="replace").strip()
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        return status, None, detail
    return status, parsed if isinstance(parsed, dict) else None, detail
