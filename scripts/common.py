"""Shared helpers for the car-search site scripts.

Every site script returns cars in one shape (see new_car). The phone is used to match
duplicates and is shown on the page so the buyer can call the seller.
"""
import json, os, re, subprocess, time

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"


FAILED = []  # pages that never loaded, even after retries: search.py reports them, so a blocked site never looks like "no cars"
GONE = set()  # pages the site says don't exist (HTTP 404/410)
WRONG = []  # model pages that don't exist ("OpenSooq toyota/fj-cruiser-xx"): a wrong page name in models.json, not an outage
SINCE = ""  # only ads dated on or after this day ("2026-08-28"), set by search.py --days; "" = every ad


def recent(date):
    """Is the ad new enough for the buyer's window? An ad without a date is kept."""
    return not SINCE or not date or date[:10] >= SINCE


def get(url, need=None):
    """Fetch a page. A failed answer (timeout, error, "too many requests", or a block page without `need` in it) is
    tried again after 3 and then 6 seconds. If it still fails, the URL goes in FAILED and "" is returned."""
    for wait in (3, 6, None):
        r = subprocess.run(["curl", "-sL", "--max-time", "25", "-A", UA, "-w", "\n%{http_code}", url],
                           capture_output=True, text=True, errors="replace")  # a page cut inside an Arabic letter must not crash
        body, _, code = r.stdout.rpartition("\n")
        # curl exit code not 0: it stopped early (time limit, dropped connection), so the page may be cut off
        if r.returncode == 0 and code in ("404", "410"):
            GONE.add(url)
            return body  # that page doesn't exist (e.g. a wrong model slug): a real answer, so not tried again
        if r.returncode == 0 and code == "200" and body and (not need or need in body):
            return body
        if wait:
            time.sleep(wait)
    FAILED.append(url)
    return ""


def next_data(html):
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    return json.loads(m.group(1))["props"]["pageProps"] if m else None


# Arabic spelling variants sellers mix (أ/إ/آ -> ا, ى -> ي, ة -> ه); tashkeel and the stretch ـ are dropped
AR = str.maketrans("أإآىة", "ااايه", "\u064b\u064c\u064d\u064e\u064f\u0650\u0651\u0652\u0640")
KEEP = "a-z0-9ء-ي"  # Latin letters, digits and Arabic letters


def norm(s):
    """'Land-Cruiser 200' -> 'landcruiser200', 'سوبر سفاري' -> 'سوبرسفاري'. Used to compare names across sites."""
    return re.sub(f"[^{KEEP}]", "", str(s or "").lower().translate(AR))


def matches(value, tokens):
    """True when a site's model name starts with one of the model's match tokens."""
    v = norm(value)
    return bool(v) and any(v.startswith(norm(t)) for t in tokens if norm(t))


def fix_km(km):
    try:
        km = int(float(str(km).replace(",", "")))
    except (TypeError, ValueError):
        return 0
    return km * 1000 if 0 < km < 1000 else km  # sellers often type "200" for 200,000 km


def phone(p):
    """Last 8 digits of a Kuwaiti number. A masked OpenSooq number '669724XX' becomes '669724??'."""
    s = re.sub(r"[^0-9Xx]", "", str(p or "")).upper().replace("X", "?")
    if s.startswith("965") and len(s) > 8:
        s = s[3:]
    return s[-8:] if len(s) >= 8 and s.count("?") <= 2 else None


# Arabic ad phrases -> English feature chips shown on the page.
FEATURES = [
    (r'شرط\s*ال?فحص|فحص|subject to inspection|inspection allowed', 'Inspection allowed'), (r'صبغ\s*ال?وكا|original paint', 'Original paint'),
    (r'سيرف?ي?س\s*(منتظم|مناظم|وكال|بالوكال)|سرفيس منتظم|regular service|service history', 'Regular service'),
    (r'(ال)?مالك\s*(ال)?[اأ]و?ل|[اأ]ول\s*مالك|first owner|one owner', 'First owner'),
    (r'وارد\s*[:：\-]?\s*(ال)?(ساير|وكال|غانم|بابطين|ملا|الكويت|زاهد|بهبهاني)|وكال[ةه]\s*(ال)?كويت', 'Kuwait agency car'),
    (r'فتح[هة]|sunroof|panoramic', 'Sunroof'), (r'جلد|leather', 'Leather'),
    (r'كاميرا|كامير[اةه]|camera', 'Camera'),  # not كامري (Camry)
    (r'بصم[هة]|push start|keyless', 'Push start'),
    (r'دبل', '4x4'), (r'تواير\s*جد|كفرات\s*جديد', 'New tyres'), (r'ثلاج[هة]', 'Cool box'),
    (r'(خالي[هة]?|خاليه|بدون|ما\s*عليها)\s*(من\s*)?(ال)?حوادث|accident[- ]free|no accidents', 'No accidents claimed'), (r'اقساط|أقساط', 'Installments'),
    (r'ضمان|warranty', 'Warranty'),
]


