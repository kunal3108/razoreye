from __future__ import annotations

import json
import logging
import os
import re
from typing import TypedDict

from openai import OpenAI


logger = logging.getLogger(__name__)

CONTEXT_LINE_LIMIT = 16
CONTEXT_WINDOW = 1
STOP_WORDS = {
    "about",
    "added",
    "after",
    "also",
    "and",
    "api",
    "apis",
    "are",
    "current",
    "from",
    "into",
    "llms",
    "new",
    "not",
    "our",
    "server",
    "the",
    "their",
    "this",
    "txt",
    "with",
}


class CompetitiveAnalysis(TypedDict):
    signal: str
    impact: str
    coverage: str
    recommendation: str
    next_step: str
    source: str


TOPICS = {
    "International Payments": (
        ("international payments", "international payments api"),
        (
            r"International Payments Support from Razorpay",
            r"Accept Payments from International Customers",
            r"cross-border payments",
            r"PA-CB",
        ),
    ),
    "Subscriptions": (
        ("subscriptions", "subscription api"),
        (
            r"Payments \| Subscriptions",
            r"Subscriptions API",
            r"Recurring Payments",
        ),
    ),
    "MCP Server": (
        ("mcp server", "model context protocol"),
        (
            r"About Razorpay MCP Server",
            r"Model Context Protocol",
        ),
    ),
}


def _added_text(diff_text: str) -> str:
    return "\n".join(
        line[1:].strip()
        for line in diff_text.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    ).lower()


def _find_coverage(content: str, patterns: tuple[str, ...]) -> str | None:
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    for pattern in patterns:
        for cleaned in lines:
            if re.search(pattern, cleaned, re.IGNORECASE):
                title_match = re.match(r"- \[([^\]]+)\]", cleaned)
                return title_match.group(1) if title_match else cleaned[:110]
    return None


def _search_terms(diff_text: str) -> set[str]:
    changed_text = " ".join(
        line[1:]
        for line in diff_text.splitlines()
        if line.startswith(("+", "-"))
        and not line.startswith(("+++", "---"))
    ).lower()
    terms = {
        token
        for token in re.findall(r"[a-z0-9][a-z0-9-]+", changed_text)
        if len(token) >= 4 and token not in STOP_WORDS
    }
    for _, (topic_terms, _) in TOPICS.items():
        if any(term in changed_text for term in topic_terms):
            terms.update(
                token
                for term in topic_terms
                for token in re.findall(r"[a-z0-9][a-z0-9-]+", term)
                if len(token) >= 4 and token not in STOP_WORDS
            )
    return terms


def _relevant_context(
    content: str,
    terms: set[str],
    label: str,
    evidence_patterns: tuple[str, ...] = (),
) -> str:
    """Retrieve grounded lines from a complete llms.txt without sending the full file."""
    lines = content.splitlines()
    if not lines:
        return f"[{label} is empty]"

    scored: list[tuple[int, int]] = []
    for index, line in enumerate(lines):
        lowered = line.lower()
        matches = {term for term in terms if term in lowered}
        if matches:
            score = len(matches) * 10 + sum(len(term) for term in matches)
            scored.append((score, index))

    selected: set[int] = set()
    for pattern in evidence_patterns:
        pattern_matches = 0
        for index, line in enumerate(lines):
            if not re.search(pattern, line, re.IGNORECASE):
                continue
            selected.update(
                range(
                    max(0, index - CONTEXT_WINDOW),
                    min(len(lines), index + CONTEXT_WINDOW + 1),
                )
            )
            pattern_matches += 1
            if pattern_matches >= 2:
                break
    for _, index in sorted(scored, reverse=True)[:CONTEXT_LINE_LIMIT]:
        selected.update(
            range(
                max(0, index - CONTEXT_WINDOW),
                min(len(lines), index + CONTEXT_WINDOW + 1),
            )
        )
        for heading_index in range(index, -1, -1):
            if lines[heading_index].lstrip().startswith("#"):
                selected.add(heading_index)
                break

    if not selected:
        return (
            f"[No lexical matches found after scanning the complete {label} "
            "for terms from the detected diff.]"
        )

    return "\n".join(
        f"L{index + 1}: {lines[index]}" for index in sorted(selected)
    )


