"""Gemini API calls for the 5-step pipeline: filter, cluster, score, summarise, headline."""

import json
from google import genai
from .config import (
    MODEL, MODEL_FAST,
    FILTER_CONTEXT_CHARS, CLUSTER_CONTEXT_CHARS,
    SUMMARY_CONTEXT_CHARS, HEADLINE_CONTEXT_CHARS,
    RELEVANCE_PROMPT, RELEVANCE_SCHEMA,
    SCORE_PROMPT, BATCH_SCORE_SCHEMA,
    SUMMARY_PROMPT, BATCH_SUMMARY_SCHEMA,
    CLUSTER_PROMPT, CLUSTER_SCHEMA,
    HEADLINE_PROMPT, HEADLINE_SCHEMA,
)


def filter_relevant(client: genai.Client, entries: list[dict]) -> list[dict]:
    """One batch call: return only the AI-relevant entries from the full list."""
    if not entries:
        return []
    items = "\n".join(
        f"[{i}] {e['title']} | {e['summary'][:FILTER_CONTEXT_CHARS]}"
        for i, e in enumerate(entries)
    )
    prompt = f"{RELEVANCE_PROMPT}\n\nReturn the indices of all relevant articles:\n{items}"
    response = client.models.generate_content(
        model=MODEL_FAST,
        contents=prompt,
        config={"response_mime_type": "application/json", "response_schema": RELEVANCE_SCHEMA, "temperature": 0},
    )
    indices = set(json.loads(response.text).get("relevant_indices", []))
    return [e for i, e in enumerate(entries) if i in indices]


def cluster_stories(client: genai.Client, entries: list[dict]) -> list[list[int]]:
    """One batch call: group entries by topic, return list of clusters (each is a list of indices)."""
    if not entries:
        return []
    items = "\n".join(
        f"[{i}] {e['title']} | {e['summary'][:CLUSTER_CONTEXT_CHARS]}"
        for i, e in enumerate(entries)
    )
    prompt = f"{CLUSTER_PROMPT}\n\nArticles:\n{items}"
    response = client.models.generate_content(
        model=MODEL_FAST,
        contents=prompt,
        config={"response_mime_type": "application/json", "response_schema": CLUSTER_SCHEMA, "temperature": 0},
    )
    clusters = json.loads(response.text).get("clusters", [])
    return [c["indices"] for c in clusters if c.get("indices")]


def score_items(client: genai.Client, entries: list[dict]) -> list[dict]:
    """One batch call: return importance + uk_relevance scores for each entry. Uses MODEL_FAST."""
    if not entries:
        return []
    items = "\n".join(
        f"[{i}] {e['title']} | {e['summary'][:FILTER_CONTEXT_CHARS]}"
        for i, e in enumerate(entries)
    )
    prompt = f"{SCORE_PROMPT}\n\nScore each of the {len(entries)} articles below:\n{items}"
    response = client.models.generate_content(
        model=MODEL_FAST,
        contents=prompt,
        config={"response_mime_type": "application/json", "response_schema": BATCH_SCORE_SCHEMA, "temperature": 0},
    )
    scores = json.loads(response.text).get("scores", [])
    fallback = {"importance": 1, "uk_relevance": 1}
    while len(scores) < len(entries):
        scores.append(dict(fallback))
    return scores


def summarise_all(client: genai.Client, entries: list[dict]) -> list[dict]:
    """One batch call: summarise all entries and return ordered list of summary dicts."""
    if not entries:
        return []
    items = "\n\n---\n\n".join(
        f"[{i}] Source country hint: {e['country']} | Title: {e['title']}\n{e.get('full_text') or e['summary'][:SUMMARY_CONTEXT_CHARS]}"
        for i, e in enumerate(entries)
    )
    prompt = f"{SUMMARY_PROMPT}\n\nSummarise each of the {len(entries)} articles below:\n\n{items}"
    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config={"response_mime_type": "application/json", "response_schema": BATCH_SUMMARY_SCHEMA, "temperature": 0},
    )
    summaries = json.loads(response.text).get("summaries", [])
    # Pad with fallback if Gemini returns fewer items than expected
    fallback = {"title": "—", "country": "", "action_type": "Other", "body": "—", "strategic_note": "", "importance": 1, "uk_relevance": 1, "translated": False}
    while len(summaries) < len(entries):
        summaries.append(fallback)
    return summaries


def generate_headline(client: genai.Client, summaries: list[dict]) -> dict:
    """One call: generate a two-part executive briefing header from today's summaries."""
    if not summaries:
        return {"uk": "", "international": ""}
    items = "\n".join(
        f"- [{s.get('country', '?')}] [{s.get('action_type', 'Other')}] {s.get('title', '—')}: {s.get('body', '')[:HEADLINE_CONTEXT_CHARS]}"
        for s in summaries
    )
    prompt = f"{HEADLINE_PROMPT}\n\nToday's items:\n{items}"
    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config={"response_mime_type": "application/json", "response_schema": HEADLINE_SCHEMA, "temperature": 0},
    )
    result = json.loads(response.text)
    return {"uk": result.get("uk", ""), "international": result.get("international", "")}
