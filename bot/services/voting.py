
import random

def determine_winner(round_data, return_detail=False):
    opts = round_data["options"]
    total = sum(o["votes"] for o in opts)
    if total == 0:
        pick = random.choice(opts)
        return (pick["map"], {"reason": "no_votes", "chosen_label": pick["label"]}) if return_detail else pick["map"]

    maxv = max(o["votes"] for o in opts)
    top = [o for o in opts if o["votes"] == maxv]
    if len(top) > 1:
        pick = random.choice(top)
        detail = {"reason": "tie", "chosen_label": pick["label"], "tied_labels": [o["label"] for o in top]}
        return (pick["map"], detail) if return_detail else pick["map"]

    pick = next(o for o in opts if o["votes"] == maxv)
    return (pick["map"], {"reason": "highest", "chosen_label": pick["label"]}) if return_detail else pick["map"]
