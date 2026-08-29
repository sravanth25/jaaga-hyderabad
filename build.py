#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JaaGa Hyderabad SEO site generator
-----------------------------------
Reads  data/site.json  +  data/services.json
Writes dist/<slug>.html  (one static, self-canonical, schema-rich page per service)
       dist/all-services.html   (services hub)
       dist/sitemap.xml
       dist/robots.txt
       dist/assets/style.css

Run:  python build.py
Deploy: push the dist/ folder to Vercel / Netlify / any static host.
"""
import json, os, html, datetime, re, shutil

ROOT = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(ROOT, "dist")
DATA = os.path.join(ROOT, "data")

def load(name):
    with open(os.path.join(DATA, name), encoding="utf-8") as f:
        return json.load(f)

def esc(s):
    return html.escape(str(s), quote=True)

# ----------------------------------------------------------------------------
# JSON-LD schema graph (this is what wins FAQ rich results + AI-answer citations)
# ----------------------------------------------------------------------------
def build_schema(sv, site):
    base = site["baseUrl"].rstrip("/")
    url = f"{base}/{sv['slug']}.html"
    org_id = f"{base}/#org"

    graph = []

    # LocalBusiness / Organization
    graph.append({
        "@type": ["Organization", "LocalBusiness", "ProfessionalService"],
        "@id": org_id,
        "name": site["orgName"],
        "url": base + "/",
        "logo": site.get("logo", base + "/assets/logo.png"),
        "image": site.get("ogImage", base + "/assets/og.jpg"),
        "telephone": site["phone"],
        **({"email": site["email"]} if site.get("email") else {}),
        "priceRange": site.get("priceRange", "₹₹"),
        "address": {
            "@type": "PostalAddress",
            "streetAddress": site["address"]["street"],
            "addressLocality": site["address"]["locality"],
            "addressRegion": site["address"]["region"],
            "postalCode": site["address"]["postalCode"],
            "addressCountry": "IN",
        },
        "geo": {"@type": "GeoCoordinates", "latitude": site["geo"]["lat"], "longitude": site["geo"]["lng"]},
        "areaServed": {"@type": "City", "name": sv.get("city", "Hyderabad")},
        "contactPoint": [cp for cp in [
            {"@type": "ContactPoint", "telephone": site["phone"],
             "contactType": "customer service", "areaServed": "IN",
             **({"email": site["email"]} if site.get("email") else {}),
             "availableLanguage": ["en", "te", "hi"]},
            ({"@type": "ContactPoint", "telephone": site["altPhone"],
              "contactType": "customer service", "areaServed": "IN",
              "availableLanguage": ["en", "te", "hi"]} if site.get("altPhone") else None),
        ] if cp],
        "sameAs": site.get("sameAs", []),
    })
    # Only emit AggregateRating if real review data is configured (fake review markup is penalised)
    if site.get("rating"):
        graph[0]["aggregateRating"] = {
            "@type": "AggregateRating",
            "ratingValue": site["rating"]["value"],
            "reviewCount": site["rating"]["count"],
        }

    # Service
    graph.append({
        "@type": "Service",
        "@id": url + "#service",
        "serviceType": sv["service"],
        "name": f"{sv['service']} in {sv.get('city','Hyderabad')}",
        "description": sv["metaDescription"],
        "provider": {"@id": org_id},
        "areaServed": {"@type": "City", "name": sv.get("city", "Hyderabad")},
        "url": url,
        **({"offers": {"@type": "Offer", "priceCurrency": "INR",
                       "price": str(sv["price"]), "url": url}} if sv.get("price") else {}),
    })

    # BreadcrumbList
    graph.append({
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": base + "/"},
            {"@type": "ListItem", "position": 2, "name": "Services", "item": base + "/all-services.html"},
            {"@type": "ListItem", "position": 3, "name": sv["service"], "item": url},
        ],
    })

    # FAQPage
    if sv.get("faqs"):
        graph.append({
            "@type": "FAQPage",
            "@id": url + "#faq",
            "mainEntity": [
                {"@type": "Question", "name": f["q"],
                 "acceptedAnswer": {"@type": "Answer", "text": f["a"]}}
                for f in sv["faqs"]
            ],
        })

    # HowTo (for process-driven services)
    if sv.get("process", {}).get("steps"):
        steps = sv["process"]["steps"]
        howto = {
            "@type": "HowTo",
            "@id": url + "#howto",
            "name": f"How to get {sv['service']} in {sv.get('city','Hyderabad')}",
            "step": [
                {"@type": "HowToStep", "position": i + 1, "name": s["name"], "text": s["desc"]}
                for i, s in enumerate(steps)
            ],
        }
        if sv.get("documents"):
            howto["supply"] = [{"@type": "HowToSupply", "name": d} for d in sv["documents"]]
        if sv.get("price"):
            howto["estimatedCost"] = {"@type": "MonetaryAmount", "currency": "INR", "value": str(sv["price"])}
        graph.append(howto)

    # WebPage + Speakable
    graph.append({
        "@type": "WebPage",
        "@id": url + "#webpage",
        "url": url,
        "name": sv["title"],
        "description": sv["metaDescription"],
        "inLanguage": "en-IN",
        "isPartOf": {"@id": base + "/#website"},
        "datePublished": sv.get("datePublished", site.get("datePublished")),
        "dateModified": sv.get("dateModified", site.get("dateModified")),
        "speakable": {"@type": "SpeakableSpecification",
                      "cssSelector": [".jg-h1", ".jg-takeaways"]},
        "about": {"@id": url + "#service"},
    })

    return {"@context": "https://schema.org", "@graph": graph}

# ----------------------------------------------------------------------------
# HTML fragments
# ----------------------------------------------------------------------------
def wa_link(site, msg):
    from urllib.parse import quote
    return f"https://wa.me/{site['whatsapp']}?text={quote(msg)}"

def telhref(num):
    return "tel:" + re.sub(r"[^\d+]", "", num)

def analytics_html(site):
    """Vercel Web Analytics for static/HTML sites (enable Web Analytics in the Vercel dashboard)."""
    if not site.get("vercelAnalytics"):
        return ""
    return ('<script>window.va=window.va||function(){(window.vaq=window.vaq||[]).push(arguments);};</script>'
            '<script defer src="/_vercel/insights/script.js"></script>')

def fmt_date(iso):
    """'2026-08-24' -> '24 August 2026' for display."""
    try:
        d = datetime.datetime.strptime(iso, "%Y-%m-%d")
        return f"{d.day} {d.strftime('%B %Y')}"
    except Exception:
        return iso

# Short labels for the nav bar only (full category names stay on pages/hub)
NAV_SHORT = {
    "Verification & Due Diligence": "Verification",
    "Legal & Documentation": "Legal & Docs",
    "Alerts & Monitoring": "Alerts",
    "Valuation & Specialty": "Valuation",
    "Documentation & Utility": "Documentation",
    "Land Records (Telangana)": "Land Records",
    "Loans & NRI Services": "Loans & NRI",
}

def grouped(services):
    """Group services by category, preserving first-seen order."""
    order, buckets = [], {}
    for s in services:
        c = s.get("category", "Services")
        if c not in buckets:
            buckets[c] = []
            order.append(c)
        buckets[c].append(s)
    return [(c, buckets[c]) for c in order]

def nav_html(site, services, active=None):
    groups = ""
    for cat, items in grouped(services):
        li = "".join(
            f'<li><a href="{esc(s["slug"])}.html"'
            f'{" aria-current=\"page\"" if s["slug"]==active else ""}>{esc(s["service"])}</a></li>'
            for s in items
        )
        groups += (
            f'<div class="jg-nav-group">'
            f'<button type="button" class="jg-nav-trigger" aria-expanded="false">'
            f'{esc(NAV_SHORT.get(cat, cat))}<span class="jg-caret" aria-hidden="true">▾</span></button>'
            f'<div class="jg-nav-menu"><ul>{li}</ul></div></div>'
        )
    return f"""<header class="jg-topbar">
  <div class="jg-wrap jg-topbar-row">
    <a class="jg-brand" href="all-services.html">
      <span class="jg-brand-mark">JaaGa</span>
      <span class="jg-brand-sub">Property Services · Hyderabad</span>
    </a>
    <a class="jg-cta-btn jg-topbar-cta" href="{esc(wa_link(site, site['waDefault']))}" rel="nofollow">WhatsApp Us</a>
    <button type="button" class="jg-nav-toggle" aria-label="Toggle menu" aria-expanded="false">
      <span></span><span></span><span></span></button>
  </div>
  <div class="jg-navbar">
    <nav class="jg-nav" aria-label="Primary">
      {groups}
      <a class="jg-nav-all" href="all-services.html">All Services</a>
    </nav>
  </div>
