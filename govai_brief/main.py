"""Entry point for the AI State Intel daily briefing pipeline."""

import html as html_lib
import os
import re
import smtplib
import socket
import feedparser
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from google import genai

from .config import FEEDS, GOVUK_KEYWORDS, govuk_ai_url, FEED_ENTRY_LIMIT
from .gemini import filter_relevant, cluster_stories, summarise_all, generate_headline

load_dotenv()

# Tier priority for cluster deduplication: lower rank = higher priority
_TIER_RANK = {"Official": 0, "Analysis": 1, "Discourse": 2}


def strip_html(text: str) -> str:
    """Remove HTML tags from feed summary text."""
    return re.sub(r'<[^>]+>', '', text)


def fetch_entries(feed: dict, lookback_dates: set, limit: int = FEED_ENTRY_LIMIT) -> list[dict]:
    """Fetch entries within lookback_dates. Silently skips feeds that fail or time out."""
    try:
        parsed = feedparser.parse(feed["url"])
    except Exception:
        return []
    if not parsed.entries:
        return []
    entries = []
    for entry in parsed.entries[:limit]:
        published_parsed = entry.get("published_parsed") or entry.get("updated_parsed")
        if not published_parsed:
            continue  # skip entries with no date — can't verify recency
        # Compare date only, ignore time and timezone conversion
        published_date = datetime(*published_parsed[:3]).date()
        if published_date not in lookback_dates:
            continue
        entries.append({
            "country": feed["country"],
            "tier": feed["tier"],
            "lang": feed.get("lang", "en"),
            "published": datetime(*published_parsed[:3]).strftime("%-d %b %Y"),
            "title": entry.get("title", "No title"),
            "summary": strip_html(entry.get("summary", entry.get("description", ""))),
            "link": entry.get("link", ""),
        })
    return entries


def collect_entries(feeds: list[dict], lookback_dates: set) -> list[dict]:
    """Fetch all entries from all feeds, deduplicated by URL."""
    all_entries = []
    for feed in feeds:
        all_entries.extend(fetch_entries(feed, lookback_dates))
    # Deduplicate by URL — gov.uk keyword searches often return the same article for multiple
    # keywords, inflating token usage across all 4 Gemini calls.
    seen_urls = set()
    deduped = []
    for e in all_entries:
        if e["link"] not in seen_urls:
            seen_urls.add(e["link"])
            deduped.append(e)
    return deduped


def resolve_clusters(relevant_entries: list[dict], clusters: list[list[int]]) -> list[dict]:
    """For each cluster, pick the highest-tier entry as primary. Ensures every index is covered."""
    # Guard: ensure every index appears in exactly one cluster
    clustered_indices = {i for cluster in clusters for i in cluster}
    for i in range(len(relevant_entries)):
        if i not in clustered_indices:
            clusters.append([i])

    clustered_items = []
    for cluster in clusters:
        valid = [i for i in cluster if i < len(relevant_entries)]
        if not valid:
            continue
        cluster_entries = [relevant_entries[i] for i in valid]
        sorted_entries = sorted(cluster_entries, key=lambda e: _TIER_RANK.get(e["tier"], 99))
        clustered_items.append(sorted_entries[0])
    return clustered_items


def apply_tier_filter(summaries: list[dict], clustered_items: list[dict]) -> list[tuple[dict, dict]]:
    """Apply tier-aware uk_relevance thresholds, with dynamic backoff on heavy news days."""
    scored_items = [
        (s, e)
        for s, e in zip(summaries, clustered_items)
        if e["tier"] == "Official"
        or (e["tier"] == "Analysis" and s.get("uk_relevance", 0) >= 2)
        or (e["tier"] == "Discourse" and s.get("uk_relevance", 0) >= 4)
    ]
    # Dynamic backoff: on heavy news days (> 12 items), tighten Discourse to uk_relevance >= 5
    if len(scored_items) > 12:
        scored_items = [
            (s, e) for s, e in scored_items
            if e["tier"] != "Discourse" or s.get("uk_relevance", 0) >= 5
        ]
    return scored_items


def render_section(items: list[tuple[dict, dict]]) -> str:
    """Render a list of (summary, entry) pairs as formatted text blocks."""
    return "\n\n".join(format_block(s, e) for s, e in items)


