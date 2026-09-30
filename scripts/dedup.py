"""Find the same car advertised more than once (across sites, or reposted on one site).

The script merges on its own only when it is certain:
- the same chassis number (VIN, Al-Sayer's sites), or
- identical km that is not a round number (e.g. 187,340) with the same model and year, price within 10%
  and no colour clash.
Different chassis numbers are never merged.

Everything else that looks alike (same model and year, km within 3% or 1,500 km, price within 15%, no colour
clash) is a candidate pair, even with the same phone: a dealer often sells several look-alike cars. candidates() lists
the pairs among the cars on the page; a fresh checker agent per pair decides (references/dup-checker.md,
checks.py). The phone, the ad text and the photos are its evidence.
Motorgy's phone is its own sales line, so it says nothing about the seller.
"""
import difflib, re
from common import colour

RANK = {"4Sale": 0, "Al-Sayer": 1, "Motorgy": 2, "OpenSooq": 3}


def same_phone(a, b):
    """True / False, or None when unknown. A masked OpenSooq '669724??' matches any number starting 669724."""
    p, q = a.get("phone"), b.get("phone")
    if not p or not q or "Motorgy" in (a["source"], b["source"]):
        return None
    known = [(x, y) for x, y in zip(p, q) if "?" not in (x, y)]
    return len(known) >= 6 and all(x == y for x, y in known)


def same_car(a, b, exact=False, loose=False):
    """exact: identical odd km. loose (candidates for the checkers): km within 3% or 1,500, price within 15%."""
    if a["model"] != b["model"] or not a["year"] or a["year"] != b["year"]:
        return False
    if not a["km"] or not b["km"]:
        return False
    if exact:
        if a["km"] != b["km"] or a["km"] % 1000 == 0:
            return False
    elif abs(a["km"] - b["km"]) > (max(0.03 * max(a["km"], b["km"]), 1500) if loose else max(0.02 * max(a["km"], b["km"]), 300)):
        return False
    if abs(a["price"] - b["price"]) > (0.15 if loose else 0.10) * max(a["price"], b["price"]):
        return False
    ca, cb = colour(a.get("color")), colour(b.get("color"))
    return not (ca and cb and ca != cb)


def same_text(a, b):
    for f, n in (("title", 30), ("desc", 60)):
        x, y = (re.sub(r"\s+", " ", (c.get(f) or "")).strip().lower() for c in (a, b))
        if min(len(x), len(y)) >= n and difflib.SequenceMatcher(None, x, y).ratio() >= 0.9:
            return True
    return False


def why(a, b):
    """Reason string when a and b are certainly the same car, else None."""
    if a.get("vin") and b.get("vin"):
        return "same chassis number" if a["vin"].upper() == b["vin"].upper() else None
    if same_car(a, b, exact=True):
        return "identical odd km, same model and year, price within 10%"
    return None


def dedup(cars):
    """Returns (kept cars with an `also` list, groups of merged ads with the reasons)."""
    order = sorted(cars, key=lambda c: (c.get("price") or 10**9, -len(c["images"]),  # the cheapest copy is kept (owner's rule), then the most photos
                                   RANK.get(c["source"], 9), -(int((c.get("posted") or "0").replace("-", "") or 0))))
    groups = []  # each: [keeper, (ad, reason), ...]
    for c in order:
        for g in groups:
            if g[0]["model"] == c["model"] and (r := why(g[0], c) or next((x for m, _ in g[1:] if (x := why(m, c))), None)):
                g.append((c, r)); break
        else:
            groups.append([c])
    kept, merged = [], []
    for g in groups:
        k = dict(g[0])
        k["also"] = [{"source": m["source"], "url": m["url"], "price": m["price"], "phone": m.get("phone")} for m, _ in g[1:] if m["url"] != k["url"]]
        for m, _ in g[1:]:
            for f in ("color", "imp", "cond", "posted"):
                k[f] = k.get(f) or m.get(f)
            if not k.get("phone") and m["source"] != "Motorgy":
                k["phone"] = m.get("phone")  # e.g. an Al-Sayer car: the number on its 4Sale copy
            k["features"] = k["features"] + [x for x in m["features"] if x not in k["features"]]
        kept.append(k)
        if len(g) > 1:
            merged.append({"kept": _brief(g[0]), "removed": [dict(_brief(m), reason=r) for m, r in g[1:]]})
    return kept, merged


def candidates(cars):
    """Look-alike pairs among the cars on the page, with hints for the checker. Different chassis numbers are skipped."""
    out = []
    for i, a in enumerate(cars):
        for b in cars[i + 1:]:
            if (a.get("vin") and b.get("vin")) or not same_car(a, b, loose=True):
                continue
            hints = [{True: "same phone", False: "different phones", None: "no phone to compare"}[same_phone(a, b)]]
            if "?" in (a.get("phone") or "") + (b.get("phone") or "") and same_phone(a, b) is not None:
                hints[0] += " (visible digits only: OpenSooq hides the last 2)"
            if a["source"] == b["source"] and a.get("seller") and a.get("seller") == b.get("seller"):
                hints.append("same seller account")
            if same_text(a, b):
                hints.append("near-identical ad text")
            if a["km"] == b["km"]:
                hints.append("identical km")
            out.append((a, b, hints))
    return out


def _brief(c):
    return {k: c.get(k) for k in ("id", "source", "model", "year", "km", "price", "color", "phone", "seller", "vin", "url")}