</header>"""

NAV_JS = """<script>
(function(){
  var bar=document.querySelector('.jg-topbar'),
      tog=document.querySelector('.jg-nav-toggle'),
      mq=window.matchMedia('(max-width:960px)');
  if(tog){tog.addEventListener('click',function(){
    var o=bar.classList.toggle('nav-open');tog.setAttribute('aria-expanded',o);});}
  document.querySelectorAll('.jg-nav-trigger').forEach(function(btn){
    btn.addEventListener('click',function(){
      if(!mq.matches)return;
      var g=btn.closest('.jg-nav-group'),o=g.classList.toggle('open');
      btn.setAttribute('aria-expanded',o);});
  });
  document.addEventListener('click',function(e){
    if(!mq.matches&&!e.target.closest('.jg-nav-group')){
      document.querySelectorAll('.jg-nav-group.open').forEach(function(g){g.classList.remove('open');});}
  });
})();
</script>"""

def takeaways_html(sv):
    if not sv.get("keyTakeaways"): return ""
    items = "".join(f"<li>{esc(t)}</li>" for t in sv["keyTakeaways"])
    return f"""<aside class="jg-takeaways" aria-label="Key takeaways">
  <h2>Key Takeaways</h2><ul>{items}</ul></aside>"""

def process_html(sv):
    p = sv.get("process")
    if not p or not p.get("steps"): return ""
    steps = "".join(
        f'<li class="jg-step"><span class="jg-step-n">{i+1}</span>'
        f'<div><h3>{esc(s["name"])}</h3><p>{esc(s["desc"])}</p></div></li>'
        for i, s in enumerate(p["steps"])
    )
    return f"""<section class="jg-sec"><h2>{esc(p.get('heading','The Process'))}</h2>
  <ol class="jg-steps">{steps}</ol></section>"""

def docs_html(sv):
    if not sv.get("documents"): return ""
    items = "".join(f"<li>{esc(d)}</li>" for d in sv["documents"])
    return f"""<section class="jg-sec"><h2>Documents Required</h2>
  <ul class="jg-checklist">{items}</ul></section>"""

def challenges_html(sv):
    if not sv.get("challenges"): return ""
    cards = "".join(
        f'<div class="jg-chal"><h3>{esc(c["title"])}</h3><p>{esc(c["desc"])}</p></div>'
        for c in sv["challenges"]
    )
    return f"""<section class="jg-sec"><h2>Common Problems We Solve</h2>
  <div class="jg-chal-grid">{cards}</div></section>"""

def faq_html(sv):
    if not sv.get("faqs"): return ""
    items = "".join(
        f'<details class="jg-faq"><summary>{esc(f["q"])}</summary><p>{esc(f["a"])}</p></details>'
        for f in sv["faqs"]
    )
    return f"""<section class="jg-sec" id="faq"><h2>Frequently Asked Questions</h2>{items}</section>"""

def areas_html(sv, site):
    areas = ", ".join(site["areas"])
    return f"""<section class="jg-sec"><h2>Areas We Serve for {esc(sv['service'])}</h2>
  <p>JaaGa handles {esc(sv['service'].lower())} across {esc(site['areasCount'])} locations in Greater Hyderabad,
  covering the {esc(site['districts'])} district revenue divisions. Key areas include {esc(areas)}.
  Serving property owners, buyers and NRIs across Telangana — remotely, end to end.</p></section>"""

def refs_html(sv):
    if not sv.get("references"): return ""
    items = "".join(f'<li><a href="{esc(r["url"])}" target="_blank" rel="noopener nofollow">{esc(r["label"])}</a></li>'
                    for r in sv["references"])
    return f"""<section class="jg-sec jg-refs"><h2>Official References</h2><ul>{items}</ul>
  <p class="jg-note">JaaGa is a private facilitation service and is not affiliated with any government department.</p></section>"""

def whatyouget_html(sv):
    need = sv.get("whatWeNeed", [])
    get = sv.get("whatYouGet", [])
    if not (need or get): return ""
    n = "".join(f"<li>{esc(x)}</li>" for x in need)
    g = "".join(f"<li>{esc(x)}</li>" for x in get)
    return f"""<section class="jg-sec jg-exchange"><h2>What We Need &amp; What You Get</h2>
  <div class="jg-exchange-grid">
    <div><h3>What We Need From You</h3><ul class="jg-checklist">{n}</ul></div>
    <div><h3>What You Get</h3><ul class="jg-checklist jg-check-green">{g}</ul></div>
  </div></section>"""

def related_html(sv, services):
    others = [s for s in services if s["slug"] != sv["slug"]][:8]
    cards = "".join(
        f'<a class="jg-rel" href="{esc(s["slug"])}.html"><strong>{esc(s["service"])}</strong>'
        f'<span>{esc(s.get("shortDesc",""))}</span></a>'
        for s in others
    )
    return f"""<section class="jg-sec"><h2>Related Services</h2>
  <div class="jg-rel-grid">{cards}</div></section>"""

SOCIAL_ICONS = {
    "instagram": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="2.5" y="2.5" width="19" height="19" rx="5.5"/><circle cx="12" cy="12" r="4"/><circle cx="17.4" cy="6.6" r="1.1" fill="currentColor" stroke="none"/></svg>',
    "facebook": '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M22 12a10 10 0 10-11.6 9.9v-7H7.9V12h2.5V9.8c0-2.5 1.5-3.9 3.7-3.9 1.1 0 2.2.2 2.2.2v2.5h-1.2c-1.2 0-1.6.8-1.6 1.6V12h2.7l-.4 2.9h-2.3v7A10 10 0 0022 12z"/></svg>',
    "linkedin": '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M4.98 3.5a2.5 2.5 0 100 5 2.5 2.5 0 000-5zM3 9h4v12H3zM9 9h3.8v1.7h.1c.5-1 1.8-2 3.7-2 4 0 4.7 2.6 4.7 6V21h-4v-5.3c0-1.3 0-2.9-1.8-2.9s-2.1 1.4-2.1 2.8V21H9z"/></svg>',
    "x": '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M18.9 2H22l-7.3 8.3L23 22h-6.6l-5.2-6.8L5.3 22H2l7.8-8.9L1.5 2h6.8l4.7 6.2L18.9 2zm-1.2 18h1.7L7.4 3.8H5.6L17.7 20z"/></svg>',
    "youtube": '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M23 12s0-3.2-.4-4.7a2.5 2.5 0 00-1.8-1.8C19.2 5 12 5 12 5s-7.2 0-8.8.5A2.5 2.5 0 001.4 7.3C1 8.8 1 12 1 12s0 3.2.4 4.7a2.5 2.5 0 001.8 1.8C4.8 19 12 19 12 19s7.2 0 8.8-.5a2.5 2.5 0 001.8-1.8C23 15.2 23 12 23 12zM9.8 15.3V8.7l5.7 3.3-5.7 3.3z"/></svg>',
}

def social_html(site):
    items = site.get("socials", [])
    if not items:
        return ""
    links = "".join(
        f'<a href="{esc(s["url"])}" target="_blank" rel="noopener me" aria-label="{esc(s["label"])}" title="{esc(s["label"])}">'
        f'{SOCIAL_ICONS.get(s.get("icon",""), "")}</a>'
        for s in items
    )
    return f'<div class="jg-social">{links}</div>'

def footer_html(site, services):
    links = "".join(f'<li><a href="{esc(s["slug"])}.html">{esc(s["service"])}</a></li>' for s in services)
    year = datetime.date.today().year
    return f"""<footer class="jg-footer">
  <div class="jg-wrap">
    <div class="jg-footer-top">
      <div class="jg-footer-brand">
        <span class="jg-brand-mark">JaaGa</span>
        <p>{esc(site['tagline'])}</p>
        <p class="jg-footer-contact">
          <a href="{esc(wa_link(site, site['waDefault']))}" rel="nofollow">WhatsApp {esc(site['phone'])}</a><br>
          <a href="{telhref(site['phone'])}">{esc(site['phone'])}</a>{f' · <a href="{telhref(site["altPhone"])}">{esc(site["altPhone"])}</a>' if site.get('altPhone') else ''}<br>
          {f'<a href="mailto:{esc(site["email"])}">{esc(site["email"])}</a>' if site.get('email') else ''}
        </p>
        {social_html(site)}
      </div>
      <nav class="jg-footer-links" aria-label="All services">
        <h4>All Hyderabad Services</h4><ul>{links}</ul>
      </nav>
    </div>
    <div class="jg-footer-bottom">
      <span>© {year} {esc(site['orgName'])}. All rights reserved.</span>
      <span>Serving {esc(site['areasCount'])} localities across Greater Hyderabad &amp; Telangana.</span>
    </div>
  </div>
