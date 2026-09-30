"""Al-Sayer's own used-car sites (no phone per car; the page links to each car's ad).

- Al Sayer Car World (alsayercarworld.com): all brands, Laravel + Inertia JSON in <div id="app" data-page>.
  7 cars per page. Only status "Live" is for sale; "Reserved" is skipped.
- Lexus certified (lexus.com.kw/en/pre-owned): Next.js payload, one page with every car.
Lexus cars without their own gallery show only the maker's studio picture: that counts as no photos.
Both give the chassis number (VIN), so the same car on both sites is matched exactly (dedup.py).
Toyota Kuwait's used stock (toyota.com.kw) has no photos, so it is not used.
"""
import difflib, html as H, json, re, threading
from concurrent.futures import ThreadPoolExecutor
from common import get, new_car, norm, matches, FAILED

NAME = "Al-Sayer"
CW = "https://www.alsayercarworld.com"
LEX = "https://www.lexus.com.kw"
_lock, _cache = threading.Lock(), {}


def _page(n):
    h = get(f"{CW}/en/search?page={n}", need="data-page=")
    m = re.search(r'<div id="app" data-page="([^"]*)"', h)
    return json.loads(H.unescape(m.group(1)))["props"]["listings"] if m else {}


def car_world():
    first = _page(1)
    rows = list(first.get("data") or [])
    with ThreadPoolExecutor(6) as ex:
        for p in ex.map(_page, range(2, (first.get("last_page") or 1) + 1)):
            rows += p.get("data") or []
    return [r for r in rows if r.get("status") == "Live"]


def lexus():
    h = get(f"{LEX}/en/pre-owned", need="chassis")
    s = "".join(json.loads('"' + m + '"') for m in re.findall(r'self\.__next_f\.push\(\[1,"((?:[^"\\]|\\.)*)"\]\)', h))
    for m in re.finditer(r'\[\{"id":', s):
        try:
            arr, _ = json.JSONDecoder().raw_decode(s[m.start():])
        except ValueError:
            continue
        if arr and isinstance(arr[0], dict) and "chassis" in arr[0]:
            return arr
    FAILED.append(f"{LEX}/en/pre-owned")  # the page came without its cars: they are missing, not sold out
    return []


def everything():
    """Both sites, fetched once per search (the search asks for every model in parallel)."""
    with _lock:
        if "all" not in _cache:
            try:
                cw = car_world()
            except Exception as e:
                print(f"  ! Al Sayer Car World: {e}"); FAILED.append(f"Al Sayer Car World: {str(e)[:150]}"); cw = []
            try:
                lx = lexus()
            except Exception as e:
                print(f"  ! Lexus certified: {e}"); FAILED.append(f"Lexus certified: {str(e)[:150]}"); lx = []
            _cache["all"] = (cw, lx)
        return _cache["all"]


def same_brand(make, m, key):
    a = norm(make)
    return any(a == norm(b) or difflib.SequenceMatcher(None, a, norm(b)).ratio() >= 0.75 for b in (m["brand"], key.split("/")[0]))


def is_model(name, toks):
    """'FORTUNER_N' starts with 'Fortuner'; 'EVOQUE' ends 'Range Rover Evoque'."""
    n = norm(name)
    return matches(name, toks) or any(len(n) >= 4 and norm(t).endswith(n) for t in toks)


def fetch(key, m, toks, lo, hi):
    cw, lx = everything()
    out = []
    for r in cw:
        if not (same_brand(r.get("make"), m, key) and is_model(r.get("model"), toks) and lo <= (r.get("retail_price") or 0) <= hi):
            continue
        info = [r.get("certification_type"), "warranty" if r.get("warranty") else None, r.get("model_type")]
        out.append(new_car(
            id=f"a{r['id']}", source=NAME, model=key, year=r.get("year") or 0, km=r.get("kilometers") or 0,
            price=int(r["retail_price"]), trans=(r.get("transmission") or "Automatic").capitalize(), color=r.get("exterior_color"),
            title=f"{r.get('year')} {r.get('make')} {r.get('model')}", desc=" · ".join(x for x in info if x),
            images=[x["original_url"] for x in r.get("media") or [] if x.get("original_url")],
            url=f"{CW}/en/{(r.get('dealership') or {}).get('slug', 'alsayer-showroom')}/listing/{r['slug']}",
            posted=(r.get("created_at") or "")[:10] or None, dealer=True, vin=r.get("vin_number")))
    if norm(m["brand"]) == "lexus":
        for r in lx:
            label = (((r.get("variant") or {}).get("display_name") or {}).get("en") or "")  # 'NX350 PREMIER', '25UX300H-PREMIER'
            short = re.sub(r"^(lexus\s+|\d\d(?=[a-z]))", "", label, flags=re.I)
            short = re.sub(r"\s+\d{4}$", "", short)  # 'LX600 2023'
            label = label or short
            name = (r.get("name") or {}).get("en") if isinstance(r.get("name"), dict) else None
            name = name or f"{r.get('model_year')} Lexus {short}"
            if not (is_model(short, toks) and lo <= (r.get("price") or 0) <= hi):
                continue
            slug = (re.match(r"[a-z]+", short.lower()) or [""])[0]
            out.append(new_car(
                id=f"l{r['id']}", source=NAME, model=key, trim=short or None, year=r.get("model_year") or 0, km=r.get("mileage") or 0,
                price=int(r["price"]), trans=r.get("transmission") or "Automatic",
                color=((r.get("color_wheel_base_id") or {}).get("name") or {}).get("en"),
                title=name, desc=f"Lexus Certified Pre-Owned · {label}",
                images=[u for u in r.get("images") or [] if "/gallery/" in u],  # the rest is the maker's studio picture
                url=f"{LEX}/en/pre-owned/details/{slug}-{r['id']}",
                posted=None, dealer=True, vin=r.get("chassis")))
    return out
