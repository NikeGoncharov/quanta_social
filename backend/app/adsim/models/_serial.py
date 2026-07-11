"""Serialization helper shared by the OpenRTB model to_dict() methods."""


def compact(d: dict) -> dict:
    """Drop keys that are None or empty ("" / [] / {}); keep meaningful zeros/ints."""
    out = {}
    for k, v in d.items():
        if v is None:
            continue
        if isinstance(v, (list, dict, str)) and len(v) == 0:
            continue
        out[k] = v
    return out
