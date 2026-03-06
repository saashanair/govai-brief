# AI State Intelligence

A personal AI governance briefing tool for public-sector practitioners. Runs every weekday morning, fetches and filters news from 30+ sources, and delivers a structured email briefing covering the latest AI policy, regulation, and deployment developments — with a UK government lens.

---

## What it does

Each run:
1. Fetches RSS feeds from official government sources, policy institutes, and tech journalism
2. Filters for AI-relevant content using Gemini
3. Clusters articles covering the same story to remove duplicates
4. Summarises each story with a what/why/how/impact body and a strategic note for UK practitioners
5. Scores by importance and UK relevance, filtering out low-signal items
6. Sends an HTML email briefing
7. Archives the output to `briefings/YYYY-MM-DD.md` in the repo

---

## Requirements

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) for dependency management
- A [Google Gemini API key](https://aistudio.google.com/app/apikey)
- A Gmail account with an [App Password](https://myaccount.google.com/apppasswords) for email delivery (optional — local runs work without it)

---

## Setup

**1. Clone the repo**

```bash
git clone https://github.com/saashanair/govai-brief.git
cd govai-brief
```

**2. Install dependencies**

```bash
uv sync
```

**3. Create a `.env` file**

```bash
cp .env.example .env
```

Edit `.env` and add your values:

```
GEMINI_API_KEY=your_gemini_api_key

# Optional — only needed for email delivery
GMAIL_USER=you@gmail.com
GMAIL_APP_PASSWORD=your_16_char_app_password
EMAIL_TO=you@example.com,colleague@example.com
```

`EMAIL_TO` accepts comma-separated addresses. All recipients are BCC'd.

---

## Running locally

```bash
uv run python main.py
```

The pipeline only runs Mon–Fri by default. To run on any day:

```bash
FORCE_RUN=1 uv run python main.py
```

To print intermediate pipeline state (relevant items, cluster primaries, scores):

```bash
DEBUG=1 FORCE_RUN=1 uv run python main.py
```

Output is written to `output.md`. If email credentials are not set, the email step is silently skipped.

---

## Automated delivery via GitHub Actions

The workflow in `.github/workflows/briefing.yml` runs at **8am UTC Mon–Fri** (8am GMT / 9am BST).

**One-time setup:**

1. Push the repo to GitHub
2. Generate a Gmail App Password: Google Account → Security → 2-Step Verification → App Passwords
3. Add four secrets in the repo: Settings → Secrets and variables → Actions

| Secret | Value |
|---|---|
| `GEMINI_API_KEY` | Your Gemini API key |
| `GMAIL_USER` | Gmail address to send from |
| `GMAIL_APP_PASSWORD` | 16-character App Password |
| `EMAIL_TO` | Comma-separated recipient addresses |

To trigger a manual run: Actions tab → Daily AI Briefing → Run workflow.

After each run, the workflow commits the dated briefing file (`briefings/YYYY-MM-DD.md`) back to the repo, building a persistent archive.

---

## Feed sources

**Official** — government and intergovernmental bodies, plus UK public sector trade press:
- UK: gov.uk (keyword searches), NHS England, Bank of England, Public Technology, UK Authority
- US: White House
- EU: European Commission Digital Strategy
- Multilateral: ITU, ASEAN, African Union

**Analysis** — think tanks and specialist trade press:
- UK: Ada Lovelace Institute, Bennett School of Public Policy, Oxford Internet Institute
- US: CSET Georgetown, FedScoop, Nextgov, Access Now
- EU: AlgorithmWatch
- Asia-Pacific: OpenGov Asia
- Global: Future of Life Institute

**Discourse** — tech and policy journalism:
- MIT Technology Review, Wired, Rest of World, Defense One, Euractiv, Economic Times Government, Computerworld AU, Tahawul Tech

---

## Scoring and filtering

Each article that passes the relevance filter is assigned two scores by Gemini.

### Importance (1–5)
Measures the weight of the governmental or policy action described. Used for display and sorting only — not used for filtering.

| Score | Criteria |
|---|---|
| 5 | Executive order, major legislation passed, national AI strategy launch, or investment above $500M |
| 4 | Significant regulatory guidance, ministerial or cabinet-level announcement, major procurement or partnership |
| 3 | Regional initiative, policy consultation launched, inter-agency framework or pilot programme |
| 2 | Academic research with government funding, minor committee hearing, incremental policy update |
| 1 | Commentary, survey, market research, or general industry news |

### UK Relevance (1–5)
Measures how directly useful the article is to a UK government AI practitioner. This is the primary filter for non-Official sources.

| Score | Criteria |
|---|---|
| 5 | Directly affects UK AI policy, legislation, procurement, or regulation |
| 4 | Close comparator jurisdiction (US, EU, Australia, Singapore, Canada) making a decision the UK is likely to follow or diverge from |
| 3 | International development with clear UK policy implications or competitive significance |
| 2 | General AI governance trend with weak UK connection |
| 1 | No meaningful UK relevance |

### Filtering rules
Whether an article appears in the briefing depends on its source tier and UK relevance score.

| Tier | Rule |
|---|---|
| Official | Always included — no score threshold |
| Analysis | Included if UK relevance ≥ 2 |
| Discourse | Included if UK relevance ≥ 4 |

**Dynamic backoff:** on days with more than 12 items passing the above rules, the Discourse threshold is raised to UK relevance ≥ 5. This keeps the briefing focused on heavy news days without permanently excluding Discourse sources.

---

## Project structure

```
config.py        — feeds, keywords, prompts, schemas
gemini.py        — 4 Gemini API functions (relevance, clustering, summarise, headline)
main.py          — pipeline orchestration, formatting, email, archiving
output.md        — latest run output (gitignored)
briefings/       — dated archive, one file per run (committed by Actions)
.env.example     — environment variable template
```

---

## Cost

Each run makes 4 Gemini API calls using `gemini-2.5-flash` at `temperature=0`. Typical cost is a few cents per run. Set a [Google Cloud billing alert](https://console.cloud.google.com/billing) as a backstop.
