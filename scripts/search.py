#!/usr/bin/env python3
"""One command: fetch every site (every list page each site reports), clean, remove duplicates and list the photos.
Fast page (default): the page shows the photos from the sites themselves, so only the photos the duplicate checker
looks at are downloaded. --download (Claude.ai page): 3 photos per car are downloaded (pick3), since that page ships its own copies.

  python3 search.py --out DIR --models toyota/prado lexus/gx porsche/cayenne \
      --min-price 1500 --max-price 6000 --min-year 2012 [--max-year 2026] [--max-km 150000] [--per-model N] [--photos N] [--download]

Models come from DIR/models.json, written for this search; ones without `sites` are resolved first (resolve.py).
Another model on a model's page is dropped by its `match` and `skip` names (right_model).
Every car that passes the filters is kept; only duplicates are merged (--per-model N caps it, for a quick look).
A page that never loads (after retries) is listed at the end and in stats.json `failed_pages`: its cars are missing.
A model page the site says doesn't exist (OpenSooq's 410) is a wrong page name, not an outage: `wrong_pages`.
Prints one line per site and model as each finishes, so a slow site shows while the search runs.
Writes DIR/cars.json (page data, with the seller's phone when the site gives one), DIR/dedup.json
({"merged": the certain merges and why}), DIR/checks/pair_N.json (look-alike pairs on the page, one file each,
for the checker agents; see references/dup-checker.md), DIR/stats.json (counts per site) and DIR/img/.
Cars without photos are dropped.
"""
import argparse, datetime, json, os, shutil, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.dirname(__file__))
import site_4sale, site_opensooq, site_motorgy, site_alsayer, resolve, common
from common import download, in_title, JUNK, FAILED, WRONG
from dedup import dedup, candidates

SITES = {"4sale": site_4sale, "opensooq": site_opensooq, "motorgy": site_motorgy,
         "alsayer": site_alsayer}


def right_model(c, m, toks):
    """False for another model on this model's page. An ad naming a `skip` model (Pajero Sport on the Pajero page) is
    dropped on every site. Motorgy's title and OpenSooq's own car name are the site's structured names, so they must
    name the model: always on Motorgy (its pages are padded with other models), on OpenSooq when the model has a
    `match` list. 4Sale titles are free text, often Arabic or without the model, so only `skip` applies there."""
    if in_title(c["title"] + " " + (c["trim"] or ""), m.get("skip") or []):
        return False
    if c["source"] == site_motorgy.NAME:
        return in_title(c["title"], toks)
    if c["source"] == site_opensooq.NAME and m.get("match") and c["trim"]:
        return in_title(c["trim"], toks)
    return True


def fetch_one(job):
    site, key, m, lo, hi = job
    t = time.time()
    toks = tuple(resolve.tokens(key, m))
    paths = m["sites"].get(site) or []
    if site != "alsayer" and not paths:
        return site, key, []
    try:  # Al-Sayer: two small sites, read whole and matched by make/model name
        found = site_alsayer.fetch(key, m, toks, lo, hi) if site == "alsayer" else SITES[site].fetch(paths, key, lo, hi)
    except Exception as e:  # one broken site must not stop the search, but it is reported
        print(f"  ! {site} {key}: {str(e)[:150]}"); FAILED.append(f"{site} {key}: {str(e)[:150]}")
        return site, key, []
    found = [c for c in found if right_model(c, m, toks)]
    wrong = [p for p in paths if f"{SITES[site].NAME} {p}" in WRONG]  # "0 ads" there would read like none for sale
    print(f"  {SITES[site].NAME} {key}: " + (f"not searched, no page named {', '.join(wrong)}" if wrong else f"{len(found)} ads, {time.time() - t:.0f} s"))
    return site, key, found


def _try(f, c, fallback):
    try:
        return f(c)
    except Exception as e:
        print(f"  ! photos for {c['id']}: {e}")
        return fallback


def ad(c, out):
    """One ad as the checker agent sees it: the facts, the seller's own text and its first 6 photos (enough to tell two cars apart)."""
    d = {k: c.get(k) for k in ("id", "source", "trim", "year", "km", "price", "color", "phone", "posted", "dealer", "title", "desc", "url")}
    local = [os.path.join(out, "img", f"{c['id']}_{i}.jpg") for i in range(6)]
    d["photos"] = [os.path.abspath(f) for f in local if os.path.exists(f)]
    return d


