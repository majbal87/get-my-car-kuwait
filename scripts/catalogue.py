#!/usr/bin/env python3
"""The saved car list: every brand and model the sites sell, in the sites' own names, with each site's pages.

  python3 catalogue.py --date                        when it was last scanned (or "none")
  python3 catalogue.py --scan                        rescan the sites (about 1-2 minutes), keeping the origin and body already set
  python3 catalogue.py --blanks                      brands without an origin, models without a body (for Claude to fill)
  python3 catalogue.py --set FILE                    FILE: {"origin": {"toyota": "Japanese"}, "body": {"toyota/land-cruiser": "SUV"}}
  python3 catalogue.py --show [--origin Japanese] [--body SUV] [--brand toyota]   (--brand also lists Motorgy's unlinked pages)

Kept inside the skill folder, in data/catalogue.json. 4Sale's list is the backbone (the biggest
catalogue, with English and Arabic names and ad counts); OpenSooq and Motorgy pages are matched to it by
name, the same way resolve.py does for one model. A maker with no model pages on 4Sale (BYD), or listed only on
OpenSooq (Denza), is saved as one entry, '<maker>/all': searching it reads all that maker's ads. Only facts from the sites, plus origin (per brand) and body type
(per model), which Claude fills in. Reliability notes are never stored here: they are written for each search.
Keys are 4Sale's slugs ('toyota/land-cruiser'); search.py takes a model's pages from here when models.json has none.
"""
import argparse, json, os, re, sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date
sys.path.insert(0, os.path.dirname(__file__))
import site_4sale, site_opensooq
from resolve import pick_brand, pick_models, o_brands, o_models, m_models

CAT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "catalogue.json")
ORIGINS = ["Japanese", "Korean", "Chinese", "European", "American", "Other"]


def load():
    return json.load(open(CAT)) if os.path.exists(CAT) else {"scanned": None, "brands": {}}


def save(cat):
    os.makedirs(os.path.dirname(CAT), exist_ok=True)
    json.dump(cat, open(CAT, "w"), ensure_ascii=False, indent=1)


def _try(f, *a):
    try:
        return f(*a)
    except Exception as e:
        print(f"  ! {f.__name__}{a}: {e}")
        return []


def brand(b, old, ob=None):
    slug = b["slug"]
    ob = ob or pick_brand(slug, o_brands()) or pick_brand(b["name_en"], o_brands())
    om = _try(o_models, ob) if ob and b.get("listings_count") is not None else []
    # 4Sale's own spellings ('mercedes', 'bently', 'genesis-1') differ from the others; OpenSooq's is usually the usual one
    tries = list(dict.fromkeys(x for x in [slug, re.sub(r"-\d+$", "", slug), b["name_en"].lower().replace(" ", "-"), ob] if x))
    mm = next((ms for x in tries if (ms := _try(m_models, x))), [])
    models = {}
    for m in (site_4sale.props(f"automotive/used-cars/{slug}/1") or {}).get("catChilds") or [] if b.get("listings_count") is not None else []:
        key, toks = f"{slug}/{m['slug']}", [m.get("name_en") or m["slug"], m["slug"]]
        models[key] = {"name": m.get("name_en") or m["slug"], "name_ar": m.get("name_ar"), "ads": m.get("listings_count", 0),
                       "body": (old.get("models") or {}).get(key, {}).get("body")
                       or ("Mixed" if (m.get("name_en") or "").lower().startswith("other") else None),  # a site's "Other Models" bin
                       "sites": {"4sale": [key], "opensooq": pick_models(om, toks, ob) if ob else [],
                                 "motorgy": pick_models(mm, toks, mm[0][0].split("/")[0]) if mm else []}}
    if not models:  # no model pages: one entry for the whole maker
        models[f"{slug}/all"] = {"name": f"All {b['name_en']}", "name_ar": b.get("name_ar"), "ads": b.get("listings_count"), "body": "Mixed",
                                 "sites": {"4sale": [slug] if b.get("listings_count") is not None else [], "opensooq": [ob] if ob else [],
                                           "motorgy": [p for p, _, _ in mm]}}
    return slug, {"name": b["name_en"], "name_ar": b.get("name_ar"), "ads": b.get("listings_count", 0),
                  "origin": old.get("origin"), "models": models, "motorgy": [p for p, _, _ in mm]}


def progress(step, total):
    """Wraps brand(): prints each maker as it finishes ('[12/78] BYD: 1 models'), so a slow scan shows it is moving."""
    done = [0]
    def run(b, old, ob=None):
        r = brand(b, old, ob)
        done[0] += 1
        print(f"  {step} [{done[0]}/{total}] {b['name_en']}: {len(r[1]['models'])} models", flush=True)
        return r
    return run