</footer>"""

# ----------------------------------------------------------------------------
# Full page
# ----------------------------------------------------------------------------
def render_page(sv, site, services):
    base = site["baseUrl"].rstrip("/")
    url = f"{base}/{sv['slug']}.html"
    schema = json.dumps(build_schema(sv, site), ensure_ascii=False, indent=None)
    intro_paras = "".join(f"<p>{esc(p)}</p>" for p in sv.get("intro", []))
    when = ""
    if sv.get("whenNeeded"):
        wn = sv["whenNeeded"]
        paras = "".join(f"<p>{esc(p)}</p>" for p in wn["paragraphs"])
        when = f'<section class="jg-sec"><h2>{esc(wn["heading"])}</h2>{paras}</section>'
    why = ""
    if sv.get("whyMatters"):
        why = f'<section class="jg-sec"><h2>Why {esc(sv["service"])} Matters</h2><p>{esc(sv["whyMatters"])}</p></section>'

    stats = "".join(
        f'<div class="jg-stat"><span class="jg-stat-n">{esc(s["n"])}</span><span class="jg-stat-l">{esc(s["l"])}</span></div>'
        for s in site["stats"]
    )
    wa = wa_link(site, sv.get("waMessage", f"Hi JaaGa, I need {sv['service']} in Hyderabad"))

    return f"""<!doctype html>
