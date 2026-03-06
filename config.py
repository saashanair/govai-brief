def _feed(country, tier, url, lang="en"):
    return {"country": country, "tier": tier, "url": url, "lang": lang}


GOVUK_KEYWORDS = [
    "artificial intelligence",
    "machine learning",
    "generative AI",
    "large language model",
    "foundation model",
    "algorithmic",
    "data strategy",
    "data governance",
]


def govuk_ai_url(from_date, to_date, keyword="artificial intelligence"):
    """Build the gov.uk news search feed URL for a given date range and keyword."""
    return (
        "https://www.gov.uk/search/news-and-communications.atom"
        f"?keywords={keyword.replace(' ', '+')}"
        f"&public_timestamp%5Bfrom%5D={from_date.strftime('%d/%m/%Y')}"
        f"&public_timestamp%5Bto%5D={to_date.strftime('%d/%m/%Y')}"
        f"&order=updated-newest"
    )


FEEDS = [
    # Tier 1 — Official: UK
    # Note: gov.uk keyword searches are injected dynamically by main.py (see GOVUK_KEYWORDS)
    _feed("UK", "Official", "https://www.england.nhs.uk/feed/"),                           # NHS England
    _feed("UK", "Official", "https://www.bankofengland.co.uk/rss/news"),                   # Bank of England / PRA
    # Tier 1 — Official: US
    _feed("US", "Official", "https://www.whitehouse.gov/news/feed"),
    # Tier 1 — Official: EU
    _feed("EU", "Official", "https://digital-strategy.ec.europa.eu/en/rss.xml"),
    # Tier 1 — Official: Multilateral / intergovernmental
    _feed("INTL",  "Official", "https://www.itu.int/hub/rss/"),                            # UN telecoms + AI standards
    _feed("ASEAN", "Official", "https://asean.org/feed/"),
    _feed("AU",    "Official", "https://au.int/en/rss.xml"),                               # African Union
    # Tier 2 — Analysis: UK think tanks and specialist trade press
    _feed("UK",   "Analysis", "https://www.adalovelaceinstitute.org/feed/"),               # Ada Lovelace Institute
    _feed("UK",   "Analysis", "https://www.bennettschool.cam.ac.uk/feed/"),                # Bennett School of Public Policy (Cambridge)
    _feed("UK",   "Analysis", "https://www.oii.ox.ac.uk/feed/"),                          # Oxford Internet Institute
    _feed("UK",   "Official", "https://www.publictechnology.net/feed/"),                   # UK public sector tech trade press
    _feed("UK",   "Official", "https://www.ukauthority.com/rss"),                         # UK public sector tech trade press
    # Tier 2 — Analysis: International think tanks and specialist trade press
    _feed("US",   "Analysis", "https://cset.georgetown.edu/feed/"),                        # Center for Security and Emerging Technology
    _feed("INTL", "Analysis", "https://futureoflife.org/feed/"),
    _feed("US",   "Analysis", "https://fedscoop.com/feed/"),                               # US federal IT trade press
    _feed("INTL", "Analysis", "https://www.accessnow.org/feed/"),
    _feed("EU",   "Analysis", "https://algorithmwatch.org/en/feed/"),
    _feed("APAC", "Analysis", "https://opengovasia.com/feed/"),                            # Asia-Pacific public sector trade press
    _feed("US",   "Analysis", "https://www.nextgov.com/rss/topic/artificial-intelligence/"),  # US federal IT trade press
    # Tier 3 — Discourse
    _feed("INTL",  "Discourse", "https://www.technologyreview.com/topic/artificial-intelligence/feed"),
    _feed("INTL",  "Discourse", "https://www.wired.com/feed/rss"),
    _feed("India", "Discourse", "https://government.economictimes.indiatimes.com/rss"),
    _feed("INTL",  "Discourse", "https://restofworld.org/feed/"),
    _feed("APAC",  "Discourse", "https://www.computerworld.com/au/feed/"),
    _feed("Gulf",  "Discourse", "https://www.tahawultech.com/feed/"),
    _feed("US",    "Discourse", "https://www.defenseone.com/rss/all/"),                    # US defense policy journalism
    _feed("EU",    "Discourse", "https://www.euractiv.com/feed/"),                         # EU policy journalism
]

MODEL = "gemini-2.5-flash"

RELEVANCE_PROMPT = (
    "Determine which of the following articles are substantially about artificial intelligence, "
    "machine learning, or generative AI — including: AI adopted or deployed in government or "
    "public services (e.g. healthcare AI, defence AI, public sector automation, government AI "
    "procurement, education AI), AI governance or regulation, AI investment, or AI strategy. "
    "Articles may be in any language. Return the indices of all relevant articles. "
    "Exclude: drone technology without AI or ML components, general digitisation or IT projects, "
    "IoT or wearable technology without AI inference, general defence or military news without AI "
    "systems involvement, broad technology surveys or market research not specific to government "
    "AI adoption, and purely commercial AI deals between private companies with no government "
    "involvement, policy implication, or public sector impact, articles where AI is mentioned "
    "only in passing as one of several technologies without being the primary focus of the initiative, "
    "and autonomous military or defence hardware systems (e.g. autonomous aircraft, weapons, or vehicles) "
    "where AI or machine learning is not explicitly described as a component of the system."
)

