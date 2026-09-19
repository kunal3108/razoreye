Create a professional README.md for Razoreye and commit it.

Structure it for a hackathon/GitHub audience:

# Razoreye

Competitive AEO Intelligence — Monitor → Detect → Compare → Recommend → Act

Explain that Razoreye is an AEO competitive-intelligence agent that monitors changes in competitors' AI-facing content, versions those changes, uses an LLM to compare them against a brand's existing coverage, generates ACT / WATCH / NO ACTION recommendations, and routes actionable intelligence to Slack.

Include these sections:

Problem
What Razoreye Does
Architecture
Current MVP
Example Workflow
AEO Signals We Can Monitor Next
Tech Stack
Running Locally
Environment Variables
Future Roadmap

For the architecture, show:
Competitor AI-facing content → Monitor → SHA-256 Change Detection → Version/Diff → LLM Analysis → Brand Coverage Comparison → ACT/WATCH/NO ACTION → Slack

Current MVP monitors llms.txt, including Razorpay, Stripe, Cashfree and the DemoPay sandbox. Make it clear that llms.txt is an emerging convention and Razoreye does not assume it is a proven AI ranking factor.

Under future monitoring, mention robots.txt/AI crawler access, sitemaps, schema/structured data, product and documentation changes, API documentation, MCP/agent-discovery surfaces, entity signals, AI answer-engine mentions/citations, share of voice, and eventual GA4/Search Console business-impact correlation.

Tech stack should reflect the actual repository only. Inspect the code before documenting dependencies or commands; do not invent technologies.

For environment variables, list only variable names such as OPENAI_API_KEY and SLACK_BOT_TOKEN. Never include secret values.

Add a short section explaining the differentiation:
Traditional AEO readiness tools: “How AI-ready is my website?”
Razoreye: “What are my competitors changing, does it create a gap for us, and what should we do about it?”

Keep the README concise, polished and product-focused. Do not make unsupported claims about llms.txt, AI rankings, or causality.

After creating it, verify no API keys, Slack tokens, .env files, or razoreye.db are included. Commit the README, but do not modify application functionality.