"""Build subscribable .ics calendars (Google Calendar, Apple Calendar, Outlook) from the
Economic Calendar Data (Investing.com) Apify Actor.

    python -m econcal_ics.build --out public                 # live data (needs APIFY_TOKEN)
    python -m econcal_ics.build --out public --sample tests/sample-events.json   # offline demo
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from icalendar import Alarm, Calendar, Event as ICalEvent

from .client import ACTOR_URL, Event, flag, load_events
from .feeds import FEEDS, Feed

PRODID = "-//economic-calendar-ics//Investing.com via Apify//EN"


def event_uid(e: Event) -> str:
    base = f"{e.id}-{e.day.isoformat()}-{e.title}"
    return hashlib.sha1(base.encode()).hexdigest()[:20] + "@economic-calendar-ics"


def event_description(e: Event) -> str:
    lines = [f"{flag(e.country)} {e.country.title()} ({e.currency or '-'})"]
    if e.importance:
        lines.append(f"Impact: {e.importance.upper()} {e.stars}")
    if e.actual or e.forecast or e.previous:
        lines.append(f"Actual: {e.actual or '-'} | Forecast: {e.forecast or '-'} | Previous: {e.previous or '-'}")
        if e.surprise():
            lines.append(f"Result vs forecast: {e.surprise()}")
    lines.append("")
    lines.append(f"Data: Investing.com economic calendar via {ACTOR_URL}")
    return "\n".join(lines)


def build_calendar(feed: Feed, events: list[Event], generated: datetime) -> Calendar:
    cal = Calendar()
    cal.add("prodid", PRODID)
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")
    cal.add("method", "PUBLISH")
    cal.add("x-wr-calname", feed.name)
    cal.add("x-wr-caldesc", feed.description)
    cal.add("x-wr-timezone", "UTC")
    cal.add("refresh-interval;value=duration", "PT6H")
    cal.add("x-published-ttl", "PT6H")
    for e in events:
        if not feed.predicate(e):
            continue
        ve = ICalEvent()
        ve.add("uid", event_uid(e))
        ve.add("dtstamp", generated)
        prefix = f"{flag(e.country)} {e.currency + ' ' if e.currency else ''}"
        summary = f"{prefix}{e.title}"
        if e.actual:
            summary += f" — {e.actual}"
            if e.forecast:
                summary += f" (f {e.forecast})"
        ve.add("summary", summary)
        ve.add("description", event_description(e))
        ve.add("categories", [c for c in [e.importance or "holiday", e.country] if c])
        if e.all_day or e.when is None:
            ve.add("dtstart", e.day)
            ve.add("dtend", e.day + timedelta(days=1))
            ve.add("transp", "TRANSPARENT")
        else:
            ve.add("dtstart", e.when)
            ve.add("dtend", e.when + timedelta(minutes=15))
            if feed.alarm_minutes and e.importance == "high":
                alarm = Alarm()
                alarm.add("action", "DISPLAY")
                alarm.add("description", f"In {feed.alarm_minutes} min: {e.title}")
                alarm.add("trigger", timedelta(minutes=-feed.alarm_minutes))
                ve.add_component(alarm)
        cal.add_component(ve)
    return cal


def render_index(feeds_meta: list[dict], base_url: str, generated: datetime) -> str:
    cards = []
    for f in feeds_meta:
        ics_url = f"{base_url.rstrip('/')}/{f['slug']}.ics" if base_url else f"{f['slug']}.ics"
        webcal = ics_url.replace("https://", "webcal://").replace("http://", "webcal://")
        gcal = f"https://calendar.google.com/calendar/r?cid={html.escape(webcal)}"
        outlook = ("https://outlook.live.com/calendar/0/addfromweb?url=" + html.escape(ics_url)
                   + "&name=" + html.escape(f["name"]))
        nxt = "".join(
            f"<li><span class='t'>{html.escape(n['when'])}</span> {html.escape(n['title'])}</li>" for n in f["next"]
        ) or "<li class='muted'>No upcoming events in the current window</li>"
        cards.append(f"""
      <article class="card">
        <h2>{html.escape(f['name'])}</h2>
        <p class="desc">{html.escape(f['description'])}</p>
        <p class="count">{f['count']} events in feed</p>
        <ul class="next">{nxt}</ul>
        <div class="btns">
          <a class="btn g" href="{gcal}" target="_blank" rel="noopener">+ Google Calendar</a>
          <a class="btn a" href="{html.escape(webcal)}">+ Apple Calendar</a>
          <a class="btn o" href="{outlook}" target="_blank" rel="noopener">+ Outlook</a>
          <a class="btn d" href="{html.escape(ics_url)}" download>.ics</a>
        </div>
        <input class="url" readonly value="{html.escape(ics_url)}" onclick="this.select()">
      </article>""")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Economic Calendar for Google Calendar, Apple & Outlook — FOMC, CPI, NFP (free .ics feeds)</title>
<meta name="description" content="Subscribe to a free, auto-updating economic calendar in Google Calendar, Apple Calendar or Outlook: FOMC meetings, CPI release dates, Nonfarm Payrolls, central bank decisions and high-impact forex news.">
<style>
:root{{--bg:#0b1020;--card:#121a33;--ink:#e8ecff;--mut:#9aa6d1;--acc:#4f8cff;--line:#243056}}
*{{box-sizing:border-box}}body{{margin:0;font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;background:var(--bg);color:var(--ink)}}
header{{padding:40px 24px 8px;max-width:1150px;margin:auto}}h1{{font-size:30px;margin:0 0 8px}}header p{{color:var(--mut);margin:0}}
main{{max-width:1150px;margin:auto;padding:16px 24px 48px;display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:16px}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px}}h2{{font-size:17px;margin:0 0 6px}}
.desc{{color:var(--mut);margin:0 0 8px;font-size:13.5px}}.count{{font-size:12px;color:var(--acc);margin:0 0 8px;font-weight:600}}
.next{{list-style:none;padding:0;margin:0 0 12px;font-size:13px}}.next li{{padding:4px 0;border-top:1px dashed var(--line)}}.t{{color:var(--mut);font-variant-numeric:tabular-nums;margin-right:6px}}
.btns{{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:8px}}.btn{{text-decoration:none;color:#fff;padding:7px 10px;border-radius:8px;font-size:12.5px;font-weight:600}}
.g{{background:#1a73e8}}.a{{background:#3a3a3c}}.o{{background:#0f6cbd}}.d{{background:#2b365f}}
.url{{width:100%;background:#0b1020;color:var(--mut);border:1px solid var(--line);border-radius:8px;padding:6px 8px;font-size:12px}}
.muted{{color:var(--mut)}}footer{{max-width:1150px;margin:auto;padding:0 24px 40px;color:var(--mut);font-size:13px}}a{{color:var(--acc)}}
</style></head><body>
<header><h1>📅 Economic Calendar → Google Calendar, Apple & Outlook</h1>
<p>Free, auto-updating <b>.ics</b> feeds of FOMC meetings, CPI release dates, Nonfarm Payrolls, central bank decisions and every high-impact event. Times in your calendar's local time zone. Updated {generated.strftime('%Y-%m-%d %H:%M UTC')}.</p></header>
<main>{''.join(cards)}</main>
<footer>Data: Investing.com economic calendar, collected with the <a href="{ACTOR_URL}">Economic Calendar Data (Investing.com) Apify Actor</a>. Not investment advice.</footer>
</body></html>"""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="public", help="output folder (default: public)")
    ap.add_argument("--sample", help="use a local JSON export instead of calling the Actor")
    ap.add_argument("--days-back", type=int, default=7)
    ap.add_argument("--days-ahead", type=int, default=45)
    ap.add_argument("--base-url", default="", help="public URL of the folder, e.g. https://<user>.github.io/<repo>")
    args = ap.parse_args(argv)

    events = load_events(sample_file=args.sample, days_back=args.days_back, days_ahead=args.days_ahead)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    generated = datetime.now(timezone.utc).replace(microsecond=0)
    now = generated if not args.sample else min((e.when for e in events if e.when), default=generated) + timedelta(days=6)

    meta = []
    for feed in FEEDS:
        cal = build_calendar(feed, events, generated)
        (out / f"{feed.slug}.ics").write_bytes(cal.to_ical())
        matched = [e for e in events if feed.predicate(e)]
        upcoming = [e for e in matched if (e.when or datetime.combine(e.day, datetime.min.time(), timezone.utc)) >= now][:4]
        meta.append({
            "slug": feed.slug, "name": feed.name, "description": feed.description, "count": len(matched),
            "next": [{"when": (e.when.strftime('%a %d %b %H:%M') + ' UTC') if e.when else e.day.strftime('%a %d %b'),
                      "title": f"{flag(e.country)} {e.title}"} for e in upcoming],
        })
        print(f"{feed.slug:18} {len(matched):4} events")
    (out / "feeds.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "index.html").write_text(render_index(meta, args.base_url, generated), encoding="utf-8")
    print(f"Wrote {len(FEEDS)} calendars to {out}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
