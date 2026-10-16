# FundBoard Gold Bot

Persian-language gold-market research drafts for FundBoard Gold. The current research workflow is **dry-run by design**: it generates local text drafts and uploads them as GitHub Actions artifacts; the research workflow does not send Telegram messages.

## Research modules

- \`generate_gold_technical_report.py\`: spot/close context, daily-session returns, SMA/RSI and conditional scenarios from the configured price source.
- \`generate_gold_macro_report.py\`: dated US real-yield, broad-dollar and policy-rate context plus Federal Reserve releases.
- \`generate_gold_periodic_context.py\`: monitors official World Gold Council pages, discovers official XLSX links, attempts workbook inspection, and adds a clearly attributed summary from the latest public monthly ETF commentary when available.
- \`build_gold_daily_briefing.py\`: combines the technical, macro and periodic sections into a single draft.
- \`analyze_gold_news.py\` / \`publish_gold_news.py\`: existing news selection/publishing code; keep its publishing behavior separate from the research dry-run workflow.

## Run locally

Python 3.12 is recommended. Install the workbook reader and run the offline tests:

\`\`\`bash
python -m pip install openpyxl==3.1.5
python -m unittest -v test_gold_news_logic.py test_gold_technical_report.py test_gold_macro_report.py test_gold_periodic_context.py test_gold_daily_briefing.py
\`\`\`

To build drafts, run the modules in this order:

\`\`\`bash
python generate_gold_technical_report.py
python generate_gold_macro_report.py
python generate_gold_periodic_context.py
python build_gold_daily_briefing.py
\`\`\`

The live-source workflow is \`.github/workflows/validate-gold-news.yml\`. Run it from **Actions** or inspect the most recent run. Artifacts currently expire after seven days.

## Data and accuracy limits

- Official World Gold Council pages:
  - https://www.gold.org/goldhub/data/gold-etfs-holdings-and-flows
  - https://www.gold.org/goldhub/data/gold-reserves-by-country
- ETF holdings/flows are published on weekly/monthly schedules depending on the view; downloadable workbook data is monthly. Central-bank holdings/changes can be reported monthly or quarterly and may lag.
- Goldhub's official XLSX downloads may require a logged-in account; unauthenticated GitHub Actions downloads returned HTTP 403. The script reports that restriction and does **not** invent or reconstruct workbook numbers. Public article summaries, when accessible, are explicitly attributed and are not represented as raw XLSX calculations.
- Optional authorized access: if your Goldhub account permits these downloads, add a repository Actions secret named `WGC_GOLDHUB_COOKIE` containing the session cookie header from your own logged-in session. Do not paste it into chat, commit it, or print it in logs. Session cookies expire and must be refreshed by you. Only set this secret if the account and data terms authorize automated access; otherwise leave it unset. The workflow passes it only to the periodic-context step and only HTTPS requests to official `gold.org` hosts are allowed.
- A genuine numeric time-series pipeline still requires an accessible, permitted source for the underlying workbooks or another authoritative machine-readable feed, plus schema-specific tests before publishing numerical changes.
- Missing, stale, blocked or malformed data should be reported as unavailable rather than silently replaced with guessed values.

## Safety and publishing

- Do not put tokens or other secrets in source files or logs.
- Do not merge the draft pull request or enable new Telegram publishing without explicit approval.
- This project produces research context, not personalized investment advice.
