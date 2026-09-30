---
name: get-my-car
description: "**Get My Car (Kuwait Car Search)**: Asks the buyer what they're looking for in their own words (budget, years, km, how recent the ads, page name), picks the models from a saved, dated list of what the sites sell, searches every page of 4Sale, OpenSooq, Motorgy, and Al-Sayer's Car World and Lexus certified with one script, merges the same car listed on several sites (look-alikes judged by a fresh checker agent per pair), and builds a fast HTML page saved on this computer and opened in Chrome (every photo loading straight from the car sites, light and dark mode, English / العربية, top picks, reliability notes, the seller's phone and an Open-ad button), ending with how a vague request was read. Works for any car, from a cheap sedan to a Porsche or G-Class. A claude.ai page only when asked (slower, 3 photos per car). TRIGGERS: 'find me a used car', 'car search', 'get my car', 'kuwait car search', 'my friend wants a … car, budget … KD', 'search all car sites for …', 'used SUV / sedan / 7-seater / Porsche under … KD in Kuwait'. Not for buying, messaging sellers or financing."
---

# Get My Car 🇰🇼 (Kuwait Car Search)

From "find me a used X" to a page on this computer: ask, search all sites with one command, review, build. `SK="$HOME/.claude/skills/get-my-car"` (quote it in every command). The car list lives inside the skill in `"$SK/data/catalogue.json"`; the log of pages made is `"$SK/data/pages.md"`.

## 0. Sources first
Open `"$SK/references/sources.md"`. If "Last checked" is more than 30 days old, refresh it (rules are in the file) before searching.

## 1. Ask the buyer
- If the request says little ("find me a car"), ask in plain words: "What are you looking for? What's the car for, your budget, and anything you already have in mind?"
- Then ask what is still missing in **one** `AskUserQuestion` call. It holds at most 4 questions, each with an "Other" for exact values, so ask only these, in this order, and drop what is already known:
  1. **Budget**, if not given.
  2. **Years and mileage**, as one question ("2018 or newer, under 150,000 km?"), if not given.
  3. **"How recent should the ads be?"** (always): Last week / Last 2 weeks / Last month (Recommended) / All. Fewer days search faster; "All" also finds older ads still for sale. No answer or "don't mind": last month.
  4. **"What should this page be called?"** (always).
  5. **"Update the car list?"** (only when the list is a week old or more).
  When all five are needed, fold the ad age into question 2 ("2018+, under 150,000 km, ads from the last month?").
  Don't ask what they already said, and don't offer fixed brand lists: the buyer's words decide ("reliable Japanese", "Chinese SUV", "an LX under 80,000 km"). Anything else (seats, body type) is judged from their words, not asked.
- Details of the last two:
  - **"Update the car list?"** Run `python3 "$SK/scripts/catalogue.py" --date` first. The sites' model lists change slowly, so a list less than 7 days old is used as it is, without asking (mention its date in your one-line reading). A week or older: ask, with the date ("The car list was last updated 2026-09-19. Update it first? It takes about 2 minutes."). Yes: step 2a. No: use the saved one. If it says `none`, there is no list yet: say so and do step 2a without asking.
  - **"What should this page be called?"** It may be for the user's son or a friend, so offer a person's name ("Ahmad's Car Search") or a title of its own ("Family SUVs"), with "Other" for the exact words.
- **Vague answers** ("around 5,000", "not too old", "something reliable"): don't ask again. Use your own judgment and note what you decided; the reply and the page explain it at the end (step 5 `reading`, step 6).
- State your reading in one line and continue.

## 2a. Update the car list (when the user says yes to the weekly question, or when there is none)
- `python3 "$SK/scripts/catalogue.py" --scan` (about 2 minutes, one progress line per maker) reads every maker on 4Sale and OpenSooq and each maker's models, in the sites' own names and with ad counts, and links each model's pages on 4Sale, OpenSooq and Motorgy. A maker with no model pages on 4Sale (BYD) or only on OpenSooq (Denza) is saved as one entry, `byd/all`. Origin and body type already set are kept.
- It then lists the blanks: brands without an origin (Japanese, Korean, Chinese, European, American, Other) and models without a body type (SUV, Sedan, Pickup, Coupe, Hatchback, Van, Convertible, Wagon). Fill them from what you know in one file and run `python3 "$SK/scripts/catalogue.py" --set <file>` (`{"origin": {"byd": "Chinese"}, "body": {"byd/song-plus": "SUV"}}`).
- Nothing else goes in the list: reliability notes are written fresh for each search.

