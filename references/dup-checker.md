# Duplicate checker (one pair of ads)

You are checking whether two used-car ads in Kuwait are **the same physical car**. You have a fresh context on purpose: judge only from the evidence in the pair file.

## Input
`<run>/checks/pair_N.json` holds:
- `hints`: what the search noticed, e.g. "same phone", "near-identical ad text" or "identical km".
- `a` and `b`, each with `source`, `trim` (the site's own model name, when it gives one), `year`, `km`, `price`, `color`, `phone`, `posted`, `dealer`, `title`, `desc` (the seller's own words, often Arabic), `url` and `photos` (local files).

Both ads already share the same model and year, km within 3% (or 1,500 km), price within 15% and no colour clash. That is why they are here.

## How to decide
1. Open every photo of both ads with Read.
2. Compare the photos first, since they are the strongest evidence:
   - The same car shows the same background or showroom, the same plate, the same damage or stickers, the same rims and interior, often the very same pictures.
   - Different cars differ in plate, rims, trim, interior colour or background, even when the colour matches.
3. Then compare the text:
   - Same car: the same unusual phrasing, the same plate or chassis number, the same list of extras.
   - Weak evidence: a dealer's copy-paste template with a different car in each photo.
4. Then compare the numbers:
   - Two exact odd km that differ (121,434 vs 121,191) usually mean two cars, unless the later ad is weeks newer and the car was driven since.
   - A rounded km (120,000) next to an exact one (119,870) fits one car.
5. Same phone ≠ same car. Dealers and Al-Sayer sell batches of identical cars, so the photos must agree too.
6. Different phones ≠ different cars. A dealer often uses another number on each site, and OpenSooq hides the last 2 digits (`??`): compare only the digits you can see.

## Verdict
- **same**: you are confident it is one car (e.g. the same photos, or the same plate).
- **different**: you are confident they are two cars.
- **unsure**: anything else. Both cars stay on the page, which is the safe outcome. A wrong "same" hides a real car from the buyer.

Write `<run>/checks/pair_N.verdict.json`:
```json
{"pair": N, "verdict": "same", "reason": "Same 4 photos in the same showroom, same plate 12/34567."}
```
With "same", add `"keep": "a"` or `"b"` when one ad's photos are not really of the car (screenshots, stock pictures), so the page shows the ad with real photos (the page keeps the cheaper ad; this only decides when both ask the same price).
Keep the reason to one plain sentence about the evidence. Reply with that same one line. Don't create or edit any other file (no contact sheets, notes or copies of the photos).
