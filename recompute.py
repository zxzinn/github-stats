#!/usr/bin/env python3
"""Recompute totals from result_v2.json with adjustable language exclusions."""
import json
import sys
from pathlib import Path

EXCLUDE_LANGS = {"Jupyter Notebook"}

data = json.loads(Path(sys.argv[1]).read_text())

new_lang = {}
new_total_add = 0
new_total_del = 0
new_per_repo = []

for r in data["per_repo"]:
    add = 0
    dele = 0
    by_lang = {}
    for lang, v in r["by_lang"].items():
        if lang in EXCLUDE_LANGS:
            continue
        add += v["add"]
        dele += v["del"]
        by_lang[lang] = v
        new_lang.setdefault(lang, {"add": 0, "del": 0})
        new_lang[lang]["add"] += v["add"]
        new_lang[lang]["del"] += v["del"]
    if add + dele == 0:
        continue
    new_total_add += add
    new_total_del += dele
    new_per_repo.append({**r, "by_lang": by_lang, "totals": {"add": add, "del": dele,
                          "other_add": r["totals"]["other_add"], "other_del": r["totals"]["other_del"]}})

new_per_repo.sort(key=lambda r: -(r["totals"]["add"] + r["totals"]["del"]))
out = {
    "user": data["user"],
    "totals": {
        "added": new_total_add,
        "deleted": new_total_del,
        "net": new_total_add - new_total_del,
        "commits": sum(r["commits"] for r in new_per_repo),
        "repos_contributed": len(new_per_repo),
    },
    "languages": dict(sorted(new_lang.items(), key=lambda x: -(x[1]["add"]+x[1]["del"]))),
    "per_repo": new_per_repo,
    "excluded_languages": sorted(EXCLUDE_LANGS),
}
print(json.dumps(out, indent=2))
