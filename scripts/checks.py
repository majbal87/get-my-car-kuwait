#!/usr/bin/env python3
"""Apply the checker agents' verdicts to DIR/cars.json.

  python3 checks.py --out DIR

For each DIR/checks/pair_N.verdict.json with "verdict": "same", the dearer ad (same price: the one with fewer
photos, or the lower-ranked site) is removed from the page, unless the prices match and the verdict says "keep": "a" or "b", and becomes an `also` link on the other, with "checked": true (build.py
counts these as duplicates merged). "different" and "unsure" keep both. All verdicts are logged in
DIR/dedup.json under "checked". Pairs without a verdict file are reported and left alone.
"""
import argparse, glob, json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from dedup import RANK

ap = argparse.ArgumentParser()
ap.add_argument("--out", required=True)
a = ap.parse_args()

cars = json.load(open(os.path.join(a.out, "cars.json")))
by = {c["id"]: c for c in cars}
moved, log, missing = {}, [], []  # moved: merged-away id -> the id it now lives under


def root(i):
    while i in moved:
        i = moved[i]
    return i


for f in sorted(glob.glob(os.path.join(a.out, "checks", "pair_*.json")), key=lambda p: int(p.split("_")[-1].split(".")[0])):
    if f.endswith(".verdict.json"):
        continue
    pair = json.load(open(f))
    vf = f.replace(".json", ".verdict.json")
    if not os.path.exists(vf):
        missing.append(pair["pair"]); continue
    v = json.load(open(vf))
    log.append({"pair": pair["pair"], "a": pair["a"]["id"], "b": pair["b"]["id"], "hints": pair["hints"],
                "verdict": v.get("verdict"), "reason": v.get("reason")})
    if v.get("verdict") != "same":
        continue
    x, y = (root(pair[k]["id"]) for k in ("a", "b"))
    if x == y or x not in by or y not in by:
        continue
    # the cheapest copy is kept (owner's rule), then the one with the most photos
    keep, drop = sorted((by[x], by[y]), key=lambda c: (c.get("price") or 10**9, -len(c["imgs"]), RANK.get(c["source"], 9)))
    if v.get("keep") in ("a", "b") and root(pair[v["keep"]]["id"]) == drop["id"] and drop.get("price") == keep.get("price"):  # same price: the checker saw better photos there
        keep, drop = drop, keep
    keep.setdefault("also", []).append({"source": drop["source"], "url": drop["url"], "price": drop["price"],
                                        "phone": drop.get("phone"), "checked": True})
    keep["also"] += drop.get("also") or []
    if not keep.get("phone") and drop["source"] != "Motorgy":
        keep["phone"] = drop.get("phone")
    moved[drop["id"]] = keep["id"]
    del by[drop["id"]]

out = [c for c in cars if c["id"] in by]
json.dump(out, open(os.path.join(a.out, "cars.json"), "w"), ensure_ascii=False, indent=1)
dp = os.path.join(a.out, "dedup.json")
d = json.load(open(dp)) if os.path.exists(dp) else {}
d["checked"] = log
json.dump(d, open(dp, "w"), ensure_ascii=False, indent=1)
count = {k: sum(1 for x in log if x["verdict"] == k) for k in ("same", "different", "unsure")}
print(f"{len(cars) - len(out)} cars merged; verdicts {count}" + (f"; NO VERDICT for pairs {missing}" if missing else ""))
