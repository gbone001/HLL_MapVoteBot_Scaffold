from bot.utils.maps import base_map_code, normalize_cooldowns


def test_base_map_code_strips_variants():
    assert base_map_code("FOY_WARFARE_DAY") == "FOY"
    assert base_map_code("OMAHA") == "OMAHA"


def test_normalize_cooldowns_merges_variants_and_handles_noise():
    raw = {
        "FOY_WARFARE": 2,
        "FOY_NIGHT": 1,
        "OMAHA_OFFENSIVE": "3",
        "INVALID": "not-a-number",
    }

    result = normalize_cooldowns(raw)

    assert result == {"FOY": 2, "OMAHA": 3}
```}