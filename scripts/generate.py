#!/usr/bin/env python3
"""
Morgenbrief-generator
Henter nyheter fra RSS-feeder, lar Claude lage en strukturert brief,
og genererer HTML-filer for GitHub Pages.
"""

import anthropic
import feedparser
import json
import os
import re
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

# ---------------------------------------------------------------------------
# Konfigurasjon
# ---------------------------------------------------------------------------

OSLO_TZ = ZoneInfo("Europe/Oslo")

FEEDS = [
    ("NRK Siste",                "https://www.nrk.no/nyheter/siste.rss"),
    ("NRK Vestfold og Telemark", "https://www.nrk.no/vestfoldogtelemark/siste.rss"),
    ("E24 Økonomi",              "https://e24.no/rss.xml"),
    ("Nettavisen",               "https://www.nettavisen.no/rss.xml"),
    ("Digi.no",                  "https://www.digi.no/rss.xml"),
    ("Teknisk Ukeblad",          "https://www.tu.no/rss"),
]

ROOT = Path(__file__).parent.parent   # repo-root
ARCHIVE_DIR = ROOT / "archive"
ARCHIVE_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# RSS-henting
# ---------------------------------------------------------------------------

def fetch_articles(hours: int = 48) -> list[dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    articles = []

    for source, url in FEEDS:
        try:
            feed = feedparser.parse(url, request_headers={"User-Agent": "MorgenbriefBot/1.0"})
            for entry in feed.entries[:25]:
                pub = None
                for attr in ("published_parsed", "updated_parsed"):
                    val = getattr(entry, attr, None)
                    if val:
                        pub = datetime(*val[:6], tzinfo=timezone.utc)
                        break

                if not pub or pub < cutoff:
                    continue

                title   = entry.get("title", "").strip()
                summary = entry.get("summary", entry.get("description", "")).strip()
                # Strip HTML tags from summary
                summary = re.sub(r"<[^>]+>", " ", summary)
                summary = re.sub(r"\s+", " ", summary)[:600]
                link    = entry.get("link", "")

                if title:
                    articles.append({
                        "source":    source,
                        "title":     title,
                        "summary":   summary,
                        "link":      link,
                        "published": pub.isoformat(),
                    })
        except Exception as exc:
            print(f"  ⚠️  Feil ved henting av {url}: {exc}")

    print(f"  📡  Hentet {len(articles)} artikler fra {len(FEEDS)} feeder")
    return articles


# ---------------------------------------------------------------------------
# Claude-kall
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """Du er en nyhetsredaktør som lager en daglig norsk morgenbrief.
Skriv på norsk bokmål. Vær faktabasert, nøytral og konsis – maks 40 ord per punkt.
Returner KUN gyldig JSON, ingen annen tekst."""

USER_TEMPLATE = """Dato: {date_str}

Disse artiklene er hentet fra RSS-feeder de siste 48 timene:

{articles_json}

Kategoriser og prioriter dem i disse seksjonene. Hopp over seksjoner uten ferske nyheter.
Seksjoner:
  1. "🏦 Bank, finans og næringsliv"
  2. "🤖 Kunstig intelligens og teknologi"
  3. "🏔️ Telemark og Skien"
  4. "🏛️ Norsk politikk og samfunn"
  5. "⚡ Energi og strøm"

Returner dette JSON-formatet – ingen markdown, ingen forklaring, bare JSON:
{{
  "sections": [
    {{
      "emoji": "🏦",
      "title": "Bank, finans og næringsliv",
      "items": [
        {{
          "headline": "Kort, beskrivende overskrift",
          "body": "1-2 setninger, maks 40 ord.",
          "source_name": "Kildenavn",
          "source_url": "https://..."
        }}
      ]
    }}
  ],
  "watchlist": [
    {{
      "headline": "Sak å følge",
      "reason": "Hvorfor dette kan utvikle seg (1 setning)."
    }}
  ]
}}"""


def generate_brief(articles: list[dict], date_str: str) -> dict:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    articles_json = json.dumps(articles, ensure_ascii=False, indent=2)
    user_msg = USER_TEMPLATE.format(date_str=date_str, articles_json=articles_json)

    print("  🤖  Kaller Claude for å lage morgenbrief …")
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
    )

    text = response.content[0].text.strip()
    # Fjern eventuelle markdown-blokker
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    return json.loads(text)


# ---------------------------------------------------------------------------
# HTML-rendering
# ---------------------------------------------------------------------------