def format_block(data: dict, entry: dict) -> str:
    """Format a summary dict into the display block."""
    translated = " | Translated" if data.get("translated") else ""
    country = data.get("country") or entry["country"]
    importance = data.get("importance", 0)
    uk_relevance = data.get("uk_relevance", 0)
    return (
        f"=========================\n"
        f"{country} | {entry['tier']} | {data.get('action_type', 'Other')}{translated} | Importance: {importance}/5 | UK Relevance: {uk_relevance}/5\n"
        f"{entry['published']}\n\n"
        f"{data.get('title', '—')}\n\n"
        f"{data.get('body', '—')}\n\n"
        f"Strategic note: {data.get('strategic_note', '')}\n\n"
        f"Source: {entry['link']}\n"
        f"========================="
    )


def format_block_html(data: dict, entry: dict) -> str:
    """Format a summary dict as an HTML card for the email."""
    importance   = data.get("importance", 0)
    country      = html_lib.escape(data.get("country") or entry["country"])
    action_type  = html_lib.escape(data.get("action_type", "Other"))
    translated   = " &middot; Translated" if data.get("translated") else ""
    tier         = html_lib.escape(entry["tier"])
    published    = html_lib.escape(entry.get("published", ""))
    title        = html_lib.escape(data.get("title", "—"))
    body         = html_lib.escape(data.get("body", "—")).replace("\n", "<br>")
    strategic    = html_lib.escape(data.get("strategic_note", ""))
    link         = html_lib.escape(entry.get("link", ""))

    imp_colors   = {5: "#b71c1c", 4: "#c84b00", 3: "#7a5c00", 2: "#546e7a", 1: "#90a4ae"}
    imp_color    = imp_colors.get(importance, "#90a4ae")

    return (
        f'<table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:16px;border:1px solid #dde1e7;">'
        f'<tr><td style="background:#f5f6f8;padding:8px 14px;border-bottom:1px solid #dde1e7;">'
        f'<table width="100%" cellpadding="0" cellspacing="0"><tr>'
        f'<td style="font-family:Arial,sans-serif;font-size:11px;color:#666;">'
        f'{country} &middot; {tier} &middot; {action_type}{translated} &middot; {published}'
        f'</td>'
        f'<td align="right" style="font-family:Arial,sans-serif;font-size:11px;font-weight:bold;color:{imp_color};white-space:nowrap;">'
        f'Importance {importance}/5'
        f'</td></tr></table></td></tr>'
        f'<tr><td style="padding:14px 16px;">'
        f'<h3 style="margin:0 0 10px;font-family:Georgia,serif;font-size:15px;font-weight:bold;color:#1a3a5c;line-height:1.4;">{title}</h3>'
        f'<p style="margin:0 0 12px;font-family:Arial,sans-serif;font-size:13px;line-height:1.6;color:#333;">{body}</p>'
        f'<table width="100%" cellpadding="10" cellspacing="0" style="border-left:3px solid #1a3a5c;background:#f0f4f8;margin-bottom:12px;">'
        f'<tr><td style="font-family:Arial,sans-serif;font-size:12px;line-height:1.5;color:#444;">'
        f'<strong>Strategic note:</strong> {strategic}'
        f'</td></tr></table>'
        f'<p style="margin:0;font-family:Arial,sans-serif;font-size:12px;">'
        f'<a href="{link}" style="color:#1a3a5c;">Read source &rarr;</a>'
        f'</p></td></tr></table>'
    )


