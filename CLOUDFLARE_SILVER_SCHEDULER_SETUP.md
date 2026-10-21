# FundBoard Silver minute scheduler

This Worker replaces the *schedule trigger* for the two publishing workflows. It dispatches the existing GitHub Actions workflows; content generation and Telegram publishing remain in the repository.

## Important
- Cloudflare Cron Triggers are not hard real-time. The Worker checks every minute, but GitHub Actions queueing and Telegram/network delays can still delay a post.
- Do not disable GitHub's current schedules until the Worker is deployed and verified. Otherwise there may be a gap in publishing.
- After verification, remove the `schedule:` blocks from:
  - `.github/workflows/publish-silver-scheduled-content.yml`
  - `.github/workflows/publish-silver-prices.yml`
  Keep each workflow's `workflow_dispatch:` trigger so the Worker can launch it.
- A KV namespace is used to prevent duplicate dispatches for the same slot.

## 1. Create the KV namespace
In Cloudflare Dashboard, open Workers & Pages → KV and create a namespace named e.g. `fundboard-silver-schedule`.

## 2. Create the Worker
Create a Worker named `fundboard-silver-scheduler`, paste the contents of `fundboard-silver-scheduler.js`, and add:
- Binding: KV namespace, variable name `SCHEDULE_KV`, select the namespace created above.
- Secret: `GITHUB_TOKEN`, a fine-grained GitHub token restricted to `ARYAMEHRAJI/fundboard-gold-bot` with **Actions: Read and write** permission. Do not put this token in repository files.

## 3. Add the Cron Trigger
Worker → Settings → Triggers → Cron Triggers → add:
`* * * * *`

The code calculates the local date and time in `Asia/Tehran` and dispatches only at these slots:
- 09:00 technical post + silver price
- 10:30 news
- 12:00 periodic performance
- 14:00 gold/silver comparison
- 16:00 macro analysis
- 17:00 silver price
- 18:00 education
- 20:00 daily briefing

## 4. Verify before switching over
Check Worker logs and GitHub Actions after a test window. Confirm each slot creates exactly one workflow run and that Telegram actually receives the post. Only after that should the two GitHub `schedule:` triggers be removed, to avoid duplicate posts.
