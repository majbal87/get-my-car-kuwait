# Get My Car 🇰🇼

**A Kuwait car search skill for Claude. Looking for a used car in Kuwait? Just ask.**

No more scrolling through car sites for hours, one by one. Tell Claude what you want, the way you'd tell a friend. It searches Kuwait's main car sites for you, all at once, and gives you one clear page with every car that fits.

It works for **any car**: a cheap first car for your son, a 7-seat family SUV, a pickup for work, a new Chinese electric car, or a Porsche. It knows **151 car makers and 898 models** sold in Kuwait: Japanese, Korean, Chinese, European, American and more.

## Just talk to it

You can ask in your own words, for example:

- *"Find me a reliable Japanese SUV, budget 10,000 KD."*
- *"My son needs his first car, something cheap and easy to fix, under 2,000 KD."*
- *"A 7-seat Chinese SUV, 2023 or newer."*
- *"Any Land Cruiser under 15,000 KD with less than 150,000 km."*

Claude then asks you a few quick questions, all at once:

> **Claude:** Which years and how many km? How recent should the ads be: last week, last month or all? And what should I call your page?

That's all. Claude searches the sites and your page opens by itself.

## What Claude does for you

- **Searches every site at once:** 4Sale, OpenSooq, Motorgy, Al-Sayer Car World and Lexus certified pre-owned. It reads every ad, not just the first page.
- **Removes repeats.** The same car is often listed on two sites. Claude spots it and shows it only once, at its lowest price.
- **Picks the best ones** and tells you why in one simple line: the age, the km, the service history, the price.
- **Tells you what to check** before you buy each model, and how reliable it's known to be.
- **Points out ads that look wrong,** like a price or km that doesn't make sense, so you can ask the seller.
- **Tells you when a site couldn't be checked.** If a site is down, the page says so at the top, so missing cars never look like "none for sale".

## Your page

- Every matching car with its photos, year, km and price
- **Top picks first**
- The seller's phone number (when the site shows it) and a button to open the original ad
- Filter by price and year, and save the cars you like with a heart
- **English and Arabic**, light and dark mode

## Keeps itself up to date

Car sites change all the time, so this skill looks after itself:

- **Every week** it offers to refresh its list of car makers and models from the sites, so new cars (like new Chinese brands) show up. It takes about 2 minutes, and you just say yes.
- **Every month** it checks whether Kuwait's car sites have changed, before it searches.
- **Every search is fresh:** you always see the ads that are for sale today.

## How to install

You need **Claude Code**, in the Claude desktop app or in the terminal.

**The easy way:** open Claude Code and say:

> *Install the skill from https://github.com/majbal87/get-my-car-kuwait into ~/.claude/skills/get-my-car*

Claude sets it up for you. Then just ask for a car.

**If you prefer to do it yourself,** run this once:

```bash
git clone https://github.com/majbal87/get-my-car-kuwait.git ~/.claude/skills/get-my-car
```

**Cowork (Claude desktop app):** not tested there yet.

## Good to know

- Works best on a Mac with Google Chrome, where your page opens by itself.
- Your pages are saved on your own computer. Nothing is shared unless you send it.
- Reliability notes are a summary of each model's reputation, not official test results.
- It only finds and shows cars. It doesn't buy, contact sellers or arrange financing.