<html lang="en-IN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(sv['title'])}</title>
<meta name="description" content="{esc(sv['metaDescription'])}">
{f'<meta name="keywords" content="{esc(sv["keywords"])}">' if sv.get("keywords") else ""}
<link rel="canonical" href="{esc(url)}">
<meta name="robots" content="index,follow,max-snippet:-1,max-image-preview:large,max-video-preview:-1">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{esc(site['orgName'])}">
<meta property="og:locale" content="en_IN">
<meta property="og:title" content="{esc(sv['title'])}">
<meta property="og:description" content="{esc(sv['metaDescription'])}">
<meta property="og:url" content="{esc(url)}">
<meta property="og:image" content="{esc(site.get('ogImage', base + '/assets/og.jpg'))}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{esc(sv['title'])}">
<meta name="twitter:description" content="{esc(sv['metaDescription'])}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=DM+Sans:opsz,wght@9..40,400;9..40,500;9..40,600;9..40,700;9..40,800;9..40,900&display=swap">
<link rel="icon" href="assets/favicon.ico" sizes="any">
<link rel="apple-touch-icon" href="assets/logo.png">
<link rel="stylesheet" href="assets/style.css">
<script type="application/ld+json">{schema}</script>
</head>
<body>
{nav_html(site, services, active=sv['slug'])}
<main>
  <section class="jg-hero">
    <div class="jg-wrap">
      <nav class="jg-crumb" aria-label="Breadcrumb"><a href="all-services.html">Services</a> <span>/</span> {esc(sv['service'])}</nav>
      <h1 class="jg-h1">{esc(sv['h1'])}</h1>
      <p class="jg-lede">{esc(sv.get('tagline',''))}</p>
      {f'<p class="jg-dateline">Last updated: {esc(fmt_date(sv.get("dateModified", site.get("dateModified"))))}</p>' if (sv.get("dateModified") or site.get("dateModified")) else ''}
      <div class="jg-hero-cta">
        <a class="jg-cta-btn jg-cta-lg" href="{esc(wa)}" rel="nofollow">Get Started on WhatsApp</a>
        <a class="jg-cta-ghost" href="{telhref(site['phone'])}">Call {esc(site['phone'])}</a>
      </div>
      <div class="jg-stats">{stats}</div>
    </div>
  </section>

  <div class="jg-wrap jg-body">
    <article class="jg-article">
      {takeaways_html(sv)}
      {intro_paras}
      {when}
      {process_html(sv)}
      {docs_html(sv)}
      {challenges_html(sv)}
      {why}
      {areas_html(sv, site)}
      {faq_html(sv)}
      {whatyouget_html(sv)}
      {refs_html(sv)}
    </article>
  </div>

  <section class="jg-band">
    <div class="jg-wrap jg-band-inner">
      <div><h2>Get your {esc(sv['service'])} done — without the SRO/MRO queues.</h2>
      <p>Message us your survey number or document number. We handle the rest, end to end.</p></div>
      <a class="jg-cta-btn jg-cta-lg" href="{esc(wa)}" rel="nofollow">Start on WhatsApp</a>
    </div>
  </section>

  <div class="jg-wrap jg-body">{related_html(sv, services)}</div>
