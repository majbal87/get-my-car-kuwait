"""Find each site's slugs for a model and save them into models.json (`sites`).
A model keyed as in the saved car list (catalogue.py, 4Sale slugs like 'toyota/land-cruiser') takes its pages from
there; any other model is looked up live on the sites.

  python3 resolve.py --out DIR porsche/cayenne mercedes-benz/g-class

  python3 resolve.py --brands              4Sale's brands with ad counts (its catalogue covers Chinese brands too)
  python3 resolve.py --models chery         4Sale's models for one brand with ad counts

Models come only from DIR/models.json, written fresh for each search (the skill has no built-in car list).
Found slugs are saved there too.

A models.json entry needs `name` and `brand`; `match` (optional) lists the names the model goes by
(default: the name without the brand, e.g. ["Cayenne"]). Sites name brands and models differently
(4Sale: 'mercedes', OpenSooq: 'lexus-ls'), so matching is by normalised name. Check the printout:
a wrong or missing slug is fixed by hand in models.json.
"""
import difflib, json, os, re, sys
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
import site_4sale, site_opensooq, site_motorgy
from common import norm

def load(out=None):
    """This search's models (DIR/models.json)."""
    path = os.path.join(out, "models.json") if out else None
    return json.load(open(path)) if path and os.path.exists(path) else {}


def tokens(key, m):
    return m.get("match") or [re.sub(rf"^{re.escape(m['brand'])}\s+", "", m["name"], flags=re.I), key.split("/")[1]]


def pick_brand(want, options):
    """want: e.g. 'mercedes-benz'; options: site slugs. Exact, then prefix, then close spelling ('bently')."""
    w = norm(want)
    by = {norm(o): o for o in options}
    if w in by:
        return by[w]
    pre = [o for n, o in by.items() if n and (w.startswith(n) or n.startswith(w))]
    if pre:
        return pre[0]
    close = difflib.get_close_matches(w, list(by), n=1, cutoff=0.8)
    return by[close[0]] if close else None


def pick_models(opts, toks, brand, every=False):
    """opts: (slug, label, count). Prefer exact name matches, else names that start with a token.
    every: the model has a `match` list (e.g. G-Class: G 63, G 500), so take every page that fits one of them."""
    def names(slug, label):
        s = slug.split("/")[-1].split("|")[-1]
        s = re.sub(r"^o\d+-", "", s)                      # OpenSooq 'o26583-lc'
        s = re.sub(rf"^({re.escape(brand)}-)+", "", s)    # OpenSooq 'lexus-ls', 'mg-mg-rx8'
        return {norm(s), norm(re.sub(r"-\d+$", "", s)), norm(label)}  # 4Sale 'highlander-2'
    t = [norm(x) for x in toks]
    exact = [o[0] for o in opts if names(o[0], o[1]) & set(t)]
    close = [o[0] for o in opts if any(difflib.get_close_matches(x, list(names(o[0], o[1])), n=1, cutoff=0.8) for x in t if len(x) >= 5)]
    longer = [o[0] for o in opts if any(n.startswith(x) for n in names(o[0], o[1]) for x in t if x)]
    shorter = [o[0] for o in opts if any(x.startswith(n) for n in names(o[0], o[1]) for x in t if len(n) >= 2)]  # OpenSooq 'fj'
    if every and (exact or longer):
        return list(dict.fromkeys(exact + longer))
    return exact or longer or shorter or close  # close: 4Sale's 'sentafe', 'corola', 'avallon'


f_models, o_models, m_models = (lru_cache(maxsize=None)(s.models) for s in (site_4sale, site_opensooq, site_motorgy))


@lru_cache(maxsize=None)
def f_brands():
    return tuple(b for b, _, _ in site_4sale.brands())


@lru_cache(maxsize=None)
def o_brands():
    return tuple(b for b, _, _ in site_opensooq.brands())


def resolve(key, m):
    brand, toks = key.split("/")[0], tokens(key, m)
    sites = {}
    fb = pick_brand(brand, f_brands()) or pick_brand(m["brand"], f_brands())
    sites["4sale"] = ([f"{fb}/{s}" for s in pick_models(fms, toks, fb, bool(m.get("match")))] if (fms := f_models(fb)) else [fb]) if fb else []
    ob = pick_brand(brand, o_brands()) or pick_brand(m["brand"], o_brands())
    sites["opensooq"] = pick_models(o_models(ob), toks, ob, bool(m.get("match"))) if ob else []
    sites["motorgy"] = []
    for b in dict.fromkeys([brand, fb, norm(m["brand"])]):
        if b and (ms := m_models(b)):
            sites["motorgy"] = pick_models(ms, toks, b, bool(m.get("match"))); break
    return sites


def main(keys, out):
    models = load(out)
    missing = [k for k in keys if k not in models]
    for k in missing:
        print(f"{k}: not in models.json. Add name, brand, body, seats, rel, note, check first.")
    keys = [k for k in keys if k in models]
    from catalogue import sites as saved
    with ThreadPoolExecutor(6) as ex:
        for k, (s, where) in zip(keys, ex.map(lambda k: (x, "car list") if (x := saved(k)) else (resolve(k, models[k]), "live"), keys)):
            models[k]["sites"] = s
            print(f"{k} ({where})", json.dumps(s))
    path = os.path.join(out, "models.json")
    extra = json.load(open(path)) if os.path.exists(path) else {}
    for k in keys:
        extra.setdefault(k, {})["sites"] = models[k]["sites"]
    os.makedirs(out, exist_ok=True)
    json.dump(extra, open(path, "w"), ensure_ascii=False, indent=1)
    return models


if __name__ == "__main__":
    ap = __import__("argparse").ArgumentParser()
    ap.add_argument("--out")
    ap.add_argument("--brands", action="store_true")
    ap.add_argument("--models", metavar="BRAND")
    ap.add_argument("keys", nargs="*")
    a = ap.parse_args()
    if a.brands:
        for b, _, n in sorted(site_4sale.brands(), key=lambda x: -x[2]):
            print(f"{b}  {n}")
    elif a.models:
        fb = pick_brand(a.models, f_brands())
        for s, label, n in sorted(f_models(fb) if fb else [], key=lambda x: -x[2]):
            print(f"{fb}/{s}  {label}  {n}")
    else:
        main(a.keys, a.out)