def pick3(n):
    """Claude.ai page: which of a car's n photos to download: the 1st, 4th and 7th; with fewer than 7 the 1st, 4th and
    last; with fewer than 4 the 1st and last (or just the one)."""
    return list(dict.fromkeys([0, 3, 6] if n >= 7 else [0, 3, n - 1] if n >= 4 else [0, n - 1]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--models", nargs="+", required=True)
    ap.add_argument("--min-price", type=int, default=100, help="below this is a placeholder price, not a real one")
    ap.add_argument("--max-price", type=int, default=10**7)
    ap.add_argument("--min-year", type=int, default=0)
    ap.add_argument("--max-year", type=int, default=9999)
    ap.add_argument("--min-km", type=int, default=0, help="0 keeps new cars (0 km); review flags a km the ad contradicts")
    ap.add_argument("--max-km", type=int, default=10**7)
    ap.add_argument("--per-model", type=int, default=0, help="0 = keep every car (default)")
    ap.add_argument("--photos", type=int, default=0, help="fast page: photos per car; 0 = every photo the ad has")
    ap.add_argument("--sites", nargs="+", default=list(SITES))
    ap.add_argument("--days", type=int, default=30, help="4Sale and OpenSooq: only ads from the last N days (0 = all); "
                    "Motorgy, Car World and Lexus are shops listing their current stock, so they are read whole")
    ap.add_argument("--download", action="store_true", help="Claude.ai page: download 3 photos per car (pick3); default: link them")
    a = ap.parse_args()
    sys.stdout.reconfigure(line_buffering=True)  # progress lines show as they happen, even when the output is piped
    if shutil.which("caffeinate"):  # keep the Mac awake until the search ends: an idle sleep once froze a search for 16 min
        subprocess.Popen(["caffeinate", "-i", "-w", str(os.getpid())])
    common.SINCE = str(datetime.date.today() - datetime.timedelta(days=a.days)) if a.days else ""
    t0 = time.time()

    models = resolve.load(a.out)
    todo = [k for k in a.models if k in models and "sites" not in models[k]]
    if todo:
        print("resolving site slugs for", todo)
        models = resolve.main(todo, a.out)
    for k in [k for k in a.models if k not in models]:
        print(f"skip {k}: add it to {a.out}/models.json first"); a.models.remove(k)

    jobs = [(s, k, models[k], a.min_price, a.max_price) for k in a.models for s in a.sites]
    with ThreadPoolExecutor(8) as ex:
        results = list(ex.map(fetch_one, jobs))

    stats = {s: {"in_price_range": 0, "kept_after_filters": 0} for s in a.sites}
    cars, seen = [], set()
    for site, key, found in results:
        stats[site]["in_price_range"] += len(found)
        for c in found:
            if c["id"] in seen or not (a.min_year <= c["year"] <= a.max_year) or not (a.min_km <= c["km"] <= a.max_km) \
                    or JUNK.search(c["title"] + " " + c["desc"]):
                continue
            seen.add(c["id"]); cars.append(c); stats[site]["kept_after_filters"] += 1

    kept, merged = dedup(cars)
    removed = sum(len(g["removed"]) for g in merged)
    no_photos = sum(1 for c in kept if not c["images"])
    kept = [c for c in kept if c["images"]]  # the page is photo-first: no photos, no car

    chosen = []
    for k in a.models:
        ds = sorted((c for c in kept if c["model"] == k), key=lambda c: (-c["year"], c["km"]))
        years = [[c for c in ds if c["year"] == y] for y in dict.fromkeys(c["year"] for c in ds)]
        mix = [y[i] for i in range(max(map(len, years), default=0)) for y in years if i < len(y)]  # one per year, in turns
        took = mix[:a.per_model] if a.per_model and not k.endswith("/all") else mix  # a whole maker ('byd/all') is kept whole: sellers mislabel the type, so review sorts it
        chosen += took
        print(f"  {k}: {len(took)} kept of {len(ds)} (read in price range: {sum(len(f) for _, key, f in results if key == k)})  "
              + " ".join(f"{s}:{sum(1 for c in cars if c['model'] == k and c['source'] == SITES[s].NAME)}" for s in a.sites))

    os_cars = [c for c in chosen if c["source"] == site_opensooq.NAME]  # its list data has only the cover
    print(f"reading the photo lists of {len(os_cars)} OpenSooq ads")
    with ThreadPoolExecutor(8) as ex:
        for c, imgs in zip(os_cars, ex.map(lambda c: _try(site_opensooq.photos, c, c["images"]), os_cars)):
            c["images"] = imgs
    shutil.rmtree(os.path.join(a.out, "img"), ignore_errors=True)  # photos from an earlier run
    os.makedirs(os.path.join(a.out, "img"))
    if a.download:  # Claude.ai page: it can't show other sites' photos, so 3 photos per car are downloaded
        photo_jobs = []
        for c in chosen:
            keep = pick3(len(c["images"]))
            c["imgs"] = [f"img/{c['id']}_{i}.jpg" for i in keep]
            photo_jobs += [(c["images"][i], os.path.join(a.out, f)) for i, f in zip(keep, c["imgs"])]
        with ThreadPoolExecutor(12) as ex:
            list(ex.map(download, photo_jobs))
        out = []
        for c in chosen:
            c["imgs"] = [f for f in c["imgs"] if os.path.exists(os.path.join(a.out, f))]
            if not c["imgs"]:
                continue  # the page is photo-first
            out.append(c)
    else:  # fast page: the photos' web addresses; the page loads them from the sites
        for c in chosen:
            c["imgs"] = c["images"][:a.photos or None]
        out = chosen
    pairs = candidates(out)
    # the checker agents look at photo files: fetch the first 6 of each car in a pair (the ones not downloaded yet)
    pair_cars = {c["id"]: c for x, y, _ in pairs for c in (x, y)}.values()
    jobs = [(u, os.path.join(a.out, "img", f"{c['id']}_{i}.jpg")) for c in pair_cars for i, u in enumerate(c["images"][:6])]
    print(f"downloading photos of {len(pair_cars)} look-alike cars for the checker")
    with ThreadPoolExecutor(12) as ex:
        list(ex.map(download, [j for j in jobs if not os.path.exists(j[1])]))
    shutil.rmtree(os.path.join(a.out, "checks"), ignore_errors=True)  # old pairs from an earlier run
    os.makedirs(os.path.join(a.out, "checks"))
    for i, (x, y, hints) in enumerate(pairs, 1):
        json.dump({"pair": i, "hints": hints, "a": ad(x, a.out), "b": ad(y, a.out)},
                  open(os.path.join(a.out, "checks", f"pair_{i}.json"), "w"), ensure_ascii=False, indent=1)
    for c in out:
        for f in ("images", "seller"):
            c.pop(f, None)

    stats = {"days": a.days, "sites": stats, "ads_after_filters": len(cars), "duplicates_removed": removed, "pairs_to_check": len(pairs),
             "no_photos": no_photos, "unique_cars": len(kept), "on_page": len(out), "seconds": round(time.time() - t0)}
    json.dump(out, open(os.path.join(a.out, "cars.json"), "w"), ensure_ascii=False, indent=1)
    json.dump({"merged": merged}, open(os.path.join(a.out, "dedup.json"), "w"), ensure_ascii=False, indent=1)
    stats["failed_pages"], stats["wrong_pages"] = sorted(set(FAILED)), WRONG
    json.dump(stats, open(os.path.join(a.out, "stats.json"), "w"), indent=1)
    print(json.dumps(stats))
    if FAILED:
        print(f"\n⚠ {len(stats['failed_pages'])} page(s) did not load after 3 tries. Their cars are MISSING (this is not 'none for sale'):")
        for u in stats["failed_pages"]:
            print("   ", u)
    for w in WRONG:  # the site answered "no such page": waiting won't help, the page name must be fixed
        print(f"\n⚠ {w}: no such page (wrong page name?). Its cars are MISSING. Fix `sites` in models.json (step 2) and search again.")


if __name__ == "__main__":
    main()
