import json
from pathlib import Path
import easyocr

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

reader = easyocr.Reader(['en'], gpu=False, verbose=False)
results = {}
for map_key, prefix in map_prefixes.items():
    path = Path('temp/assets/points') / f"{prefix}_SP_NoMap.png"
    detections = reader.readtext(str(path), detail=1, paragraph=False)
    items = []
    for bbox, text, conf in detections:
        text = text.strip()
        if not text:
            continue
        xs = [p[0] for p in bbox]
        ys = [p[1] for p in bbox]
        items.append({'text': text.upper(), 'x': sum(xs)/len(xs), 'y': sum(ys)/len(ys), 'conf': conf})
    results[map_key] = items

Path('temp').mkdir(exist_ok=True)
with open('temp/ocr_results.json','w',encoding='utf-8') as f:
    json.dump(results, f, indent=2)
print('ocr complete')