def scan():
    old = load()["brands"]
    brands = (site_4sale.props("automotive/used-cars/1") or {}).get("catChilds") or []
    if not brands:
        sys.exit("4Sale's brand list came back empty: the saved list is left as it was.")
    with ThreadPoolExecutor(8) as ex:
        run = progress("4Sale makers", len(brands))
        found = dict(ex.map(lambda b: run(b, old.get(b["slug"]) or {}), brands))
        # makers only OpenSooq lists (Denza)
        taken = {pick_brand(k, o_brands()) or pick_brand(v["name"], o_brands()) for k, v in found.items()}
        extra = [(ob, name) for ob, name, _ in site_opensooq.brands() if ob not in taken and ob not in found]
        run = progress("OpenSooq-only makers", len(extra))
        found.update(ex.map(lambda x: run({"slug": x[0], "name_en": x[1], "listings_count": None}, old.get(x[0]) or {}, x[0]), extra))
    cat = {"scanned": date.today().isoformat(), "brands": found}
    save(cat)
    n = sum(len(b["models"]) for b in found.values())
    new = [k for k in found if k not in old]
    print(f"saved {len(found)} brands, {n} models to {CAT}" + (f"; new brands: {', '.join(new)}" if new else ""))
    blanks(cat)


def blanks(cat):
    b = [k for k, v in cat["brands"].items() if not v.get("origin")]
    m = [k for v in cat["brands"].values() for k, x in v["models"].items() if not x.get("body") and x["ads"]]
    print(f"{len(b)} brands without an origin, {len(m)} models (with ads) without a body")
    if b:
        print("brands:", ", ".join(f"{k} ({cat['brands'][k]['name']})" for k in b))
    for k in m:
        x = cat["brands"][k.split("/")[0]]["models"][k]
        print(f"  {k}  {x['name']}")


def set_values(path):
    cat, fill = load(), json.load(open(path))
    for k, o in (fill.get("origin") or {}).items():
        if k in cat["brands"]:
            cat["brands"][k]["origin"] = o
    for k, body in (fill.get("body") or {}).items():
        b = cat["brands"].get(k.split("/")[0])
        if b and k in b["models"]:
            b["models"][k]["body"] = body
    save(cat)
    blanks(cat)


def show(origin=None, body=None, only=None):
    cat = load()
    print(f"car list scanned {cat['scanned']}")
    for o in ORIGINS + [None]:
        bs = [(k, b) for k, b in cat["brands"].items() if b.get("origin") == o and (not origin or (o or "").lower() == origin.lower())
              and (not only or k == only)]
        if not bs:
            continue
        print(f"\n## {o or 'origin not set'}")
        for k, b in sorted(bs, key=lambda x: -(x[1]["ads"] or 0)):
            ms = [(mk, m) for mk, m in b["models"].items() if m["ads"] != 0
                  and (not body or (m.get("body") or "").lower() in (body.lower(), "mixed"))]
            if ms:
                print(f"{b['name']} ({b['ads']} ads): " + "; ".join(
                    f"{m['name']}{' / ' + m['name_ar'] if m.get('name_ar') not in (None, m['name']) else ''} [{mk}] {m.get('body') or '?'} {m['ads'] if m['ads'] is not None else '?'}" for mk, m in sorted(ms, key=lambda x: -(x[1]["ads"] or 0))))
            if only:  # Motorgy names some models by engine (Mercedes s500, BMW 730li), so name matching misses them
                linked = {p for m in b["models"].values() for p in m["sites"]["motorgy"]}
                rest = [p for p in b.get("motorgy") or [] if p not in linked]
                print(f"  Motorgy pages not linked to a model: {', '.join(rest) if rest else 'none'}")


def sites(key):
    """A model's pages on every site, or None when it isn't in the saved list."""
    b = load()["brands"].get(key.split("/")[0])
    return b["models"][key]["sites"] if b and key in b["models"] else None


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", action="store_true")
    ap.add_argument("--scan", action="store_true")
    ap.add_argument("--blanks", action="store_true")
    ap.add_argument("--set", metavar="FILE")
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--origin")
    ap.add_argument("--body")
    ap.add_argument("--brand")
    a = ap.parse_args()
    if a.date:
        print(load()["scanned"] or "none")
    elif a.scan:
        scan()
    elif a.blanks:
        blanks(load())
    elif a.set:
        set_values(a.set)
    else:
        show(a.origin, a.body, a.brand)