</main>
{footer_html(site, services)}
{NAV_JS}
{analytics_html(site)}
</body>
</html>"""

# ----------------------------------------------------------------------------
# Services hub (all-services.html)
# ----------------------------------------------------------------------------
def render_hub(site, services):
    base = site["baseUrl"].rstrip("/")
    url = base + "/all-services.html"
    # group by category
    cats = {}
    for s in services:
        cats.setdefault(s.get("category", "Services"), []).append(s)
    cat_html = ""
    for cat, items in cats.items():
        cards = "".join(
            f'<a class="jg-svc-card" href="{esc(s["slug"])}.html">'
            f'<strong>{esc(s["service"])}</strong><span>{esc(s.get("shortDesc",""))}</span>'
            f'<span class="jg-svc-arrow">→</span></a>'
            for s in items
        )
        cat_html += f'<section class="jg-cat"><h2>{esc(cat)}</h2><div class="jg-svc-grid">{cards}</div></section>'

    itemlist = {
        "@context": "https://schema.org", "@type": "ItemList",
        "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": s["service"],
             "url": f"{base}/{s['slug']}.html"} for i, s in enumerate(services)
        ],
    }
    stats = "".join(
        f'<div class="jg-stat"><span class="jg-stat-n">{esc(s["n"])}</span><span class="jg-stat-l">{esc(s["l"])}</span></div>'
        for s in site["stats"]
    )
    return f"""<!doctype html>
