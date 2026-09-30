"""4Sale (q84sale.com): Next.js pages, __NEXT_DATA__ holds the data. Full seller phone in the list data."""
import time
from concurrent.futures import ThreadPoolExecutor
from common import get, next_data, new_car, fix_km, phone, recent, FAILED

NAME = "4Sale"
BASE = "https://www.q84sale.com/en/"


def props(path):
    return next_data(get(BASE + path, need="__NEXT_DATA__"))


def brands():
    p = props("automotive/used-cars/1") or {}
    return [(c["slug"], c["slug"], c.get("listings_count", 0)) for c in p.get("catChilds") or []]


def models(brand):
    p = props(f"automotive/used-cars/{brand}/1") or {}
    return [(c["slug"], c.get("name_en") or c["slug"], c.get("listings_count", 0)) for c in p.get("catChilds") or []]


def detail(l, key):
    try:
        return _detail(l, key)
    except Exception as e:  # one odd ad (e.g. a new attribute type) must not wipe out the model
        print(f"  ! 4Sale ad {l.get('id')}: {str(e)[:150]}")  # short: an error can carry a whole page
        FAILED.append(f"{BASE}listing/{l.get('slug')}")  # the car is missing, so it is reported
        return None


def _detail(l, key):
    p = props(f"listing/{l['slug']}")
    if p and p.get("pageStatus") == 404:
        return None  # the ad was taken down after the list was read: sold or removed, not a page that failed
    L = p["listing"]
    a = {}
    for x in L.get("attrsAndVals") or []:
        v = x["valData"]
        a[(x.get("attrData") or {}).get("name_en")] = (v.get("name_en") or v.get("val")) if isinstance(v, dict) else v  # file attrs (Inspection Report) have no name_en
    y = str(a.get("Year") or "")
    return new_car(
        id="q" + str(l["id"]), source=NAME, model=key, year=int(y) if y.isdigit() else 0,
        km=fix_km(a.get("Mileage")), price=int(float(L["price"])), trans=a.get("Transmission") or "Automatic",
        color=a.get("Color Exterior"), imp=a.get("Import"), body=a.get("Body Type"), cond=a.get("Body Condition"),
        title=L["title"], desc=L["description"], images=L.get("images") or [],
        url=f"https://www.q84sale.com/en/listing/{l['slug']}", posted=(L.get("date_published") or "")[:10],
        dealer=l.get("user_type") not in (None, "normal"), phone=phone(l.get("phone")), seller=l.get("user_id"))


def list_ads(bm):
    """Every ad on a model's list pages: exactly the pages 4Sale reports (totalPages), read in parallel."""
    first = props(f"automotive/used-cars/{bm}/1")
    if not first:  # the page came without its data (an error or cut-off page): one more try
        time.sleep(5)
        first = props(f"automotive/used-cars/{bm}/1")
    if not first:  # listed under failed_pages, so it never reads as "no cars for sale" (an empty model still has the data)
        FAILED.append(f"{BASE}automotive/used-cars/{bm}/1")
        return []
    n = first["totalPages"]
    if n > 100:
        print(f"  ⚠ 4Sale {bm}: {n} list pages, reading them all")
    with ThreadPoolExecutor(8) as ex:
        pages = [first] + list(ex.map(lambda i: props(f"automotive/used-cars/{bm}/{i}"), range(2, n + 1)))
    FAILED.extend(f"{BASE}automotive/used-cars/{bm}/{i}" for i, pg in enumerate(pages, 1) if not pg)
    return [l for pg in pages if pg for l in pg["listings"] if l.get("title") and l.get("price")]


def fetch(paths, key, lo, hi):
    """paths: 4Sale 'brand/model' slugs. Returns cars in the common shape, price already in range."""
    ads = [l for bm in paths for l in list_ads(bm)]
    seen = set()
    # date_sort: the date the ad was posted or last refreshed by its seller (the order 4Sale lists them in)
    ads = [l for l in ads if lo <= l["price"] <= hi and recent(l.get("date_sort") or l.get("date_published"))
           and not (l["id"] in seen or seen.add(l["id"]))]
    done = []

    def one(l):
        c = detail(l, key)
        done.append(1)
        if len(done) % 100 == 0:  # a wide search can open hundreds of ad pages: show it is moving
            print(f"  4Sale {key}: {len(done)}/{len(ads)} ad pages")
        return c
    with ThreadPoolExecutor(10) as ex:
        return [c for c in ex.map(one, ads) if c]
