from __future__ import annotations

import re
from typing import TypedDict


class CompetitiveAnalysis(TypedDict):
    signal: str
    impact: str
    coverage: str
    recommendation: str
    next_step: str


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


def analyze_competitive_impact(
    *,
    competitor_name: str,
    diff_text: str,
    razorpay_content: str,
) -> CompetitiveAnalysis:
    """Deterministic MVP analyzer; replace this function with an LLM adapter later."""
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
    }