## 2. Choose the models
- The skill has no built-in car list; the saved list is only what the sites sell. `python3 "$SK/scripts/catalogue.py" --show [--origin Japanese] [--body SUV] [--brand toyota]` prints it grouped by origin, with each model's key, body type and ad count, so you see what is actually sold in Kuwait.
- Pick the models from the buyer's words: usually 4–10, or just the ones they named. Map their words to the list's names ("LC 300" is `toyota/land-cruiser`, "S 500" is `mercedes/s-class`). When unsure what fits (e.g. "reliable Chinese SUV"), do a quick web search. A model not in the list can still be searched: give it a `brand/model` key of your own and its pages are looked up live.
- Write `$S/models.json`, one entry per model, keyed as in the car list (`mercedes/g-class`): `name`, `brand`, `body`, `seats`, `engine`, `rel` (1–5, reputation summary; a short text such as "Good (CX-9 turbo: check the head gasket)" also works, with `rel_ar`), `note`, `check` (what to inspect), `note_ar`, `check_ar`, and `match` when the model goes by several names (G-Class: `["G-Class","G Class","G 63","G63","G 500","G500"]`). Add `skip` for other models whose names start the same or share the site's page (Pajero: `["Pajero Sport"]`; the car list's lumped `mazda/cx` for a CX-9 search: `match` `["CX-9"]`, `skip` `["CX-3","CX-30","CX-5","CX-50","CX-60","CX-90"]`). `match` and `skip` work in Arabic too, and most 4Sale titles are Arabic, so add the names sellers write there (the car list shows 4Sale's Arabic name next to each model; Patrol: skip `["Super Safari", "Safari", "سوبر سفاري", "سفاري", "بكب", "وانيت"]`). Arabic names match whole words (so "كروز", Cruze, never catches "كروزر", Cruiser), so give the spellings sellers use. `seats` is a short number (5, 7); a car whose ad says otherwise gets its own (step 3). Write the notes for the cars this budget and these years actually buy (at 35,000 KD an LX is an LX 600, not an old LX 570).
- The search takes each model's pages from the car list (or looks them up live), saves them in `sites` and prints them. Check them: fix a wrong or missing one by hand in `sites`, then search again. An empty list means that site has no such model. When one buyer model spans several list entries (G-Class: `mercedes/g-class` and `mercedes/g63`), put all their pages in one `sites`.
- Motorgy names some models by engine instead of by model (Mercedes `s500`, BMW `730li`), so the list can't link them by name and that site would be skipped quietly. For each brand you search, `catalogue.py --show --brand <brand>` ends with "Motorgy pages not linked to a model"; add the ones that belong to your model to its `sites.motorgy` (the model's `match` names then keep only the right cars). A model gets its `sites` on the first search; to add them before searching, `python3 "$SK/scripts/resolve.py" --out $S <model keys>` writes them into `models.json` (the other fields are kept), or write the `sites` block by hand.
- A whole-maker entry (`byd/all`) reads all that maker's ads: sellers mislabel the type (a Denza B5 as "Sedan"), so set its other sites' pages by hand to the fitting models (OpenSooq lists them) and, in review, remove the ads of another type than asked (a pickup in an SUV search). 4Sale files Denza under BYD.
- Don't edit the skill's files during a search.

