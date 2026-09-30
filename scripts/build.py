#!/usr/bin/env python3
"""Fill template.html with DIR/cars.json + DIR/meta.json, write DIR/index.html and one screenshot.
Fast page (default): a complete HTML file that opens in any browser; the photos load from the car sites.
With --claude it builds the Claude.ai page instead and packs the downloaded photos (search.py --download, 3 per car):
one file per car (ph/<id>.json), loaded when its card comes into view. If the photos pass 250 MB, the last photo of
the car with the most is left out, again and again (the ad has them all). DIR/files.json lists what to publish; over
250 files or 60 MB the rest goes in files_2.json, files_3.json…, each published to the same url after the first.

  python3 build.py --out DIR --title "Family SUVs Kuwait" [--claude]

DIR/meta.json is written by Claude for each search: eyebrow, h1, h1_accent, lede, budget, pickline, checked, sources
and, when Claude had to judge a vague request, reading (a short list; the page shows it closed at the bottom).
The stats line (ads checked, duplicates merged) is added from DIR/stats.json; merges made after the
search (`also` entries with "checked": true, from checks.py or by hand) are added to the duplicate count.
A site or model that couldn't be checked (stats.json failed_pages, wrong_pages) gets a warning at the top of the page.
"""
import argparse, base64, glob, json, os, shutil, subprocess, sys
sys.path.insert(0, os.path.dirname(__file__))
from resolve import load
from common import norm

SK = os.path.join(os.path.dirname(__file__), "..")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

ap = argparse.ArgumentParser()
ap.add_argument("--out", required=True)
ap.add_argument("--title", required=True)
ap.add_argument("--claude", action="store_true", help="Claude.ai page: pack the downloaded photos with it")
a = ap.parse_args()

models = load(a.out)
cars = json.load(open(os.path.join(a.out, "cars.json")))
meta = json.load(open(os.path.join(a.out, "meta.json")))
st = json.load(open(os.path.join(a.out, "stats.json")))
used = {c["model"] for c in cars}
for c in cars:
    c["name"], c["brand"] = models[c["model"]]["name"], models[c["model"]]["brand"]
sites = [s for s, v in st["sites"].items() if v["kept_after_filters"]]
names = {"4sale": "4Sale", "opensooq": "OpenSooq", "motorgy": "Motorgy", "alsayer": "Al-Sayer"}
# pages that didn't load or don't exist, by site and model: the page warns, so they never look like "none for sale"
missing = {}
for p in st.get("failed_pages", []) + st.get("wrong_pages", []):
    s = next((s for s in names if s in norm(p)), "alsayer")  # 'q84sale.com' has '4sale'; Lexus certified is Al-Sayer's
    missing.setdefault(names[s], set()).update(m["name"] for k, m in models.items()
                                               if any(norm(x) in norm(p) for x in [k] + m.get("sites", {}).get(s, [])))
meta["missing"] = [[s, ", ".join(sorted(ms))] for s, ms in missing.items()]
manual = sum(1 for c in cars for x in c.get("also") or [] if x.get("checked"))
meta["stats"] = {"ads": st["ads_after_filters"], "dupes": st["duplicates_removed"] + manual,
                 "n_sites": len(sites), "site_names": ", ".join(names[s] for s in sites)}
if not a.claude:  # fast page: imgs are the sites' photo addresses, shown as they are
    for c in cars:
        c["n"] = len(c["imgs"])
# Claude.ai limits: a version holds 511 files and 256 MB; one publish sends 255 files and 64 MB; a file is at most 15 MB.
# Each car is one file (ph/<id>.json, its up to 3 photos), so a page holds up to 500 cars, published in batches.
TOTAL, BATCH_MB, BATCH_FILES = 250 * 2**20, 60 * 2**20, 250
if a.claude and len(cars) > 500:
    sys.exit(f"⚠ {len(cars)} cars: too many for a Claude.ai page (500 at most). Make the fast page, or narrow the search.")
size = lambda f: os.path.getsize(os.path.join(a.out, f))
for c in cars if a.claude else []:
    c["imgs"] = [f for f in c["imgs"] if os.path.exists(os.path.join(a.out, f))]
