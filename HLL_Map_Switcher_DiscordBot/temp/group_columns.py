import json

with open('temp/ocr_results.json','r',encoding='utf-8') as f:
    data=json.load(f)

maps = list(data.keys())
results = {}
for map_key, items in data.items():
    if not items:
        continue
    xs = sorted(set(round(item['x'], 1) for item in items))
    if len(xs) < 5:
        # fallback distribute by sorting
        sorted_items = sorted(items, key=lambda d:d['y'])
        chunk = max(1, len(sorted_items)//5)
        cols = []
        idx = 0
        for i in range(5):
            col = [it['text'] for it in sorted(sorted_items[idx:idx+chunk], key=lambda d:d['y'])]
            cols.append(col)
            idx += chunk
        results[map_key] = cols
        continue
    centroids = []
    xs_sorted = sorted(xs)
    for i in range(5):
        idx = min(int(len(xs_sorted) * (i + 0.5) / 5), len(xs_sorted)-1)
        centroids.append(xs_sorted[idx])
    for _ in range(10):
        groups = {i: [] for i in range(5)}
        for item in items:
            idx = min(range(5), key=lambda j: abs(item['x'] - centroids[j]))
            groups[idx].append(item)
        new_centroids = []
        for i in range(5):
            if groups[i]:
                new_centroids.append(sum(it['x'] for it in groups[i]) / len(groups[i]))
            else:
                new_centroids.append(centroids[i])
        if all(abs(new_centroids[i]-centroids[i]) < 1 for i in range(5)):
            centroids = new_centroids
            break
        centroids = new_centroids
    cols = []
    for i in range(5):
        col_items = sorted(groups[i], key=lambda it: it['y'])
        cols.append([it['text'].upper() for it in col_items])
    results[map_key] = cols

with open('temp/strongpoints_grouped.json','w',encoding='utf-8') as f:
    json.dump(results, f, indent=2)
print('grouped')
