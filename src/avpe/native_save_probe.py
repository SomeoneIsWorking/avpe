"""Validation policy for the live AVP:E profile payload save seam."""


def profile_snapshot_is_verified(snapshot: object) -> bool:
    """Validate the live CProfile payload contract captured at SaveGame entry."""
    if not isinstance(snapshot, dict) or any((
        not isinstance(snapshot.get("object"), str),
        not isinstance(snapshot.get("data"), str),
        snapshot.get("size") != 0x20,
        snapshot.get("revision") != "0x1CD9DEE3",
        snapshot.get("slot_count") != 4,
        not isinstance(snapshot.get("payload_hex"), str),
    )):
        return False
    payload_hex = snapshot["payload_hex"]
    if len(payload_hex) != snapshot["size"] * 2:
        return False
    try:
        payload = bytes.fromhex(payload_hex)
    except ValueError:
        return False
    return len(payload) == snapshot["size"]
