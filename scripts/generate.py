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
  --bg: #f8f7f4;
  --surface: #ffffff;
  --surface2: #f0eeea;
  --text: #1a1a1a;
  --text-muted: #6b7280;
  --accent: #2563eb;
  --accent-light: #eff6ff;
  --border: #e5e3de;
  --header-bg: #0f172a;
  --header-text: #f1f5f9;
  --header-muted: #94a3b8;
  --badge-bg: #1e293b;
  --footer-bg: #0f172a;
  --footer-text: #64748b;
  --watchlist-bg: #eff6ff;
  --watchlist-border: #2563eb;
  --toggle-bg: #334155;
  --toggle-icon: "🌙";
}
[data-theme="dark"] {
  --bg: #0f172a;
  --surface: #1e293b;
  --surface2: #273548;
  --text: #f1f5f9;
  --text-muted: #94a3b8;
  --accent: #60a5fa;
  --accent-light: #1e3a5f;
  --border: #334155;
  --header-bg: #020617;
  --header-text: #f1f5f9;
  --header-muted: #64748b;
  --badge-bg: #334155;
  --footer-bg: #020617;
  --footer-text: #475569;
  --watchlist-bg: #1e3a5f;
  --watchlist-border: #60a5fa;
  --toggle-bg: #60a5fa;
  --toggle-icon: "☀️";
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "Inter", "Segoe UI", sans-serif;
  background: var(--bg);
  color: var(--text);
  line-height: 1.65;
  transition: background 0.2s, color 0.2s;
}
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
.wrapper { max-width: 720px; margin: 0 auto; }

/* Header */
.site-header {
  background: var(--header-bg);
  padding: 24px 40px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
}
.header-left h1 {
  color: var(--header-text);
  font-size: 20px;
  font-weight: 700;
  letter-spacing: -0.3px;
}
.header-left p { color: var(--header-muted); font-size: 13px; margin-top: 2px; }
.header-right { display: flex; align-items: center; gap: 20px; }
.site-header nav a {
  color: var(--header-muted);
  font-size: 13px;
  text-decoration: none;
  padding-bottom: 2px;
  border-bottom: 2px solid transparent;
  transition: color 0.15s, border-color 0.15s;
}
.site-header nav a:hover,
.site-header nav a.active { color: var(--header-text); border-bottom-color: var(--accent); }

/* Theme toggle */
.theme-toggle {
  background: var(--toggle-bg);
  border: none;
  border-radius: 20px;
  width: 44px;
  height: 24px;
  cursor: pointer;
  position: relative;
  transition: background 0.2s;
  flex-shrink: 0;
}
.theme-toggle::after {
  content: "";
  position: absolute;
  top: 3px;
  left: 3px;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: #fff;
  transition: transform 0.2s;
}
[data-theme="dark"] .theme-toggle::after { transform: translateX(20px); }
.theme-toggle-wrap { display: flex; align-items: center; gap: 8px; }
.theme-toggle-wrap span { font-size: 14px; line-height: 1; }

/* Content */
.content { padding: 36px 40px; }

/* Date badge */
.date-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: var(--badge-bg);
  color: var(--header-text);
  font-size: 12px;
  font-weight: 500;
  padding: 4px 12px;
  border-radius: 20px;
  margin-bottom: 28px;
  letter-spacing: 0.3px;
}

/* Sections */
.section { margin-bottom: 36px; }
.section-divider {
  border: none;
  border-top: 1px solid var(--border);
  margin-bottom: 28px;
}
.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 1.8px;
  color: var(--text-muted);
  margin-bottom: 16px;
}

