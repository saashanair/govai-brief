# AI State Intelligence – Project Instructions

## Purpose
A personal AI governance intelligence tool for public-sector practitioners.

Each run it:
- Fetches RSS feeds across 3 tiers: Official (government + intergovernmental + UK trade press), Analysis (policy institutes + specialist trade press), Discourse (tech journalism)
- Filters for AI-relevant items using Gemini, with explicit exclusions for non-AI content
- Deduplicates cross-source coverage by clustering articles about the exact same named event
- Generates structured summaries with action type, importance score, uk_relevance score, and strategic note
- Filters by tier-aware uk_relevance thresholds with dynamic backoff on heavy news days
- Produces a 3–5 sentence executive briefing header
- Writes to output.md and archives to briefings/YYYY-MM-DD.md
- Sends HTML + plain text email via Gmail SMTP
- GitHub Actions commits the dated briefing file back to the repo

It is NOT a production system.

---

## Pipeline (4 Gemini API calls per run)

1. **Relevance filter** (`filter_relevant`) — batch call; 300-char context window per entry; returns indices of AI-relevant items
2. **Clustering** (`cluster_stories`) — groups entries by exact same named event only; highest-tier entry per cluster becomes primary; duplicates silently dropped. Bias is towards separate clusters — same country or same general topic does NOT justify clustering.
3. **Summarise** (`summarise_all`) — batch call; 1000-char context window; returns title, country, action_type, body, strategic_note, importance, uk_relevance, translated
4. **Headline** (`generate_headline`) — produces a 3–5 sentence executive briefing header

All calls use `temperature=0` for determinism.

---

## Decision-Making Principles

### Relevance — what is excluded
- Drone technology without AI or ML components
- General digitisation or IT projects
- IoT or wearable technology without AI inference
- General defence or military news without AI systems involvement
- Broad technology surveys or market research not specific to government AI adoption
- Purely commercial AI deals between private companies with no government involvement, policy implication, or public sector impact
- Articles where AI is mentioned only in passing
- Autonomous military hardware where AI is not explicitly described as a component

### Importance scoring (1–5)
Computed by Gemini but NOT used for suppression — used for display and sorting only:
- **5**: Executive order, major legislation passed, national AI strategy launch, or investment above $500M
- **4**: Significant regulatory guidance, ministerial or cabinet-level announcement, major procurement or partnership
- **3**: Regional initiative, policy consultation launched, inter-agency framework or pilot programme
- **2**: Academic research with government funding, minor committee hearing, incremental policy update
- **1**: Commentary, survey, market research, or general industry news

### uk_relevance scoring (1–5)
Primary filter for non-Official sources:
- **5**: Directly affects UK AI policy, legislation, procurement, or regulation
- **4**: Close comparator jurisdiction (US, EU, Australia, Singapore, Canada) making a decision UK is likely to follow or diverge from
- **3**: International development with clear UK policy implications or competitive significance
- **2**: General AI governance trend with weak UK connection
- **1**: No meaningful UK relevance

### Suppression threshold (tier-aware)
- **Official**: always included
- **Analysis**: included if uk_relevance ≥ 2
- **Discourse**: included if uk_relevance ≥ 4
- **Dynamic backoff**: if total combined items > 12, Discourse tightened to uk_relevance ≥ 5

### Tier definitions and rationale
- **Official**: Actual government/intergovernmental bodies AND UK-specific trade press (PublicTechnology, UK Authority). UK trade press is Official because their content is inherently UK-relevant and should not be gated by scoring.
- **Analysis**: Think tanks, research institutes, and specialist trade press covering a specific government beat (FedScoop, Nextgov, OpenGov Asia). Content is gated by uk_relevance ≥ 2.
- **Discourse**: General tech/policy journalism. Higher bar — uk_relevance ≥ 4.

### Cluster primary selection
Tier priority: Official > Analysis > Discourse. Secondary entries silently dropped.

### Strategic note framing
The strategic note answers: "why should someone working in UK government AI take note of this?" It covers risk, opportunity, precedent, or direction of travel. It does NOT name specific UK government departments, bodies, or frameworks — these change frequently due to machinery of government (MOG) changes and Gemini hallucinates defunct structures. For example, CDDO and the Office for AI no longer exist as named entities.

### Country labelling
Identified by Gemini from article content. Feed labels (APAC, INTL) used as fallback only. Multilateral initiatives → "Global".

