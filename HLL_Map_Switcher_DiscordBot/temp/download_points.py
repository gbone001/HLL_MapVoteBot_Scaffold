import json
from pathlib import Path
import urllib.request

map_prefixes = {
    "PHL_L_1944_Warfare": "PHL",
    "carentan_warfare": "Carentan",
    "elalamein_warfare": "ElAlamein",
    "elsenbornridge_warfare": "Elsenborn",
    "foy_warfare": "Foy",
    "hill400_warfare": "Hill400",
    "hurtgenforest_warfare_V2": "HurtgenV2",
    "kharkov_warfare": "Kharkov",
    "kursk_warfare": "Kursk",
    "omahabeach_warfare": "Omaha",
    "remagen_warfare": "Remagen",
    "stalingrad_warfare": "Stalingrad",
    "stmariedumont_warfare": "SMDMV2",
    "stmereeglise_warfare": "SME",
    "tobruk_warfare": "Tobruk",
    "utahbeach_warfare": "Utah"
}

base_dir = Path('temp/assets/points')
base_dir.mkdir(parents=True, exist_ok=True)
for prefix in map_prefixes.values():
    url = f"https://raw.githubusercontent.com/mattwright324/maps-let-loose/main/assets/points/{prefix}_SP_NoMap.png"
    dest = base_dir / f"{prefix}_SP_NoMap.png"
    if not dest.exists():
        print('Downloading', prefix)
        urllib.request.urlretrieve(url, dest)
print('done')
