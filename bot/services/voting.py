
import random


def determine_winner(round_data, return_detail=False):
    opts = round_data["options"]
    total = sum(o["votes"] for o in opts)

    meta = round_data.get("meta") or {}
    try:
        minimum_votes = int(meta.get("minimum_votes", 0) or 0)
    except (TypeError, ValueError):
        minimum_votes = 0
    minimum_votes = max(0, minimum_votes)

    if total == 0:
        pick = random.choice(opts)
        detail = {"reason": "no_votes", "chosen_label": pick["label"]}
        return (pick["map"], detail) if return_detail else pick["map"]

    if minimum_votes and total < minimum_votes:
        pick = random.choice(opts)
        detail = {
            "reason": "below_threshold",
            "chosen_label": pick["label"],
            "required": minimum_votes,
            "total": total,
        }
        return (pick["map"], detail) if return_detail else pick["map"]

    maxv = max(o["votes"] for o in opts)
    top = [o for o in opts if o["votes"] == maxv]
    if len(top) > 1:
        pick = random.choice(top)
        detail = {
            "reason": "tie",
            "chosen_label": pick["label"],
            "tied_labels": [o["label"] for o in top],
        }
        return (pick["map"], detail) if return_detail else pick["map"]

    pick = next(o for o in opts if o["votes"] == maxv)
    detail = {"reason": "highest", "chosen_label": pick["label"]}
    return (pick["map"], detail) if return_detail else pick["map"]