CSS = """
:root {
  --navy: #1a2e4a;
  --blue: #1a5276;
  --light-blue: #a8c4d8;
  --bg: #f5f5f0;
  --card-bg: #ffffff;
  --text: #1a1a1a;
  --muted: #666;
  --border: #e8e8e4;
  --accent: #e8f4f8;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: Georgia, "Times New Roman", serif;
  background: var(--bg);
  color: var(--text);
  line-height: 1.65;
}
a { color: var(--blue); }
.wrapper { max-width: 700px; margin: 0 auto; }

/* Header */
.site-header {
  background: var(--navy);
  padding: 28px 40px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
}
.site-header h1 { color: #fff; font-size: 22px; }
.site-header p  { color: var(--light-blue); font-size: 13px; font-family: Arial, sans-serif; }
.site-header nav a {
  color: var(--light-blue);
  font-size: 13px;
  font-family: Arial, sans-serif;
  text-decoration: none;
  margin-left: 16px;
  border-bottom: 1px solid transparent;
}
.site-header nav a:hover { border-bottom-color: var(--light-blue); }

/* Content */
.content { padding: 32px 40px; }

/* Sections */
.section { margin-bottom: 32px; border-bottom: 1px solid var(--border); padding-bottom: 28px; }
.section:last-of-type { border-bottom: none; }
.section-title {
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 1.5px;
  color: var(--blue);
  margin-bottom: 16px;
  font-family: Arial, sans-serif;
}
.news-item { margin-bottom: 16px; }
.news-item strong { display: block; font-size: 16px; margin-bottom: 4px; }
.news-item p { font-size: 15px; color: #3a3a3a; }
.news-item .source { font-size: 12px; color: var(--muted); font-family: Arial, sans-serif; margin-top: 3px; }
.news-item .source a { color: var(--blue); }

/* Watchlist */
.watchlist {
  background: var(--accent);
  border-left: 4px solid var(--blue);
  padding: 20px 24px;
  border-radius: 0 4px 4px 0;
}
.watchlist h3 {
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 1px;
  color: var(--blue);
  font-family: Arial, sans-serif;
  margin-bottom: 12px;
}
.watchlist ul { padding-left: 18px; }
.watchlist li { font-size: 14px; margin-bottom: 8px; }
.watchlist li strong { font-size: 14px; }

/* Archive list */
.archive-list { list-style: none; }
.archive-list li {
  border-bottom: 1px solid var(--border);
  padding: 12px 0;
  font-family: Arial, sans-serif;
}
.archive-list li a { font-size: 15px; font-weight: 600; }
.archive-list li span { font-size: 13px; color: var(--muted); margin-left: 8px; }

/* Date badge */
.date-badge {
  display: inline-block;
  background: var(--navy);
  color: #fff;
  font-family: Arial, sans-serif;
  font-size: 12px;
  padding: 3px 10px;
  border-radius: 12px;
  margin-bottom: 20px;
}

/* Footer */
.site-footer {
  background: var(--navy);
  padding: 18px 40px;
  text-align: center;
  font-family: Arial, sans-serif;
  font-size: 12px;
  color: #7f8c8d;
}

@media (max-width: 600px) {
  .site-header, .content { padding: 20px; }
}
"""


def _nav(current: str = "brief") -> str:
    archive_active = ' style="border-bottom-color:var(--light-blue)"' if current == "archive" else ""
    brief_active   = ' style="border-bottom-color:var(--light-blue)"' if current == "brief"   else ""
    return (
        f'<nav>'
        f'<a href="/webside/"{brief_active}>Siste brief</a>'
        f'<a href="/webside/archive/"{archive_active}>Arkiv</a>'
        f'</nav>'
    )


def render_brief_html(brief: dict, date_str: str, date_obj: datetime) -> str:
    weekdays = ["mandag","tirsdag","onsdag","torsdag","fredag","lørdag","søndag"]
    weekday = weekdays[date_obj.weekday()]
    human_date = date_obj.strftime(f"{weekday} %-d. %B %Y")

    sections_html = ""
    for sec in brief.get("sections", []):
        items_html = ""
        for item in sec.get("items", []):
            src = ""
            if item.get("source_url"):
                src = f'<span class="source">Kilde: <a href="{item["source_url"]}" target="_blank" rel="noopener">{item.get("source_name","")}</a></span>'
            elif item.get("source_name"):
                src = f'<span class="source">Kilde: {item["source_name"]}</span>'
            items_html += f"""
        <div class="news-item">
          <strong>{item["headline"]}</strong>
          <p>{item["body"]}</p>
          {src}
        </div>"""

        sections_html += f"""
      <div class="section">
        <div class="section-title">{sec["emoji"]} {sec["title"]}</div>
        {items_html}
      </div>"""

    watchlist_html = ""
    wl = brief.get("watchlist", [])
    if wl:
        wl_items = "".join(
            f'<li><strong>{w["headline"]}</strong> – {w["reason"]}</li>'
            for w in wl
        )
        watchlist_html = f"""
      <div class="watchlist">
        <h3>💡 Verdt å følge med på</h3>
        <ul>{wl_items}</ul>
      </div>"""

    return f"""<!DOCTYPE html>
<html lang="no">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Morgenbrief – {human_date}</title>
<style>{CSS}</style>
</head>
<body>
<div class="wrapper">
  <header class="site-header">
    <div><h1>☕ Morgenbrief</h1><p>Nyheter fra de siste 48 timene</p></div>
    {_nav("brief")}
  </header>
  <div class="content">
    <div class="date-badge">📅 {human_date}</div>
    {sections_html}
    {watchlist_html}
  </div>
  <footer class="site-footer">
    Automatisk generert av Claude · {human_date} · Kilder: NRK, E24, Nettavisen, Digi.no m.fl.
  </footer>
</div>
</body>
</html>"""