<html lang="en-IN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(site['hubTitle'])}</title>
<meta name="description" content="{esc(site['hubDescription'])}">
<link rel="canonical" href="{esc(url)}">
<meta name="robots" content="index,follow,max-snippet:-1,max-image-preview:large">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{esc(site['orgName'])}">
<meta property="og:title" content="{esc(site['hubTitle'])}">
<meta property="og:description" content="{esc(site['hubDescription'])}">
<meta property="og:url" content="{esc(url)}">
<meta property="og:image" content="{esc(site.get('ogImage', base + '/assets/og.jpg'))}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=DM+Sans:opsz,wght@9..40,400;9..40,500;9..40,600;9..40,700;9..40,800;9..40,900&display=swap">
<link rel="icon" href="assets/favicon.ico" sizes="any">
<link rel="apple-touch-icon" href="assets/logo.png">
<link rel="stylesheet" href="assets/style.css">
<script type="application/ld+json">{json.dumps(itemlist, ensure_ascii=False)}</script>
</head>
<body>
{nav_html(site, services)}
<main>
  <section class="jg-hero jg-hero-hub">
    <div class="jg-wrap">
      <h1 class="jg-h1">{esc(site['hubH1'])}</h1>
      <p class="jg-lede">{esc(site['hubLede'])}</p>
      <div class="jg-hero-cta">
        <a class="jg-cta-btn jg-cta-lg" href="{esc(wa_link(site, site['waDefault']))}" rel="nofollow">Talk to Us on WhatsApp</a>
      </div>
      <div class="jg-stats">{stats}</div>
    </div>
  </section>
  <div class="jg-wrap jg-body">{cat_html}</div>
</main>
{footer_html(site, services)}
{NAV_JS}
{analytics_html(site)}
</body>
</html>"""

# ----------------------------------------------------------------------------
# sitemap + robots
# ----------------------------------------------------------------------------
def render_sitemap(site, services):
    base = site["baseUrl"].rstrip("/")
    today = datetime.date.today().isoformat()
    urls = [base + "/all-services.html"] + [f"{base}/{s['slug']}.html" for s in services]
    body = "".join(
        f"  <url><loc>{esc(u)}</loc><lastmod>{today}</lastmod>"
        f"<changefreq>weekly</changefreq><priority>{'1.0' if i==0 else '0.9'}</priority></url>\n"
        for i, u in enumerate(urls)
    )
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{body}</urlset>\n'

SEARCH_BOTS = ["Googlebot", "Googlebot-Image", "Googlebot-News", "Googlebot-Video",
               "Bingbot", "msnbot", "Slurp", "DuckDuckBot", "YandexBot", "Baiduspider", "Applebot"]
AI_BOTS = ["Google-Extended", "GPTBot", "ChatGPT-User", "OAI-SearchBot",
           "ClaudeBot", "anthropic-ai", "Claude-Web", "PerplexityBot", "PerplexityBot",
           "Applebot-Extended", "cohere-ai", "Amazonbot", "Bytespider", "FacebookExternalHit"]

def render_robots(site):
    base = site["baseUrl"].rstrip("/")
    def block(bots):
        return "\n\n".join(f"User-agent: {b}\nAllow: /" for b in dict.fromkeys(bots))
    return f"""# {site['orgName']} - robots.txt