## 3. Search (one command: about a minute for one model, a few minutes for many)
```bash
S=<scratchpad>/<page-slug>
python3 "$SK/scripts/search.py" --out $S --models toyota/prado lexus/gx … \
  --min-price 2000 --max-price 6000 --min-year 2016 [--max-year …] [--max-km 150000] --days 30
```
`--days` is the buyer's ad age from step 1: 7, 14, 30 (the default) or 0 for all. It applies to 4Sale and OpenSooq, which list ads newest first (a seller's refreshed ad counts as new). Motorgy, Car World and Lexus are shops listing their current stock, so they are always read whole.
Set `--min-price` to a realistic floor for the budget: placeholder prices (1 KD, 12 KD) below it only slow the search.
**Budget.** A stated budget is a hard limit: `--max-price` is that budget. Only a vague one ("around 5,000 KD") gets a margin you choose (e.g. up to 5,500), and you say so in `reading` (step 5). The page's price slider always reaches the dearest car on the page, so no searched car starts hidden.
What it does:
- **Fetch.** One script per site (`site_4sale.py`, `site_opensooq.py`, `site_motorgy.py`, `site_alsayer.py`) returns cars in one shape. Every list page a site reports for the model is read (no limit, in parallel); a model with over 100 pages prints a ⚠ line but is still read whole. `site_alsayer.py` reads Al Sayer Car World (for-sale cars only, not Reserved) and Lexus certified, matched by make and model name.
- **Right model.** An ad naming a `skip` model is dropped on every site. Motorgy titles, and OpenSooq's own car names when the model has a `match` list, must name the model. 4Sale titles are free text (often Arabic, or without the model), so there only `skip` applies. Each model's line shows how many cars were read in the price range, which tells "none in range" from "none kept".
- **Per car.** `trim` is the site's own name for the car ("730Li", "CX-9 Signature"), shown on the card when the site gives one. `seats` is read from the ad ("7 راكب", "3 صفوف") when it says, else the page shows the model's. A 1xxxxxxx phone or "معرض" / "showroom" in the ad marks a dealer.
- **Clean.** Drops ads outside the year and km range and "we buy cars" ads. New and nearly new cars (0 km, "أصفار") are kept.
- **Merge certain duplicates.** `dedup.py` merges on its own only when it is certain: the same chassis number (Al-Sayer's sites), or identical odd km (e.g. 187,340) with the same model and year and a price within 10%. Every other look-alike pair on the page (same model and year, km within 3% or 1,500 km, price within 15%, no colour clash) is written to `checks/pair_N.json` for step 4, even with the same phone, because dealers sell look-alike cars.
- **Keep every car.** Drops cars without photos. Every other car that passes the filters goes on the page, however many (the buyer wants to see all of them; only duplicates are merged). It keeps every photo's web address: the page loads the photos from the sites, so nothing is downloaded for the page. Only the cars in look-alike pairs get their first 6 photos downloaded (to `$S/img/`), because the checker agents look at photo files. (`--download` downloads 3 photos per car instead: the 1st, 4th and 7th, or the 1st, 4th and last, or the 1st and last. That is only for a Claude.ai page, see the end of step 5.)
- **Write.** Outputs `cars.json` (with the seller's phone when the site shows it), `dedup.json` (the certain merges and why), `checks/pair_N.json` and `stats.json` (`pairs_to_check`, `failed_pages`).
- **Pages that didn't load.** A site can block or time out. Each page is tried 3 times (a page that is cut off, or loads but carries no ads data, counts as failed too: a model with no cars still has its data); one that still fails is listed at the end under "⚠ … did not load" and in `failed_pages`. Its cars are missing, which is not the same as none for sale. That is usually a site outage or block: wait a minute and run the same search again once. If pages still fail, carry on, and tell the buyer in the reply which site and model couldn't be checked; the page also warns at the top.
- **Wrong page name.** "⚠ OpenSooq toyota/fj-cruiser-xx: no such page" (`wrong_pages`) means the site has no page by that name, so rerunning won't help: fix that slug in the model's `sites` (step 2), or delete its `sites` so the search looks the pages up again, and search again.
- **Progress.** One line per site and model as each finishes ("4Sale toyota/fj-cruiser: 26 ads, 12 s"), and every 100 ad pages on a long 4Sale read. The search keeps the Mac awake while it runs.

## 4. Review (judgment, not script)
Read `cars.json` (year, km, price, title, desc, source) and edit it:
- **Site mistakes are reported, not fixed.** Sites misfile ads (a Macan on the Cayenne page) and sellers make typos. Don't drop or correct those ads. Give the car a `flag` (one plain sentence, with `flag_ar`) saying what looks off, e.g. another model in the photo, a monthly or deposit price, a very low km on an older car or text that contradicts the km or price, and list them in the reply. Trust the asking price otherwise.
- **Seller text.** Never edit `title` or `desc`, and never hide a phone number in them.
- **Seats and trim.** When an ad or its trim shows another seat count than the model's (a 7-seat RX 350L), set that car's `seats`.
- **Chips.** Remove any feature chip the ad text contradicts.
- **Duplicates (fresh checker agents, all at once).** For each `$S/checks/pair_N.json`, launch one `Agent` (general-purpose, `model: "sonnet"`), all in a single message so they run in parallel. Prompt: "Read "$SK/references/dup-checker.md" and follow it for $S/checks/pair_N.json." (with both paths written out in full) Keep it to about 12 agents at most (the tool refuses more than 20 at once): with more pairs, spread the pair files evenly over them, several per agent. When all have replied, run `python3 "$SK/scripts/checks.py" --out $S`. It merges the "same" pairs (the page counts them), keeps both for "different" and "unsure", and logs every verdict in `dedup.json`. If the Agent tool isn't available, check the pairs yourself by the same rules. Don't overrule a verdict unless it is plainly wrong. Merge a duplicate you spot by hand the same way (`also` entry with `"checked": true`).
- **Picks.** Choose up to 6–9 top picks across models (fewer when there are only a few cars). Each `pick` is one sentence on why, taken from the ad's facts, with its Arabic twin in `pick_ar` (a `flag` gets `flag_ar` too). Rank reliability first, then age, mileage and price, weighted by what the buyer said matters, and give each pick its place as `rank` (1 = best): the page shows the picks in that order, so the buyer sees your first choice first.

## 5. Build the page
- Write `$S/meta.json` fresh for this search (`h1` + `h1_accent` are the page name from step 1 split in two, e.g. "Ahmad's" + "Car Search", and `h1_ar` + `h1_accent_ar` the same name in Arabic word order, e.g. "بحث سيارة" + "أحمد"; `budget` is a number; end `lede` with the ad age used, e.g. "Ads from the last month." or "All ads."), e.g.
  ```json
  {"eyebrow": "Used cars · Kuwait", "h1": "Family", "h1_accent": "SUVs", "lede": "5+ seat SUVs, 2015 or newer, up to 6,000 KD. Ads from the last month.",
   "budget": 6000, "pickline": "Picked for reliability first, then age, mileage and price.", "checked": "2026-09-26",
   "sources": "4Sale, OpenSooq, Motorgy and Al-Sayer"}
  ```
- **`reading` (only when you had to judge a vague request, step 1).** A short list for the page's closed "How this search was read" box at the bottom, with `reading_ar`: budget, years and km used (and any margin), the models chosen and why, the ones left out and why, and the models with no cars found (and why, e.g. "2017+ Prados start above 7,000 KD"). Leave it out when the buyer's answers were exact: the box is then hidden.
- **Arabic.** The page has an English / العربية switch. The page's own words are built in; your words need Arabic twins:
  - In `meta.json`: `eyebrow_ar`, `h1_ar`, `h1_accent_ar`, `lede_ar`, `pickline_ar`, `sources_ar`, `reading_ar`. Add `"lang": "ar"` to open the page in Arabic (when the buyer writes in Arabic); then write the reply (step 6) in Arabic too.
  - For each model on the page, `note_ar` and `check_ar` in `$S/models.json`.
  - Write plain Kuwaiti-friendly Arabic (قير، ممشى، وكالة، شرط الفحص). Keep model names and numbers as they are. Missing Arabic falls back to English.
- `python3 "$SK/scripts/build.py" --out $S --title "<page name from step 1>"` writes `$S/index.html`, a complete page that opens in any browser: the same design as v3's Claude.ai page (cards, top picks, light and dark mode, English / العربية) with each photo loading from its car site. It also takes one screenshot (`_screenshot.png`, dark). Look at it once, fix what's broken, and don't loop.
- **Save and open it.** Copy it to `"$SK/data/pages/<page-slug>.html"` (make the folder if missing) and open it for the buyer: `open -a "Google Chrome" "<that file>"`. To share it, the buyer sends that file (it needs the internet for the photos and fonts).
- **Delete the downloaded photos.** Run `rm -rf "$S/img"`: they were only for the checker agents, and the user wants no car photos kept on their computer. Delete only that folder of this search.
- **Log it.** Add one row to `"$SK/data/pages.md"` (create it with this header if missing): `| Date | Page | For | Search | Link |`. For: who it's for (a name, or "—"). Search: one short line (e.g. "reliable Chinese SUV, ≤ 8,000 KD, 2020+"). Link: the saved file's path. When the page is remade later, update its row instead of adding one.
- **Claude.ai page (only when the user asks for a shareable Claude.ai link).** It is slower: an Artifact page can't show photos from other sites, so photos must be downloaded and shipped with the page: 3 per car. Search with `--download`, build with `--claude`: each car is one file (`ph/<id>.json`, its photos), up to 500 cars (more: make the fast page, or narrow the search). Publish `$S/index.html` with `root: $S`, `files` = `$S/files.json` exactly as written, `icon: "car"` and a one-sentence `description`. If build.py also wrote `files_2.json`, `files_3.json`…, publish each in turn to the same `url` (one publish takes at most 255 files and 64 MB). Then `rm -rf "$S/img" "$S/ph"` and log the link.

## 6. Reply
- Lead with the saved page's path (it is already open in Chrome).
- A short picks table: car, km, price, why.
- One line: ads checked on how many sites and how many duplicates were merged.
- If any site or model couldn't be checked (`failed_pages`, or `wrong_pages` you couldn't fix), say so plainly: "OpenSooq didn't respond for Prado, so its Prados are missing." Never let a failed site look like no cars.
- A few bullets on what was flagged (site mistakes left for the buyer to judge).
- Name every model that found no cars, and why if known ("no Prado under 7,000 KD at 2017+"). Never let a model vanish silently.
- Say the listings are a snapshot of today.
- The page follows the viewer's light or dark setting and has a ☾ / ☀ switch next to English / العربية.
- Last, only when you had to judge a vague request: "How I read your request", 2–4 short lines (budget and any margin, years and km, models chosen or left out and why). The same is in the page's closed box at the bottom.

## Limits
- Every site is read in full (all list pages; Motorgy through its `?pn=` pages). The car list follows 4Sale's catalogue; a model only another site sells is looked up live.
- Reliability ratings are our summary of model reputation, labelled as such. Never present them as data.
- Every car has an Open-ad button. The phone shows as a call button when the site gives it: 4Sale in full; Motorgy's is Motorgy's sales line (labelled); OpenSooq hides the last 2 digits (its reveal needs a login), so the page says the full number is on the ad; Al-Sayer gives none.
