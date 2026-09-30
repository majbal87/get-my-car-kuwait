"""OpenSooq (kw.opensooq.com): Next.js. Phone is masked ('669724XX').
The list data has only the cover photo; photos() reads the ad page's gallery for the cars that make the page."""
import re, time
from concurrent.futures import ThreadPoolExecutor
from common import get, next_data, new_car, fix_km, phone, recent, FAILED, GONE, WRONG

NAME = "OpenSooq"
IMG = "https://opensooq-imagesv2.os-cdn.com/"  # the plain path is the original photo (1920 px)
BASE = "https://kw.opensooq.com/en/cars/cars-for-sale/"


def serp(path):
    p = next_data(get(BASE + path, need="__NEXT_DATA__"))
    return p.get("serpApiResponse") if p else None


def brands():
    s = serp("") or {}
    vals = ((s.get("filters") or {}).get("car_make") or {}).get("values") or []
    return [(v["url_name"], v.get("label_en") or v["url_name"], v.get("count", 0)) for v in vals]


def models(brand):
    s = serp(brand) or {}
    vals = ((s.get("filters") or {}).get("car_model") or {}).get("values") or []
    return [(f"{brand}/{v['url_name']}", v.get("label_en") or v["url_name"], v.get("count", 0)) for v in vals]


def car(x, key):
    sub = x.get("subtitle") or ""
    y = re.match(r"(\d{4})", sub)
    img = x.get("image_uri")
    make = str(x.get("highlights") or "").split("»")[0].strip()  # 'Mercedes Benz » S-Class » 2,011 » Used'
    trim = re.sub(r"^\d{4}\s+", "", sub)                        # '2011 Mercedes Benz S-Class S 350' -> 'S-Class S 350'
    trim = trim[len(make):].strip() if make and trim.lower().startswith(make.lower()) else trim
    return new_car(
        id="o" + str(x["id"]), source=NAME, model=key, trim=trim or None, year=int(y.group(1)) if y else 0,
        km=fix_km(x.get("kilometers_Cars_value_i")), price=int(float(re.sub(r"[^\d.]", "", x.get("price_amount") or "0") or 0)),
        title=(x.get("title") or sub), desc=x.get("masked_description"),
        images=[IMG + img] if img else [],
        url=f"https://kw.opensooq.com/en/search/{x['id']}", posted=x.get("inserted_date"),
        dealer=x.get("user_target_type") not in (None, "free"), phone=phone(x.get("phone_number")),
        seller=x.get("member_id"))


def photos(c):
    """Every photo of one ad, in order, from its page's gallery (only the ad's own; related ads are elsewhere)."""
    h = get(c["url"], need="gallery").replace('\\"', '"')
    i = h.find('"gallery":{')
    j = h.find('"media":[', i)
    if i < 0 or j < 0:
        return c["images"]
    seg = h[j:h.find("]", j)]
    uris = list(dict.fromkeys(re.findall(r'"uri":"([^"]+)"', seg)))
    return [IMG + u for u in uris if not u.endswith((".mp4", ".mov"))] or c["images"]


def list_ads(bm):
    """Every ad on a model's list pages: exactly the pages OpenSooq reports (listings.meta.pages), read in parallel."""
    first = serp(bm)
    if BASE + bm in GONE:  # 410: OpenSooq has no page by this name (a wrong slug), so trying again can't help
        print(f"  ⚠ OpenSooq {bm}: no such page (wrong page name?)")
        WRONG.append(f"{NAME} {bm}")
        return []
    if not first:  # the page came without its ads data (an error page or a cut-off page): one more try
        time.sleep(5)
        first = serp(bm)
    if not first:  # listed under failed_pages, so it never reads as "no cars for sale" (an empty model still has the data)
        FAILED.append(BASE + bm)
        return []
    n = (first.get("listings", {}).get("meta") or {}).get("pages", 1)
    if n > 100:
        print(f"  ⚠ OpenSooq {bm}: {n} list pages, reading them all")
    with ThreadPoolExecutor(8) as ex:
        pages = [first] + list(ex.map(lambda i: serp(f"{bm}?page={i}"), range(2, n + 1)))
    FAILED.extend(f"{BASE}{bm}?page={i}" for i, s in enumerate(pages, 1) if not s)
    return [x for s in pages if s for x in s.get("listings", {}).get("items") or []]


def fetch(paths, key, lo, hi):
    """paths: OpenSooq 'brand/model' slugs (they differ from 4Sale's; a wrong slug gives HTTP 410 and no data)."""
    out, seen = [], set()
    for bm in paths:
        for x in list_ads(bm):
            c = car(x, key)
            if lo <= c["price"] <= hi and recent(c["posted"]) and c["id"] not in seen:
                seen.add(c["id"]); out.append(c)
    return out