def build_html_email(subject: str, timestamp: str, headline: str, uk_items: list, intl_items: list) -> str:
    """Build a complete HTML email document from the briefing content."""

    def section_html(label, items):
        if not items:
            return ""
        cards = "".join(format_block_html(s, e) for s, e in items)
        return (
            f'<tr><td style="padding:20px 28px 8px;">'
            f'<h2 style="margin:0 0 14px;font-family:Georgia,serif;font-size:17px;'
            f'color:#1a3a5c;border-bottom:2px solid #1a3a5c;padding-bottom:8px;">{label}</h2>'
            f'{cards}</td></tr>'
        )

    headline_row = ""
    if headline:
        escaped_headline = html_lib.escape(headline).replace("\n", "<br>")
        headline_row = (
            f'<tr><td style="padding:20px 28px;background:#eef2f7;border-bottom:1px solid #d0d8e4;">'
            f'<p style="margin:0 0 6px;font-family:Arial,sans-serif;font-size:10px;'
            f'text-transform:uppercase;letter-spacing:1.5px;color:#7a8fa6;">Executive Briefing</p>'
            f'<p style="margin:0;font-family:Georgia,serif;font-size:14px;line-height:1.7;color:#1a3a5c;">'
            f'{escaped_headline}</p></td></tr>'
        )

    return (
        '<!DOCTYPE html><html lang="en"><head>'
        '<meta charset="UTF-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1.0">'
        f'<title>{html_lib.escape(subject)}</title>'
        '</head>'
        '<body style="margin:0;padding:0;background:#edf0f4;">'
        '<table width="100%" cellpadding="0" cellspacing="0" style="background:#edf0f4;">'
        '<tr><td align="center" style="padding:24px 12px;">'
        '<table width="640" cellpadding="0" cellspacing="0" style="max-width:640px;width:100%;background:#ffffff;border:1px solid #dde1e7;">'
        # Header
        '<tr><td style="background:#1a3a5c;padding:22px 28px;">'
        '<p style="margin:0 0 4px;font-family:Arial,sans-serif;font-size:10px;'
        'text-transform:uppercase;letter-spacing:1.5px;color:#a8c4d8;">AI Governance Intelligence</p>'
        f'<h1 style="margin:0;font-family:Georgia,serif;font-size:20px;font-weight:bold;color:#ffffff;">'
        f'{html_lib.escape(subject)}</h1>'
        '</td></tr>'
        # Timestamp
        '<tr><td style="padding:6px 28px;background:#f8f9fa;border-bottom:1px solid #e0e4ea;">'
        f'<p style="margin:0;font-family:Arial,sans-serif;font-size:11px;color:#999;">{html_lib.escape(timestamp)}</p>'
        '</td></tr>'
        # Executive briefing
        + headline_row
        + section_html("UK", uk_items)
        + section_html("International", intl_items)
        # Footer
        + '<tr><td style="padding:14px 28px;background:#f8f9fa;border-top:1px solid #e0e4ea;">'
        '<p style="margin:0;font-family:Arial,sans-serif;font-size:11px;color:#bbb;text-align:center;">'
        'AI State Intelligence &middot; Automated daily briefing'
        '</p></td></tr>'
        '</table></td></tr></table>'
        '</body></html>'
    )


def send_email(subject: str, plain_body: str, html_body: str = None) -> None:
    """Send the briefing via Gmail SMTP. Silently skips if credentials are not set.
    EMAIL_TO may be comma-separated; all addresses go to BCC to preserve privacy.
    Sends multipart/alternative (HTML + plain text fallback) when html_body is provided.
    """
    gmail_user     = os.getenv("GMAIL_USER")
    gmail_password = os.getenv("GMAIL_APP_PASSWORD")
    email_to_raw   = os.getenv("EMAIL_TO")
    if not all([gmail_user, gmail_password, email_to_raw]):
        return  # not configured — local runs without email are fine
    recipients = [r.strip() for r in email_to_raw.split(",") if r.strip()]
    if html_body:
        msg = MIMEMultipart("alternative")
        msg.attach(MIMEText(plain_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))
    else:
        msg = MIMEText(plain_body, "plain")
    msg["Subject"] = subject
    msg["From"]    = f"AI Governance Briefing <{gmail_user}>"
    msg["To"]      = gmail_user  # all recipients go via BCC to preserve privacy
    msg["Bcc"]     = ", ".join(recipients)
    with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
        smtp.starttls()
        smtp.login(gmail_user, gmail_password)
        smtp.sendmail(gmail_user, recipients, msg.as_string())
    print(f"Briefing emailed to {len(recipients)} recipient(s)")


