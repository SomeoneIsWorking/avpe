"""Validation and polling policy for AVP:E's bounded native-asset cache."""

import json
import time

from avpe.control_http import request_bytes


def cache_snapshot_is_verified(
    snapshot: dict[str, object] | None,
    *,
    require_activity: bool = False,
) -> bool:
    if snapshot is None:
        return False

    field_names = (
        "page_bytes",
        "maximum_pages",
        "maximum_resident_bytes",
        "hits",
        "misses",
        "fills",
        "evictions",
        "resident_pages",
        "resident_bytes",
        "transient_handles",
        "peak_transient_handles",
    )
    values: dict[str, int] = {}
    for name in field_names:
        value = snapshot.get(name)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            return False
        values[name] = value

    if values["page_bytes"] != 64 * 1024:
        return False
    if values["maximum_pages"] != 512:
        return False
    if values["maximum_resident_bytes"] != 32 * 1024 * 1024:
        return False
    if values["resident_pages"] > values["maximum_pages"]:
        return False
    if values["resident_bytes"] != values["resident_pages"] * values["page_bytes"]:
        return False
    if values["resident_bytes"] > values["maximum_resident_bytes"]:
        return False
    if values["misses"] < values["fills"]:
        return False
    if values["fills"] < values["evictions"]:
        return False
    if values["resident_pages"] != values["fills"] - values["evictions"]:
        return False
    if values["transient_handles"] != 0:
        return False
    if values["peak_transient_handles"] > 1:
        return False
    if require_activity and (
        values["misses"] == 0
        or values["fills"] == 0
        or values["resident_pages"] == 0
    ):
        return False
    return True


def await_asset_cache(port: int, deadline: float) -> dict[str, object]:
    snapshot: dict[str, object] | None = None
    while time.monotonic() < deadline:
        status, body = request_bytes(port, "GET", "/assets/cache")
        if status != 200:
            raise RuntimeError(f"asset cache snapshot returned HTTP {status}")
        candidate = json.loads(body)
        if isinstance(candidate, dict):
            snapshot = candidate
            if cache_snapshot_is_verified(snapshot, require_activity=True):
                return snapshot
        time.sleep(0.05)
    raise RuntimeError(f"bounded active asset cache was not observed: {snapshot}")


def build_cache_proof(
    boot_asset_boundary: dict[str, object],
    cache: dict[str, object],
) -> dict[str, object]:
    return {
        "boot_asset_boundary": boot_asset_boundary,
        "cache": cache,
        "bounded": True,
    }