# "We buy cars" and "wanted" ads are not cars for sale.
JUNK = re.compile(r"we buy|sell your car|\bwanted\b|نشتري|شراء جميع|مطلوب\s*سيار", re.I)


def in_title(title, tokens):
    """True when a token starts at a word of the title: 'Mercedes-Benz G 63 AMG' has 'G63'; 'Lexus RX 350' has no 'ES'.
    An Arabic token must be whole words: 'سوبر سفاري' is in 'باترول سوبر سفارى2023', but 'كروز' (Cruze) is not in
    'كروزر' (Cruiser): short Arabic names often start longer words."""
    words = re.findall("[a-z0-9]+|[ء-ي]+", str(title or "").lower().translate(AR))
    runs = ["".join(words[i:j]) for i in range(len(words)) for j in range(i + 1, min(i + 4, len(words)) + 1)]
    return any(t and any(r.startswith(t) if t.isascii() else r == t for r in runs) for t in map(norm, tokens))


NO = re.compile(r"(بدون|ما\s*(في|علي)(ها|ه)?|\bno|\bwithout|\bnon)[\s\-:]*$", re.I)  # "بدون فتحة", "no sunroof"


def features(text):
    text = text or ""
    return [n for p, n in FEATURES
            if any(not NO.search(text[max(0, m.start() - 15):m.start()]) for m in re.finditer(p, text, re.I))]


SEATS = re.compile(r"\b([24-9])\s*-?\s*(?:راكب|ركاب|مقاعد|seats?|seater|passengers?)", re.I)  # "7 راكب", "7-seater"
THIRD_ROW = re.compile(r"(3|ثلاث)\s*(صفوف|مقاعد)|third row|3rd row", re.I)  # sellers write "3 مقاعد" for 3 rows
DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")  # "٧ راكب" = "7 راكب"
SHOWROOM = re.compile(r"معرض|showroom", re.I)


def seats(text):
    """Seats the ad names ("7 راكب", "3 صفوف" = 7), else None: the page then shows the model's seats."""
    text = (text or "").translate(DIGITS)
    m = SEATS.search(text)
    return int(m.group(1)) if m else (7 if THIRD_ROW.search(text) else None)


def new_car(**kw):
    """The one car shape every site script returns. `trim` is the site's own name for the car without the year and
    make ('7 Series 740Li'), when the site gives one."""
    car = dict(id=None, source=None, model=None, trim=None, year=0, km=0, price=0, trans="Automatic", color=None,
               imp=None, cond=None, seats=None, title="", desc="", features=[], images=[], url=None, posted=None,
               dealer=False, phone=None, seller=None, vin=None, pick=None, flag=None)
    car.update(kw)
    car["title"], car["desc"] = (car["title"] or "").strip(), (car["desc"] or "").strip()
    text = car["title"] + " " + car["desc"]
    if not car["features"]:
        car["features"] = features(text)
    car["seats"] = car["seats"] or seats(text)
    # a 1xxxxxxx number is a company line and "معرض" a showroom: a dealer, even when the site says private
    # (Motorgy's number is its own sales line, so it says nothing about the seller)
    car["dealer"] = bool(car["dealer"] or car["source"] != "Motorgy" and ((car["phone"] or "").startswith("1") or SHOWROOM.search(text)))
    return car


COLOURS = {"white": "white", "pearl": "white", "ابيض": "white", "أبيض": "white", "black": "black", "اسود": "black",
           "أسود": "black", "silver": "silver", "فضي": "silver", "grey": "grey", "gray": "grey", "رمادي": "grey",
           "رصاصي": "grey", "red": "red", "احمر": "red", "maroon": "red", "burgundy": "red", "blue": "blue",
           "ازرق": "blue", "navy": "blue", "green": "green", "اخضر": "green", "brown": "brown", "بني": "brown",
           "beige": "beige", "بيج": "beige", "gold": "gold", "ذهبي": "gold", "champagne": "gold",
           "orange": "orange", "yellow": "yellow", "bronze": "brown"}


def colour(c):
    """Base colour for matching ('Pearl White' -> 'white'); None when unknown."""
    s = str(c or "").lower()
    for k, v in COLOURS.items():
        if k in s:
            return v
    return None


def download(job):
    """(url, out.jpg): fetch one photo and fit it in 900 px with sips (macOS): sharp on a phone, small enough
    that every photo of ~50 cars fits in one page (build.py packs them)."""
    url, out = job
    raw = out + ".src"
    code = subprocess.run(["curl", "-sL", "--max-time", "25", "-A", UA, "-o", raw, "-w", "%{http_code}", url],
                          capture_output=True, text=True).stdout
    if code == "200":
        subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "50", "-Z", "900", raw, "--out", out],
                       capture_output=True)
    if os.path.exists(raw):
        os.remove(raw)
    return os.path.exists(out)