def deterministic_analysis(
    *,
    competitor_name: str,
    diff_text: str,
    razorpay_content: str,
) -> CompetitiveAnalysis:
    """Reliable local fallback when the external LLM is unavailable."""
    additions = _added_text(diff_text)
    detected: list[str] = []
    covered: list[str] = []
    uncovered: list[str] = []

    for topic, (addition_terms, coverage_patterns) in TOPICS.items():
        if any(term in additions for term in addition_terms):
            detected.append(topic)
            evidence = _find_coverage(razorpay_content, coverage_patterns)
            if evidence:
                covered.append(f"{topic}: {evidence}")
            else:
                uncovered.append(topic)

    if not detected:
        return {
            "signal": f"{competitor_name} expanded its machine-readable product and API coverage.",
            "impact": "LOW",
            "coverage": "No directly comparable topic was identified automatically.",
            "recommendation": "WATCH",
            "next_step": "Review the new entries and map them to Razorpay's current llms.txt coverage.",
            "source": "deterministic_fallback",
        }

    signal_topics = ", ".join(detected[:-1])
    if len(detected) > 1:
        signal_topics += f" and {detected[-1]}"
    else:
        signal_topics = detected[0]

    if uncovered:
        recommendation = "ACT"
        impact = "HIGH"
        next_step = (
            "Confirm Razorpay's equivalent capabilities and add explicit llms.txt coverage "
            f"for {', '.join(uncovered)}."
        )
    else:
        recommendation = "WATCH"
        impact = "MEDIUM"
        next_step = (
            "Compare how prominently Razorpay presents these covered topics and keep "
            "monitoring DemoPay's positioning."
        )

    return {
        "signal": f"{competitor_name} added {signal_topics} across product and API coverage.",
        "impact": impact,
        "coverage": "; ".join(covered)
        if covered
        else "No equivalent Razorpay content was found in the stored llms.txt.",
        "recommendation": recommendation,
        "next_step": next_step,
        "source": "deterministic_fallback",
    }


ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "signal": {"type": "string"},
        "impact": {"type": "string", "enum": ["HIGH", "MEDIUM", "LOW"]},
        "your_coverage": {"type": "string"},
        "recommendation": {
            "type": "string",
            "enum": ["ACT", "WATCH", "NO ACTION"],
        },
        "next_step": {"type": "string"},
    },
    "required": [
        "signal",
        "impact",
        "your_coverage",
        "recommendation",
        "next_step",
    ],
    "additionalProperties": False,
}


def analyze_competitive_impact(
    *,
    competitor_name: str,
    diff_text: str,
    competitor_content: str,
    razorpay_content: str,
) -> CompetitiveAnalysis:
    """Primary LLM analyzer with a deterministic, contract-compatible fallback."""
    try:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not configured")

        terms = _search_terms(diff_text)
        changed_text = _added_text(diff_text)
        evidence_patterns = tuple(
            pattern
            for _, (topic_terms, coverage_patterns) in TOPICS.items()
            if any(term in changed_text for term in topic_terms)
            for pattern in coverage_patterns
        )
        competitor_context = _relevant_context(
            competitor_content, terms, "competitor llms.txt"
        )
        razorpay_context = _relevant_context(
            razorpay_content,
            terms,
            "stored Razorpay llms.txt",
            evidence_patterns,
        )
        client = OpenAI(api_key=api_key, timeout=60.0, max_retries=1)
        response = client.chat.completions.create(
            model=os.environ.get("OPENAI_MODEL", "gpt-5-mini"),
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are Razoreye, a careful competitive intelligence analyst. "
                        "Analyze only the supplied text. Summarize meaningful changes rather "
                        "than repeating diff lines. Explain competitive and AEO significance. "
                        "Before recommending that Razorpay create or add anything, search the "
                        "supplied Razorpay llms.txt for equivalent products, APIs, documentation, "
                        "or topics. Never invent a Razorpay capability or claim coverage without "
                        "direct evidence in that supplied content. If equivalent coverage exists, "
                        "name the strongest matching Razorpay entries and do not recommend creating "
                        "the same capability. Keep every field concise and presentation-ready."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"COMPETITOR NAME:\n{competitor_name}\n\n"
                        f"DETECTED LLMS.TXT DIFF:\n{diff_text}\n\n"
                        "RELEVANT COMPETITOR CONTEXT RETRIEVED FROM THE COMPLETE "
                        f"CURRENT LLMS.TXT:\n{competitor_context}\n\n"
                        "RELEVANT RAZORPAY EVIDENCE RETRIEVED FROM THE COMPLETE "
                        f"STORED LLMS.TXT:\n{razorpay_context}"
                    ),
                },
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "competitive_impact_analysis",
                    "strict": True,
                    "schema": ANALYSIS_SCHEMA,
                },
            },
        )
        content = response.choices[0].message.content
        if not content:
            raise ValueError("LLM returned an empty analysis")
        parsed = json.loads(content)
        if parsed["impact"] not in {"HIGH", "MEDIUM", "LOW"}:
            raise ValueError("LLM returned an invalid impact")
        if parsed["recommendation"] not in {"ACT", "WATCH", "NO ACTION"}:
            raise ValueError("LLM returned an invalid recommendation")
        if not all(
            isinstance(parsed[field], str) and parsed[field].strip()
            for field in (
                "signal",
                "impact",
                "your_coverage",
                "recommendation",
                "next_step",
            )
        ):
            raise ValueError("LLM returned an incomplete analysis")
        return {
            "signal": parsed["signal"].strip(),
            "impact": parsed["impact"],
            "coverage": parsed["your_coverage"].strip(),
            "recommendation": parsed["recommendation"],
            "next_step": parsed["next_step"].strip(),
            "source": "openai",
        }
    except Exception:
        logger.exception("LLM competitive analysis failed; using deterministic fallback")
        return deterministic_analysis(
            competitor_name=competitor_name,
            diff_text=diff_text,
            razorpay_content=razorpay_content,
        )