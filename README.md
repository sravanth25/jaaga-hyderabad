# JaaGa Hyderabad — Static SEO Site Generator

A Probity-style programmatic SEO site for JaaGa's Hyderabad property services.
Each service becomes its **own static, self-canonical, schema-rich HTML page** — the
exact thing the live jaaga.ai service routes currently *don't* do (they all serve the
homepage shell and canonicalise to the homepage, so Google can't rank them).

## What's here

```
jaaga-hyderabad-seo/
├── build.py            # the generator (Python 3, no dependencies)
├── style.css           # JaaGa brand styles (navy #153568 / gold #f0a500 / green #16a34a, DM Sans)
├── data/
│   ├── site.json       # global config: brand, contact, areas, stats  ← EDIT THIS
│   └── services.json   # one object per service (content + FAQs + process)  ← ADD SERVICES HERE
└── dist/               # generated output — THIS is what you deploy
    ├── index.html                       # services hub
    ├── <service>-hyderabad.html         # 16 service pages
    ├── sitemap.xml
    ├── robots.txt
    └── assets/style.css
```

## Build it

```bash
python build.py
```

Regenerates everything into `dist/` in under a second.

## Deploy it (standalone static site)

The `dist/` folder is pure static HTML — deploy it anywhere:

- **Vercel:**  `cd dist && vercel deploy --prod`  (or point a Vercel project at the folder; framework preset = "Other")
- **Netlify:** drag `dist/` into the Netlify dashboard, or `netlify deploy --dir=dist --prod`
- **Own server:** copy `dist/` to the web root.

Recommended domain: a subdomain like `hyderabad.jaaga.ai` so it doesn't collide with the
existing SPA routes on `www.jaaga.ai`. Point the subdomain at the static deployment.

## ⚠️ Before you go live — edit these placeholders in `data/site.json`

| Field | Set it to |
|---|---|
| `baseUrl` | Your final domain (used in every canonical + the sitemap). **Must be correct or canonicals are wrong.** |
| `phone` / `whatsapp` / `waDefault` | Your real phone and WhatsApp number (currently `90000 00000`). |
| `address` | Your real Hyderabad office address. |
| `rating` | **Only keep this if you have genuine collected reviews.** Fake AggregateRating markup is penalised by Google — delete the `rating` block to omit it (the generator already makes it optional). |
| `stats` | Confirm the four hero stats are true for JaaGa. |
| `areas` | Localities are pre-filled for Greater Hyderabad — adjust as needed. |

## Add more services (this is the whole point of the generator)

To add a service, append one object to `data/services.json` and re-run `python build.py`.
Copy an existing entry as a template. Fields:

- **Required:** `slug`, `service`, `city`, `state`, `category`, `title`, `metaDescription`,
  `h1`, `tagline`, `shortDesc`, `keyTakeaways[]`, `faqs[{q,a}]`
- **Recommended:** `intro[]`, `whenNeeded{heading,paragraphs[]}`, `process{heading,steps[{name,desc}]}`,
  `documents[]`, `challenges[{title,desc}]`, `whyMatters`, `whatWeNeed[]`, `whatYouGet[]`,
  `references[{label,url}]`, `keywords`, `waMessage`, `price` (optional)

`process.steps` auto-generates **HowTo** schema; `faqs` auto-generate **FAQPage** schema.

### Services currently built (16)
All 15 from the Probity links you shared, plus your core catalogue:
Encumbrance Certificate · Title Verification · Prohibited Land (22A) · Court Case Check ·
CERSAI Mortgage Report · HYDRAA & FTL · RERA Verification · Find Ancestor Property ·
Mutation Creation · Property Registration · Document Translation · VLT Creation ·
Property Alert Service · Property Valuation · Property Tax Receipt · Electricity Name Change

### Suggested next services to add (from your jaaga.ai/services catalogue)
Pattadhar Passbook · Adangal/Pahani (1B) · PTIN Registration · Rectification Deed ·
Mortgage Deed · Physical Verification · Digital Land Survey · Loan/LAP assistance ·
Property Repatriation (NRI) · Buy/Rent/Sell · Water bill name change ·
Transferable Development Rights (TDR).
And for scale: duplicate the set for **Karnataka/Bengaluru** (Bhoomi RTC, Kaveri EC, BBMP khata)
— that's the service × city matrix that outranges a single-city competitor.

## What each page already ships (per Probity's formula)

- Unique, self-referencing `<link rel="canonical">`
- Unique keyworded `<title>` + meta description + OpenGraph + Twitter cards
- ~850–1,050 words of structured content (can be deepened toward Probity's ~2,000)
- JSON-LD: LocalBusiness, Service, BreadcrumbList, **FAQPage**, **HowTo**, WebPage + Speakable
- "Areas We Serve" localisation block with named Hyderabad localities
- Dense internal linking (all services in the footer + related-services grid) — hub & spoke
- Pre-filled WhatsApp CTAs per service
- `sitemap.xml` + `robots.txt`

## Verify before shipping

Run the same check that JaaGa's live site fails:

```bash
cd dist && python -c "import glob,re; [print(f, re.search(r'canonical href=\"(.*?)\"',open(f).read()).group(1)) for f in glob.glob('*.html')]"
```

Every page must print **its own URL** as the canonical (not the homepage).