def render_archive_html(entries: list[dict]) -> str:
    items_html = ""
    for e in sorted(entries, key=lambda x: x["date"], reverse=True):
        items_html += (
            f'<li><a href="/webside/archive/{e["file"]}">{e["label"]}</a>'
            f'<span>{e["date"]}</span></li>'
        )

    return f"""<!DOCTYPE html>
<html lang="no">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Morgenbrief – Arkiv</title>
<style>{CSS}</style>
</head>
<body>
<div class="wrapper">
  <header class="site-header">
    <div><h1>☕ Morgenbrief</h1><p>Arkiv – alle utgaver</p></div>
    {_nav("archive")}
  </header>
  <div class="content">
    <div class="section-title" style="margin-bottom:20px">📚 Alle utgaver</div>
    <ul class="archive-list">
      {items_html}
    </ul>
  </div>
  <footer class="site-footer">Automatisk generert av Claude</footer>
</div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Hjelpefunksjoner for arkiv-metadata
# ---------------------------------------------------------------------------

WEEKDAYS_NO = ["mandag","tirsdag","onsdag","torsdag","fredag","lørdag","søndag"]
MONTHS_NO   = ["","januar","februar","mars","april","mai","juni",
               "juli","august","september","oktober","november","desember"]

def date_label(d: datetime) -> str:
    return f"{WEEKDAYS_NO[d.weekday()].capitalize()} {d.day}. {MONTHS_NO[d.month]} {d.year}"


def load_archive_index() -> list[dict]:
    idx_path = ARCHIVE_DIR / "entries.json"
    if idx_path.exists():
        return json.loads(idx_path.read_text(encoding="utf-8"))
    return []


def save_archive_index(entries: list[dict]) -> None:
    idx_path = ARCHIVE_DIR / "entries.json"
    idx_path.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Hovedflyt
# ---------------------------------------------------------------------------

def main() -> None:
    now = datetime.now(OSLO_TZ)
    date_str = now.strftime("%Y-%m-%d")
    archive_file = f"{date_str}.html"
    archive_path = ARCHIVE_DIR / archive_file

    print(f"🗞️  Genererer morgenbrief for {date_str}")

    # 1. Hent artikler
    articles = fetch_articles(hours=48)
    if not articles:
        print("  ⚠️  Ingen artikler funnet – avbryter.")
        return

    # 2. Generer brief via Claude
    brief = generate_brief(articles, date_str)

    # 3. Render HTML
    brief_html = render_brief_html(brief, date_str, now)

    # 4. Lagre dagsarkiv
    archive_path.write_text(brief_html, encoding="utf-8")
    print(f"  ✅  Lagret arkiv: {archive_path}")

    # 5. Oppdater index.html (siste brief)
    (ROOT / "index.html").write_text(brief_html, encoding="utf-8")
    print(f"  ✅  Oppdaterte index.html")

    # 6. Oppdater arkivliste
    entries = load_archive_index()
    # Erstatt evt. eksisterende oppføring for dagens dato
    entries = [e for e in entries if e["date"] != date_str]
    entries.append({
        "date":  date_str,
        "file":  archive_file,
        "label": date_label(now),
    })
    save_archive_index(entries)

    # 7. Generer arkivside
    archive_index_html = render_archive_html(entries)
    (ARCHIVE_DIR / "index.html").write_text(archive_index_html, encoding="utf-8")
    print(f"  ✅  Oppdaterte archive/index.html ({len(entries)} utgaver)")

    print("🎉  Ferdig!")


if __name__ == "__main__":
    main()