SUMMARY_PROMPT = (
    "Analyze each article and produce a JSON summary with exactly these keys:\n"
    "\"title\": a short, specific briefing title (max 12 words) that names the actor, the precise action, "
    "and the subject — specific enough that a reader can decide whether to read further without reading "
    "the body. Use precise verbs (mandates, allocates, launches, passes, rejects, proposes) not generic "
    "ones (develops, explores, advances, unveils). Example: 'UK Treasury Mandates AI Risk Disclosure for Banks' "
    "not 'UK Explores AI in Financial Services'.\n"
    "\"country\": the specific country primarily involved or affected. A source country hint is provided "
    "with each article — use it when the article does not explicitly name a country. Use standard country "
    "names (e.g. \"UK\", \"US\", \"Singapore\", \"Vietnam\"). Never use regional labels like \"APAC\" or "
    "\"INTL\". Only use \"Global\" for explicitly multilateral initiatives involving three or more countries "
    "with no single primary actor.\n"
    "\"action_type\": one of: Investment, Regulation, Strategy, Partnership, Deployment, Other\n"
    "\"body\": 2-3 sentences giving enough context to understand what happened, why it matters, "
    "and how it will work — be specific and analytical, avoid vague filler. "
    "Where the article describes a specific law, strategy document, framework, fund, or programme, "
    "name it explicitly.\n"
    "\"strategic_note\": one sentence explaining why this matters to a UK government AI practitioner — "
    "consider what it means for UK domestic AI policy, lessons the UK should draw, regulatory alignment "
    "or divergence with the UK's approach, implications for UK public sector procurement or deployment, "
    "or the UK's competitive positioning relative to what is described\n"
    "\"importance\": integer 1-5 scored as follows — "
    "5: executive order, major legislation passed, national AI strategy launch, or investment above $500M; "
    "4: significant regulatory guidance, ministerial or cabinet-level announcement, major procurement or partnership; "
    "3: regional initiative, policy consultation launched, inter-agency framework or pilot programme; "
    "2: academic research with government funding, minor committee hearing, incremental policy update; "
    "1: commentary, survey, market research, or general industry news\n"
    "\"uk_relevance\": integer 1-5 scoring direct relevance to a UK government AI practitioner — "
    "5: directly affects UK AI policy, legislation, procurement, or regulation; "
    "4: close comparator or partner jurisdiction (US, EU, Australia, Singapore, Canada) making a decision "
    "the UK is likely to follow, align with, or diverge from, or directly involves UK actors; "
    "3: international development with clear UK policy implications or competitive significance; "
    "2: general AI governance trend with weak UK connection; "
    "1: no meaningful UK relevance\n"
    "\"translated\": true if the article was in a non-English language and you translated it, "
    "false otherwise. Always write the summary in English regardless of source language.\n"
)

CLUSTER_PROMPT = (
    "Group articles that report on the exact same specific event, announcement, or publication — "
    "for example, the same named contract, the same piece of legislation, the same named fund or "
    "strategy document, or the same specific government decision covered by multiple outlets. "
    "Do NOT cluster articles simply because they share a country, a government department, or a "
    "general theme. Separate procurements, separate policy announcements, and separate government "
    "initiatives must each be in their own cluster even if they all relate to AI in the same country. "
    "When in doubt, give articles their own cluster. "
    "Return every article index exactly once across all clusters."
)

HEADLINE_PROMPT = (
    "Write a 3-5 sentence executive briefing header summarising today's most important AI governance "
    "and policy developments for a UK government AI practitioner. Lead with UK developments if present, "
    "then international. Identify the top 2-3 themes and their significance for UK policy. "
    "Write in a professional, direct briefing style suitable for a senior policy audience."
)

# Schema for batch relevance filter — returns indices of relevant articles
RELEVANCE_SCHEMA = {
    "type": "object",
    "properties": {
        "relevant_indices": {"type": "array", "items": {"type": "integer"}},
    },
    "required": ["relevant_indices"],
}

SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {
        "title":       {"type": "string"},
        "country":     {"type": "string"},
        "action_type": {"type": "string", "enum": ["Investment", "Regulation", "Strategy", "Partnership", "Deployment", "Other"]},
        "body":        {"type": "string"},
        "strategic_note": {"type": "string"},
        "importance":  {"type": "integer", "minimum": 1, "maximum": 5},
        "uk_relevance": {"type": "integer", "minimum": 1, "maximum": 5},
        "translated":  {"type": "boolean"},
    },
    "required": ["title", "country", "action_type", "body", "strategic_note", "importance", "uk_relevance", "translated"],
}

# Schema for batch summary — array of per-item summaries
BATCH_SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {
        "summaries": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title":       {"type": "string"},
                    "country":     {"type": "string"},
                    "action_type": {"type": "string", "enum": ["Investment", "Regulation", "Strategy", "Partnership", "Deployment", "Other"]},
                    "body":        {"type": "string"},
                    "strategic_note": {"type": "string"},
                    "importance":  {"type": "integer", "minimum": 1, "maximum": 5},
                    "uk_relevance": {"type": "integer", "minimum": 1, "maximum": 5},
                    "translated":  {"type": "boolean"},
                },
                "required": ["title", "country", "action_type", "body", "strategic_note", "importance", "uk_relevance", "translated"],
            },
        }
    },
    "required": ["summaries"],
}

# Schema for story clustering — groups article indices by topic
CLUSTER_SCHEMA = {
    "type": "object",
    "properties": {
        "clusters": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "indices": {"type": "array", "items": {"type": "integer"}},
                },
                "required": ["indices"],
            },
        }
    },
    "required": ["clusters"],
}

# Schema for executive headline
HEADLINE_SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string"},
    },
    "required": ["headline"],
}
