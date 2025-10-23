from __future__ import annotations


VARIANT_GAME_SUFFIXES = {
    "WARFARE",
    "OFFENSIVE",
    "OFFENSIVEUS",
    "OFFENSIVEGER",
}

VARIANT_TIME_SUFFIXES = {
    "DAY",
    "DAWN",
    "NIGHT",
}

_VARIANT_SUFFIXES = VARIANT_GAME_SUFFIXES | VARIANT_TIME_SUFFIXES


def base_map_code(map_code: str) -> str:
    """
    Collapse a map code down to its base map identifier.

    HLL encodes game mode (e.g., Warfare, Offensive) and time-of-day (e.g., Day,
    Dawn, Night) as suffix segments separated by underscores. We strip those
    suffixes so that all variants share a common cooldown bucket.
    """
    parts = map_code.split("_")
    while parts and parts[-1].upper() in _VARIANT_SUFFIXES:
        parts.pop()
    # In case every segment gets stripped we fall back to the original code.
    return "_".join(parts) if parts else map_code


def normalize_cooldowns(raw: dict[str, int | str] | None) -> dict[str, int]:
    """
    Convert stored cooldowns to use base map codes, keeping the highest value
    for any variants that map to the same base.
    """
    normalized: dict[str, int] = {}
    if not raw:
        return normalized

    for code, value in raw.items():
        base_code = base_map_code(code)
        try:
            as_int = int(value)
        except (TypeError, ValueError):
            # Ignore malformed entries rather than crashing vote flow.
            continue
        current = normalized.get(base_code, 0)
        if as_int > current:
            normalized[base_code] = as_int
    return normalized