def main():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise SystemExit("Error: GEMINI_API_KEY not set. Add it to a .env file.")

    # Weekend check: only run Mon–Fri (set FORCE_RUN=1 to bypass locally)
    today = datetime.now(timezone.utc).date()
    weekday = today.weekday()  # 0=Mon, 6=Sun
    if weekday >= 5 and not os.getenv("FORCE_RUN"):
        print("No briefing on weekends. Set FORCE_RUN=1 to override.")
        return

    # Monday: cover Fri/Sat/Sun; otherwise just yesterday
    lookback_days = 3 if weekday == 0 else 1
    lookback_start = today - timedelta(days=lookback_days)
    yesterday = today - timedelta(days=1)
    lookback_dates = {lookback_start + timedelta(days=i) for i in range(lookback_days)}

    # One gov.uk search feed per keyword; clustering handles any cross-keyword duplicates
    govuk_feeds = [
        {"country": "UK", "tier": "Official", "lang": "en",
         "url": govuk_ai_url(lookback_start, yesterday, kw)}
        for kw in GOVUK_KEYWORDS
    ]
    feeds = govuk_feeds + FEEDS

    client = genai.Client(api_key=api_key)
    socket.setdefaulttimeout(10)  # 10s per feed request; prevents hangs on slow/dead feeds

    # API call 1: batch relevance filter
    all_entries = collect_entries(feeds, lookback_dates)
    debug = bool(os.getenv("DEBUG"))
    print(f"Fetched {len(all_entries)} entries (after URL dedup). Filtering for AI relevance...")

    relevant = filter_relevant(client, all_entries)
    print(f"{len(relevant)} relevant. Clustering stories...")

    if debug:
        print("\n--- RELEVANT ITEMS ---")
        for i, e in enumerate(relevant):
            print(f"[{i}] {e['tier']:10} | {e['country']:6} | {e['title']}")
        print()

    # API call 2: cluster by topic to deduplicate cross-source coverage
    clusters = cluster_stories(client, relevant)
    clustered_items = resolve_clusters(relevant, clusters)
    print(f"{len(clustered_items)} clustered items. Summarising...")

    if debug:
        print("--- CLUSTER PRIMARIES ---")
        for i, e in enumerate(clustered_items):
            print(f"[{i}] {e['tier']:10} | {e['country']:6} | {e['title']}")
        print()

    # API call 3: batch summarise primary entries
    summaries = summarise_all(client, clustered_items)

    if debug:
        print("--- ALL SCORED ITEMS (before filter) ---")
        for s, e in zip(summaries, clustered_items):
            status = "PASS" if (
                e["tier"] == "Official"
                or (e["tier"] == "Analysis" and s.get("uk_relevance", 0) >= 2)
                or (e["tier"] == "Discourse" and s.get("uk_relevance", 0) >= 4)
            ) else "DROP"
            print(f"[{status}] {e['tier']:10} | imp={s.get('importance')}/5 ukr={s.get('uk_relevance')}/5 | {e['country']:6} | {s.get('title', e['title'])}")
        print()

    scored_items = apply_tier_filter(summaries, clustered_items)

    if not scored_items:
        print("No AI-relevant entries found in the latest feed items.")
        return

    # Split into UK and international, each sorted by their primary score
    uk_items = sorted(
        [(s, e) for s, e in scored_items if s.get("country") == "UK"],
        key=lambda x: x[0].get("uk_relevance", 0), reverse=True
    )
    intl_items = sorted(
        [(s, e) for s, e in scored_items if s.get("country") != "UK"],
        key=lambda x: (x[0].get("uk_relevance", 0), x[0].get("importance", 0)), reverse=True
    )

    print("Generating executive summary...")

    # API call 4: executive briefing header
    headline = generate_headline(client, [s for s, _ in uk_items + intl_items])

    # Format output with UK section first, then international
    sections = []
    if uk_items:
        sections.append("## UK\n\n" + render_section(uk_items))
    if intl_items:
        sections.append("## International\n\n" + render_section(intl_items))

    output = "\n\n---\n\n".join(sections)
    print(output)

    total = len(uk_items) + len(intl_items)
    timestamp = datetime.now(timezone.utc).strftime("Generated: %Y-%m-%d %H:%M UTC")

    # Build full content string (used for both file and email)
    full_content = f"{timestamp}\n\n"
    if headline:
        full_content += f"## Today's Briefing\n\n{headline}\n\n---\n\n"
    full_content += f"{output}\n"

    with open("output.md", "w") as f:
        f.write(full_content)
    print(f"\nWritten to output.md ({total} items: {len(uk_items)} UK, {len(intl_items)} international)")

    os.makedirs("briefings", exist_ok=True)
    dated_path = f"briefings/{today.strftime('%Y-%m-%d')}.md"
    with open(dated_path, "w") as f:
        f.write(full_content)
    print(f"Archived to {dated_path}")

    # Build email subject — Monday gets a weekend-roundup label
    if weekday == 0:
        date_label = f"{lookback_start.strftime('%-d %b')}–{yesterday.strftime('%-d %b %Y')} (weekend roundup)"
    else:
        date_label = today.strftime("%-d %B %Y")
    subject = f"AI Governance Briefing — {date_label}"

    html_body = build_html_email(subject, timestamp, headline, uk_items, intl_items)
    send_email(subject, full_content, html_body)


if __name__ == "__main__":
    main()