---

## Technical Constraints

- Python only
- Managed with uv
- Three files in `govai_brief/`: config.py, gemini.py, main.py
- No database (briefings/ flat file archive is acceptable)
- No web server
- No authentication
- No UI
- No over-engineering
- No frameworks

---

## Coding Style

- Simple functional design
- No unnecessary classes
- Clear small functions
- Minimal dependencies
- Clear comments

---

## Scope Rules

DO NOT:
- Add multi-country configuration systems
- Add CLI frameworks
- Add logging frameworks

Only implement what is explicitly requested.

---

## Running Locally

```bash
uv run govai-brief                          # normal run (Mon–Fri only)
FORCE_RUN=1 uv run govai-brief              # bypass weekend check
DEBUG=1 FORCE_RUN=1 uv run govai-brief      # print all intermediate state
```

DEBUG mode prints: all relevant items after filter, cluster primaries, and all scored items with PASS/DROP status before final filter.

---

## Delivery

- HTML + plain text multipart email via Gmail SMTP (`smtplib`, stdlib only)
- All recipients via BCC — no recipient sees others' addresses
- Silently skips if `GMAIL_USER`, `GMAIL_APP_PASSWORD`, `EMAIL_TO` not set
- `EMAIL_TO`: comma-separated, all addresses go to BCC
- Monday subject line: "weekend roundup (Fri–Sun dates)"

---

## GitHub Actions

- Workflow: `.github/workflows/briefing.yml`
- Schedule: `0 8 * * 1-5` (8am UTC Mon–Fri = 8am GMT / 9am BST)
- `workflow_dispatch` enables manual triggers from the Actions tab
- After each run: commits `briefings/YYYY-MM-DD.md` back to repo
- Required secrets: `GEMINI_API_KEY`, `GMAIL_USER`, `GMAIL_APP_PASSWORD`, `EMAIL_TO`

---

## Feed Sources

**Tier 1 — Official: UK government**
- gov.uk dynamic keyword searches (8 terms — see `GOVUK_KEYWORDS` in config.py)
- NHS England (publishes on own platform, not gov.uk)
- Bank of England / PRA (independent, publishes on own platform)
- Public Technology (UK public sector trade press — inherently UK-relevant)
- UK Authority (UK public sector trade press — inherently UK-relevant)

**Tier 1 — Official: US government**
- White House

**Tier 1 — Official: EU**
- EU Digital Strategy (European Commission)

**Tier 1 — Official: Multilateral / intergovernmental**
- ITU (UN telecoms + AI standards)
- ASEAN
- African Union

**Tier 2 — Analysis: UK**
- Ada Lovelace Institute
- Bennett School of Public Policy (Cambridge)
- Oxford Internet Institute (OII)

**Tier 2 — Analysis: International**
- CSET Georgetown
- Future of Life Institute
- FedScoop (US federal IT trade press)
- Access Now
- AlgorithmWatch
- OpenGov Asia (Asia-Pacific public sector trade press)
- Nextgov (US federal IT trade press)

**Tier 3 — Discourse**
- MIT Technology Review AI
- Wired
- Economic Times Government (India)
- Rest of World
- Computerworld AU
- Tahawul Tech (Gulf/MENA)
- Defense One (US defense policy journalism)
- Euractiv (EU policy journalism)

**Removed / ruled out**
- ICO, CMA, AISI, NCSC, DASA, GDS, CDDO — covered by gov.uk keyword searches
- StateScoop, MeriTalk — duplicates (same publisher as FedScoop / weak signal)
- Alan Turing Institute — 403 error, likely IP-restricted
- Tony Blair Institute — no RSS feed
- Ofcom — no RSS feed

---

## Output Files

- `output.md` — latest run, overwritten each time (gitignored)
- `briefings/YYYY-MM-DD.md` — one file per run, committed to repo by Actions bot
- Future: monthly synthesis digest from briefings/ archive (not yet implemented)

---

## Future Direction (Not Now)

- Monthly synthesis: read all briefings/ from past month, generate trend/theme digest via Gemini, email on 1st of month
- Additional sources: OECD AI Policy Observatory, Stanford HAI, AI Now Institute, Brookings, Institute for Government, Council of Europe, Canada/Australia/Singapore official feeds
- Slack delivery: summary ping to a channel (headlines only, not full briefing)
