# AI State Intelligence – Project Instructions

## Purpose
A personal AI governance intelligence tool for public-sector practitioners.

Each run it:
- Fetches RSS feeds across 3 tiers: Official (government + intergovernmental), Analysis (policy institutes), Discourse (tech journalism)
- Filters for AI-relevant items using Gemini, with explicit exclusions for non-AI content
- Deduplicates cross-source coverage by clustering articles about the same event
- Generates structured summaries with action type, importance score, country, and strategic note
- Scores and sorts items by importance, suppressing low-value Analysis/Discourse items
- Produces a 3–5 sentence executive briefing header
- Writes everything to output.md with a UTC timestamp, highest importance first

It is NOT a production system.

---

## Pipeline (4 Gemini API calls per run)

1. **Relevance filter** (`filter_relevant`) — batch call across all fetched entries; returns indices of AI-relevant items
2. **Clustering** (`cluster_stories`) — groups entries by topic/event; the highest-tier entry per cluster becomes the primary; duplicates are silently dropped
3. **Summarise** (`summarise_all`) — batch call across cluster primaries; returns title, country, action_type, body, strategic_note, importance, translated. The strategic note is framed for a UK government AI practitioner — it explains implications for UK domestic policy, regulatory alignment or divergence, public sector procurement, or the UK's competitive positioning.
4. **Headline** (`generate_headline`) — produces a 3–5 sentence executive briefing header from the day's summaries

All calls use `temperature=0` for determinism across runs.

---

## Decision-Making Principles

### Relevance — what is excluded
The relevance filter explicitly excludes:
- Drone technology without AI or ML components
- General digitisation or IT projects
- IoT or wearable technology without AI inference
- General defence or military news without AI systems involvement
- Broad technology surveys or market research not specific to government AI adoption
- Purely commercial AI deals between private companies with no government involvement, policy implication, or public sector impact

### Importance scoring (1–5)
Assigned by Gemini at `temperature=0` against fixed criteria:
- **5**: Executive order, major legislation passed, national AI strategy launch, or investment above $500M
- **4**: Significant regulatory guidance, ministerial or cabinet-level announcement, major procurement or partnership
- **3**: Regional initiative, policy consultation launched, inter-agency framework or pilot programme
- **2**: Academic research with government funding, minor committee hearing, incremental policy update
- **1**: Commentary, survey, market research, or general industry news

### Suppression threshold
- **Official** items: always included regardless of importance score
- **Analysis / Discourse** items: only included if importance ≥ 3

### Cluster primary selection
When multiple articles cover the same event, the highest-tier entry is kept as the primary block. Tier priority: Official > Analysis > Discourse. Secondary entries are silently dropped (not surfaced as "also covered by" since they are not individually verified).

### Country labelling
Country is identified by Gemini from article content, not from the feed's country label. Feed labels (e.g. APAC, INTL) are only used as a fallback if Gemini returns nothing. Multilateral or global initiatives are labelled "Global".

---

## Technical Constraints

- Python only
- Managed with uv
- Three files: config.py, gemini.py, main.py
- No database
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
- Add scheduling
- Add email sending
- Add a database or persistent structured storage (output.md flat file is acceptable)
- Add multi-country configuration systems
- Add CLI frameworks
- Add logging frameworks

Only implement what is explicitly requested.

---

## Feed Sources (26 total)

**Tier 1 — Official: National government**
- UK: gov.uk AI search (date-filtered)
- US: White House, Nextgov AI, StateScoop, MeriTalk
- EU: EU Digital Strategy
- UK: Public Technology, UK Authority, NHS England

**Tier 1 — Official: Multilateral / intergovernmental**
- Global: ITU (UN telecoms + AI standards)
- Southeast Asia: ASEAN
- Africa: African Union
- Asia-Pacific: OpenGov Asia

**Tier 2 — Analysis**
- US: CSET Georgetown, FedScoop, Defense One
- Global: Future of Life Institute, Access Now
- EU: AlgorithmWatch, Euractiv

**Tier 3 — Discourse**
- Global: MIT Technology Review AI, Wired, Rest of World
- India: Economic Times Government
- Asia-Pacific: Computerworld AU
- Gulf/MENA: Tahawul Tech

---

## Future Direction (Not Now)

- SQLite storage
- Weekly synthesis / digest format
- Email delivery
- LinkedIn / social discourse tracking