/* News items */
.news-item {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 16px 18px;
  margin-bottom: 10px;
  transition: box-shadow 0.15s;
}
.news-item:hover { box-shadow: 0 2px 12px rgba(0,0,0,0.07); }
[data-theme="dark"] .news-item:hover { box-shadow: 0 2px 12px rgba(0,0,0,0.3); }
.news-item strong {
  display: block;
  font-size: 15px;
  font-weight: 600;
  color: var(--text);
  margin-bottom: 5px;
  line-height: 1.4;
}
.news-item p { font-size: 14px; color: var(--text-muted); line-height: 1.6; }
.news-item .source {
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 8px;
  display: flex;
  align-items: center;
  gap: 4px;
}
.news-item .source::before { content: "↗"; font-size: 10px; }
.news-item .source a { color: var(--accent); font-weight: 500; }

/* Watchlist */
.watchlist {
  background: var(--watchlist-bg);
  border: 1px solid var(--border);
  border-left: 4px solid var(--watchlist-border);
  padding: 20px 24px;
  border-radius: 0 10px 10px 0;
  margin-top: 8px;
}
.watchlist h3 {
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 1.8px;
  color: var(--accent);
  margin-bottom: 14px;
}
.watchlist ul { padding-left: 0; list-style: none; }
.watchlist li {
  font-size: 14px;
  color: var(--text);
  margin-bottom: 10px;
  padding-left: 16px;
  position: relative;
  line-height: 1.5;
}
.watchlist li::before {
  content: "•";
  position: absolute;
  left: 0;
  color: var(--accent);
  font-weight: 700;
}
.watchlist li strong { font-weight: 600; }

/* Archive list */
.archive-list { list-style: none; }
.archive-list li {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  margin-bottom: 8px;
  transition: box-shadow 0.15s;
}
.archive-list li:hover { box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
.archive-list li a {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 18px;
  font-size: 15px;
  font-weight: 500;
  color: var(--text);
  text-decoration: none;
}
.archive-list li a:hover { color: var(--accent); }
.archive-list li a span { font-size: 13px; color: var(--text-muted); font-weight: 400; }

/* Footer */
.site-footer {
  background: var(--footer-bg);
  padding: 20px 40px;
  text-align: center;
  font-size: 12px;
  color: var(--footer-text);
  margin-top: 12px;
}

@media (max-width: 600px) {
  .site-header, .content { padding: 18px 20px; }
  .site-footer { padding: 18px 20px; }
}
"""

THEME_SCRIPT = """
<script>
(function(){
  var t = localStorage.getItem('theme') || 'light';
  document.documentElement.setAttribute('data-theme', t);
})();
</script>
<script>
function toggleTheme() {
  var current = document.documentElement.getAttribute('data-theme');
  var next = current === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  localStorage.setItem('theme', next);
}
</script>
"""


def _nav(current: str = "brief") -> str:
    archive_class = ' class="active"' if current == "archive" else ""
    brief_class   = ' class="active"' if current == "brief"   else ""
    return (
        f'<div class="header-right">'
        f'<nav>'
        f'<a href="/webside/"{brief_class}>Siste brief</a>'
        f'<a href="/webside/archive/"{archive_class}>Arkiv</a>'
        f'</nav>'
        f'<div class="theme-toggle-wrap">'
        f'<span>☀️</span>'
        f'<button class="theme-toggle" onclick="toggleTheme()" aria-label="Bytt tema"></button>'
        f'<span>🌙</span>'
        f'</div>'
        f'</div>'
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

        divider = '<hr class="section-divider">' if sections_html else ""
        sections_html += f"""
      {divider}
      <div class="section">
        <div class="section-title"><span>{sec["emoji"]}</span>{sec["title"]}</div>
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
{THEME_SCRIPT}
<style>{CSS}</style>
</head>
<body>
<div class="wrapper">
  <header class="site-header">
    <div class="header-left"><h1>☕ Morgenbrief</h1><p>Nyheter fra de siste 48 timene</p></div>
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
{THEME_SCRIPT}
<style>{CSS}</style>
</head>
<body>
<div class="wrapper">
  <header class="site-header">
    <div class="header-left"><h1>☕ Morgenbrief</h1><p>Arkiv – alle utgaver</p></div>
    {_nav("archive")}
  </header>
  <div class="content">
    <div class="date-badge">📚 Alle utgaver</div>
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
