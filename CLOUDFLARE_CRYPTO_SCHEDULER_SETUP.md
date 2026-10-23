# FundBoard Crypto Scheduler setup

This is a separate scheduler for @FundBoard_Crypto. It does not change the silver Worker or its KV.

## Files added
- publish_crypto_scheduled_content.py: creates one Persian post from public market data or a crypto news RSS feed.
- .github/workflows/publish-crypto-scheduled-content.yml: manual-dispatch-only workflow. It does not publish on push and has no GitHub cron.
- fundboard-crypto-scheduler.js: Cloudflare Worker that dispatches the workflow at scheduled Tehran times.

## Before any publication
1. In GitHub, open repository Settings → Secrets and variables → Actions → New repository secret.
2. Add TELEGRAM_CRYPTO_BOT_TOKEN with a Telegram bot token whose bot is an administrator of @FundBoard_Crypto and has permission to post messages.
3. Do not put bot tokens or GitHub tokens in Variables, code, commits, screenshots, or chat.
4. The Worker needs a new GitHub fine-grained personal access token (PAT), scoped only to ARYAMEHRAJI/fundboard-gold-bot, with Actions: Read and write. Add it to Cloudflare as a Secret named GITHUB_TOKEN. Revoke any previously exposed GitHub token and do not reuse it.

## Create the Worker
1. In Cloudflare Workers & Pages, create a Worker named fundboard-crypto-scheduler.
2. Replace its code with the complete contents of fundboard-crypto-scheduler.js in this repository and deploy it.
3. In Worker Settings → Bindings, create a new KV namespace named fundboard-crypto-schedule and bind it using the variable name SCHEDULE_KV. Do not reuse the silver namespace.
4. In Worker Settings → Variables and Secrets, add GITHUB_TOKEN as a Secret, not a plain text Variable.
5. In Settings → Triggers → Cron Triggers, add * * * * * and save/deploy.

## Safe checks
- Open the Worker's /health URL. It only reports health and binding presence; it does not publish a Telegram message.
- In the response, check that status is ok, kv_bound is true, and github_token_bound is true.
- Verify that TELEGRAM_CRYPTO_BOT_TOKEN exists as a GitHub Actions repository secret before trying a workflow.
- Do not use the GitHub Actions Run workflow button for a publication test unless you are ready for a real post to appear in the channel.
- Scheduled content slots are Tehran time: 09:00 technical + prices; 10:30 news; 12:00 periodic performance; 14:00 altcoins; 16:00 macro; 17:00 prices; 18:00 education; 20:00 briefing.
- Do not remove or change the silver Worker, its KV, or its workflows.

## Content/data notes
Market-price posts use CoinGecko's public API; BTC technical analysis uses Binance daily candles; news uses public CoinDesk/Cointelegraph RSS. If market data or both RSS sources fail, the workflow stops instead of inventing a report. The initial content templates are conservative and should be reviewed before relying on them for trading decisions.