# {base}

# Default: allow all crawlers
User-agent: *
Allow: /

# Search engines
{block(SEARCH_BOTS)}

# AI crawlers - explicitly allowed so {site['orgName']} can be cited in AI answers
{block(AI_BOTS)}

# Sitemap
Sitemap: {base}/sitemap.xml

# AI model context
# {base}/llms.txt
"""

def render_llms(site, services):
    base = site["baseUrl"].rstrip("/")
    L = [f"# {site['orgName']}", "",
         f"> {site['hubDescription']}", "",
         f"{site['orgName']} helps property owners, buyers and NRIs in Hyderabad and across "
         f"Telangana handle land records, verification, legal documentation and utility "
         f"transfers remotely. Every service is delivered end to end over WhatsApp, without "
         f"the customer visiting the Sub-Registrar (SRO) or MRO offices in person.", "",
         "## Services", ""]
    for cat, items in grouped(services):
        L.append(f"### {cat}")
        for s in items:
            L.append(f"- [{s['service']} in {s.get('city','Hyderabad')}]"
                     f"({base}/{s['slug']}.html): {s.get('shortDesc','')}")
        L.append("")
    L += ["## Areas served",
          f"{site['areasCount']} localities across Greater Hyderabad and Telangana, including "
          f"{', '.join(site['areas'])}. Districts covered: {site['districts']}.", "",
          "## Contact"]
    L.append(f"- WhatsApp / phone: {site['phone']}")
    if site.get("altPhone"): L.append(f"- Alternate phone: {site['altPhone']}")
    if site.get("email"): L.append(f"- Email: {site['email']}")
    L += [f"- All services: {base}/all-services.html", "",
          "## Notes",
          f"{site['orgName']} is a private facilitation service and is not affiliated with any "
          f"government department. Official records are sourced from the relevant Telangana "
          f"government portals (Registration & Stamps, Dharani, GHMC, TG-RERA, CERSAI).", ""]
    return "\n".join(L)

# ----------------------------------------------------------------------------
def main():
    site = load("site.json")
    services = load("services.json")
    os.makedirs(os.path.join(DIST, "assets"), exist_ok=True)

    # CSS
    with open(os.path.join(ROOT, "style.css"), encoding="utf-8") as f:
        css = f.read()
    with open(os.path.join(DIST, "assets", "style.css"), "w", encoding="utf-8") as f:
        f.write(css)

    # copy image/brand assets (og.jpg, logo.png, favicon.ico, ...) into dist/assets/
    src_assets = os.path.join(ROOT, "assets")
    if os.path.isdir(src_assets):
        for fn in os.listdir(src_assets):
            if fn.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".svg", ".ico", ".gif")):
                shutil.copy(os.path.join(src_assets, fn), os.path.join(DIST, "assets", fn))

    # pages
    for sv in services:
        with open(os.path.join(DIST, f"{sv['slug']}.html"), "w", encoding="utf-8") as f:
            f.write(render_page(sv, site, services))

    with open(os.path.join(DIST, "all-services.html"), "w", encoding="utf-8") as f:
        f.write(render_hub(site, services))
    with open(os.path.join(DIST, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write(render_sitemap(site, services))
    with open(os.path.join(DIST, "robots.txt"), "w", encoding="utf-8") as f:
        f.write(render_robots(site))
    with open(os.path.join(DIST, "llms.txt"), "w", encoding="utf-8") as f:
        f.write(render_llms(site, services))
    # Google Search Console HTML-file verification
    gv = site.get("googleVerification")
    if gv:
        with open(os.path.join(DIST, f"{gv}.html"), "w", encoding="utf-8") as f:
            f.write(f"google-site-verification: {gv}.html\n")

    print(f"[OK] Generated {len(services)} service pages + hub + sitemap + robots into dist/")
    for sv in services:
        print(f"     /{sv['slug']}.html   —  {sv['title']}")

if __name__ == "__main__":
    main()
