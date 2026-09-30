"""Motorgy (motorgy.com): server-rendered cards, 12 per list page (?pn=2, 3…; hdncountAll says how many cars),
detail page has the specs, ~8+ photos and a phone (tel: link). The phone is Motorgy's sales line, not the owner's: it is shown
on the page but never used to match duplicates. The og:description is the same stock text on every car,
so it is not read."""
import html as H, json, math, re
from concurrent.futures import ThreadPoolExecutor
from common import get, new_car, fix_km, phone

NAME = "Motorgy"
BASE = "https://www.motorgy.com"


def models(brand):
    h = get(f"{BASE}/en/used-cars/{brand}")
    return [(f"{brand}/{m}", m, 0) for m in sorted(set(re.findall(rf'/en/used-cars/{re.escape(brand)}/([a-z0-9-]+)', h)))]


def cards(bm):
    """Every car of a model: exactly the list pages Motorgy reports (hdncountAll cars, 12 a page), read in parallel."""
    first = get(f"{BASE}/en/used-cars/{bm}", need="hdncountAll")  # on every list page, even a model with no cars
    total = re.search(r'id="hdncountAll" value="(\d+)"', first)
    n = math.ceil(int(total.group(1)) / 12) if total else 1
    if n > 100:
        print(f"  ⚠ Motorgy {bm}: {n} list pages, reading them all")
    with ThreadPoolExecutor(8) as ex:
        pages = [first] + list(ex.map(lambda i: get(f"{BASE}/en/used-cars/{bm}?pn={i}", need="hdncountAll"), range(2, n + 1)))
    out = {}
    for b in (b for h in pages for b in re.findall(r'<div class="car-card">(.*?)</div>\s*</div>\s*</div>\s*</a>', h, re.S)):
        link = re.search(r'href="(/en/car-details/[^"]+/(\d+))"', b)
        price = re.search(r'([\d,]+)\s*KWD\s*</p>', b)
        if link and price and link.group(2) not in out:
            out[link.group(2)] = (link.group(1), int(price.group(1).replace(",", "")))
    return out


def _photos(cid, h):
    """The ad's photos: the gallery list (lbGallery) plus the cover. Newer ads keep photos in CarImages/<id>/ and the
    cover is not in the list; older ads keep them in CarImages/ directly and their cover slot shows Motorgy's logo,
    so the cover is only taken from the car's own folder."""
    m = re.search(r'var lbGallery = (\[[^\]]*\])', h)
    try:
        gallery = json.loads(m.group(1)) if m else []
    except ValueError:
        gallery = []
    cover = re.search(r'v4-gallery__main[^>]*>\s*<img src="([^"]+)"', h)
    cover = [cover.group(1)] if cover and f"/CarImages/{cid}/" in cover.group(1) else []
    found = cover + gallery or re.findall(rf'https://motorgy\.b-cdn\.net/live/CarImages/{cid}/[^"?\s\']+', h)
    return [u.split("?")[0] for u in dict.fromkeys(found)]


def detail(cid, path, price, key):
    h = get(BASE + path, need="__label")  # the spec rows: a page without them is a block page, not the car
    spec = {k.strip(): H.unescape(v).strip() for k, v in re.findall(
        r'__label[^"]*">([^<]+)</span>\s*<span class="[^"]*__value[^"]*">([^<]*)</span>', h)}
    title = re.search(r'<h1[^>]*>([^<]*)', h)
    desc = re.search(r'<p class="v4-description__text">(.*?)</p>', h, re.S)  # Motorgy's write-up
    tel = re.search(r'href="tel:([^"]+)"', h)
    imgs = _photos(cid, h)
    y = spec.get("Year", "")
    name = H.unescape(title.group(1)).strip() if title else ""
    trim = re.sub(rf"^\d{{4}}\s+({re.escape(spec.get('Brand', ''))}\s+)?", "", name, flags=re.I)  # '2015 BMW 730Li' -> '730Li'
    return new_car(
        id="m" + cid, source=NAME, model=key, trim=trim or None, year=int(y) if y.isdigit() else 0, km=fix_km(spec.get("Mileage")),
        price=price, trans=spec.get("Transmission") or "Automatic", color=spec.get("Ext. Color"),
        imp="Kuwait" if "kuwait" in spec.get("GCC Spec", "").lower() else (spec.get("GCC Spec") or None),
        title=name,
        desc=H.unescape(re.sub(r"<[^>]+>", " ", desc.group(1))).strip() if desc else "",
        images=imgs, url=BASE + path, posted=None, dealer=False,
        phone=phone(H.unescape(tel.group(1))) if tel else None, seller=None)


def fetch(paths, key, lo, hi):
    """paths: Motorgy 'brand/model' slugs. A model page is padded with other models of the brand: search.py keeps
    only the cars whose title names the model."""
    jobs = []
    for bm in paths:
        jobs += [(cid, path, price) for cid, (path, price) in cards(bm).items() if lo <= price <= hi]
    with ThreadPoolExecutor(8) as ex:
        return list(ex.map(lambda j: detail(*j, key), jobs))
