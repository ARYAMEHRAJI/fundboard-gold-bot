/**
 * FundBoard Crypto scheduler.
 * Cloudflare Cron Trigger: * * * * *
 * Required: KV binding SCHEDULE_KV, secret GITHUB_TOKEN.
 * Uses Tehran local time and idempotency keys in its own KV namespace.
 */
const OWNER = "ARYAMEHRAJI";
const REPO = "fundboard-gold-bot";
const REF = "main";
const WORKFLOW = "publish-crypto-scheduled-content.yml";

function tehranParts(date = new Date()) {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: "Asia/Tehran",
    year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", hourCycle: "h23"
  }).formatToParts(date);
  return Object.fromEntries(parts.filter(p => p.type !== "literal").map(p => [p.type, p.value]));
}

async function dispatchWorkflow(env, inputs) {
  if (!env.GITHUB_TOKEN) throw new Error("Missing GITHUB_TOKEN secret");
  const response = await fetch(
    `https://api.github.com/repos/${OWNER}/${REPO}/actions/workflows/${WORKFLOW}/dispatches`,
    {
      method: "POST",
      headers: {
        "Accept": "application/vnd.github+json",
        "Authorization": `Bearer ${env.GITHUB_TOKEN}`,
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "FundBoard-Crypto-Scheduler",
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ ref: REF, inputs })
    }
  );
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`GitHub dispatch failed (${response.status}): ${body.slice(0, 400)}`);
  }
}

async function dispatchOnce(env, key, inputs) {
  if (await env.SCHEDULE_KV.get(key)) return { skipped: true, key };
  const lockKey = `lock:${key}`;
  if (await env.SCHEDULE_KV.get(lockKey)) return { skipped: true, key, reason: "locked" };
  await env.SCHEDULE_KV.put(lockKey, "1", { expirationTtl: 180 });
  try {
    await dispatchWorkflow(env, inputs);
    await env.SCHEDULE_KV.put(key, new Date().toISOString(), { expirationTtl: 60 * 60 * 24 * 10 });
    return { dispatched: true, key, content_type: inputs.content_type };
  } finally {
    await env.SCHEDULE_KV.delete(lockKey);
  }
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname === "/health") {
      return new Response(JSON.stringify({
        worker: "fundboard-crypto-scheduler",
        status: "ok",
        timezone: "Asia/Tehran",
        cron: "* * * * *",
        workflow: WORKFLOW,
        kv_bound: Boolean(env.SCHEDULE_KV),
        github_token_bound: Boolean(env.GITHUB_TOKEN)
      }, null, 2), { headers: { "content-type": "application/json; charset=utf-8" } });
    }
    return new Response("FundBoard Crypto scheduler is deployed. Visit /health for a non-publishing health check.", {
      headers: { "content-type": "text/plain; charset=utf-8" }
    });
  },

  async scheduled(controller, env, ctx) {
    const p = tehranParts(new Date(controller.scheduledTime));
    const date = `${p.year}-${p.month}-${p.day}`;
    const time = `${p.hour}:${p.minute}`;
    const contentSlots = {
      "09:00": "technical",
      "10:30": "news",
      "12:00": "periodic",
      "14:00": "alts",
      "16:00": "macro",
      "18:00": "education",
      "20:00": "briefing"
    };
    const tasks = [];
    if (contentSlots[time]) {
      tasks.push(dispatchOnce(env, `${date}:content:${time}`, { content_type: contentSlots[time] }));
    }
    if (time === "09:00" || time === "17:00") {
      tasks.push(dispatchOnce(env, `${date}:prices:${time}`, { content_type: "prices" }));
    }
    if (!tasks.length) return;
    const results = await Promise.allSettled(tasks);
    const failures = results.filter(r => r.status === "rejected");
    console.log(JSON.stringify({ date, time, results: results.map(r => r.status === "fulfilled" ? r.value : String(r.reason)) }));
    if (failures.length) throw new Error(`${failures.length} crypto task(s) failed at Tehran ${date} ${time}`);
  }
};