total = lambda: sum(size(f) for c in cars for f in c["imgs"]) * 4 // 3  # base64 adds a third
trimmed = 0
while a.claude and total() > TOTAL:
    max(cars, key=lambda c: len(c["imgs"]))["imgs"].pop(); trimmed += 1
mb = total() / 2**20 if a.claude else 0
shutil.rmtree(os.path.join(a.out, "ph"), ignore_errors=True)
for f in glob.glob(os.path.join(a.out, "files*.json")):
    os.remove(f)  # publish lists from an earlier build
batches = [[]]
if a.claude:
    os.makedirs(os.path.join(a.out, "ph"))
for c in cars if a.claude else []:
    c["n"], c["more"] = len(c["imgs"]), f"ph/{c['id']}.json"
    json.dump(["data:image/jpeg;base64," + base64.b64encode(open(os.path.join(a.out, f), "rb").read()).decode() for f in c["imgs"]],
              open(os.path.join(a.out, c["more"]), "w"))
    c["imgs"] = []  # the page loads the file when the car comes into view
    b = batches[-1]
    if len(b) >= BATCH_FILES or sum(map(size, b)) + size(c["more"]) > BATCH_MB:
        batches.append(b := [])
    b.append(c["more"])
for i, b in enumerate(batches if a.claude else [], 1):  # files.json, files_2.json…: one publish each, to the same url
    json.dump([{"path": f} for f in b], open(os.path.join(a.out, "files.json" if i == 1 else f"files_{i}.json"), "w"), indent=0)

data = {"meta": meta, "models": {k: {f: v for f, v in models[k].items() if f not in ("sites", "match", "skip")} for k in used}, "cars": cars}
t = open(os.path.join(SK, "template.html")).read()
t = t.replace("/*TITLE*/", a.title).replace("/*DATA*/", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))
doc = ('<!doctype html><html><head><meta charset="utf-8">'
       '<meta name="viewport" content="width=device-width, initial-scale=1">' + t + "</html>")  # what Claude.ai wraps around it
open(os.path.join(a.out, "index.html"), "w").write(t if a.claude else doc)

prev = os.path.join(a.out, "_preview.html")
open(prev, "w").write(doc)
SHOTS = {"_screenshot.png": "?theme=dark"}  # one view is enough: the data is what breaks, and each shot takes ~30 s
for name, q in SHOTS.items() if os.path.exists(CHROME) else []:  # one at a time: headless Chrome shares its profile
    if os.path.exists(os.path.join(a.out, name)):
        os.remove(os.path.join(a.out, name))
    # headless Chrome loads every photo on the page first: a big page (200+ cars) takes over a minute, so it then
    # gets a quick shot without photos (layout and data are what to check)
    for no_photos in (False, True):
        try:
            subprocess.run([CHROME, "--headless", "--disable-gpu", "--hide-scrollbars", f"--screenshot={os.path.join(a.out, name)}",
                            "--window-size=1280,2200", "--virtual-time-budget=15000", "file://" + os.path.abspath(prev) + q]
                           + ["--blink-settings=imagesEnabled=false"] * no_photos, capture_output=True, timeout=60)
        except subprocess.TimeoutExpired:
            pass  # the screenshot is usually written already
        if os.path.exists(os.path.join(a.out, name)):
            break
shots = [n for n in SHOTS if os.path.exists(os.path.join(a.out, n))]
print(f"wrote {a.out}/index.html ({len(cars)} cars, {len(t)//1024} KB); screenshot: {', '.join(shots) or 'none'}"
      + (" (without photos: the page is big)" if shots and no_photos else ""))
if a.claude:
    print(f"photos: {sum(c['n'] for c in cars)} in {len(cars)} files, {mb:.0f} MB"
          + (f"; {trimmed} left out to fit the page" if trimmed else "")
          + f"; publish lists, in order, to the same url: " + ", ".join(["files.json"] + [f"files_{i}.json" for i in range(2, len(batches) + 1)]))
else:
    print(f"photos: {sum(c['n'] for c in cars)}, linked from the sites (nothing packed)")
