/**
 * FundBoard Silver scheduler.
 * Cloudflare Cron Trigger: every minute (* * * * *)
 * Required bindings/secrets:
 *   SCHEDULE_KV (KV namespace binding)
 *   GITHUB_TOKEN (fine-grained PAT with Actions: write on this repo)
 */
const OWNER = "ARYAMEHRAJI";
const REPO = "fundboard-gold-bot";
const REF = "main";
const CONTENT_WORKFLOW = "publish-silver-scheduled-content.yml";
const PRICE_WORKFLOW = "publish-silver-prices.yml";

function tehranParts(date = new Date()) {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: "Asia/Tehran",
    year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", hourCycle: "h23"
  }).formatToParts(date);
  return Object.fromEntries(parts.filter(p => p.type !== "literal").map(p => [p.type, p.value]));
}

async function dispatchWorkflow(env, workflow, inputs = {}) {
  const response = await fetch(
    `https://api.github.com/repos/${OWNER}/${REPO}/actions/workflows/${workflow}/dispatches`,
    {
      method: "POST",
      headers: {
        "Accept": "application/vnd.github+json",
        "Authorization": `Bearer ${env.GITHUB_TOKEN}`,
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "FundBoard-Silver-Scheduler",
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ ref: REF, inputs })
    }
  );
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`GitHub dispatch failed (${response.status}): ${body.slice(0, 500)}`);
  }
}

async function dispatchOnce(env, key, workflow, inputs = {}) {
  if (await env.SCHEDULE_KV.get(key)) return { skipped: true, key };
  // Put a short-lived lock before dispatch to avoid overlapping minute ticks.
  const lockKey = `lock:${key}`;
  if (await env.SCHEDULE_KV.get(lockKey)) return { skipped: true, key, reason: "locked" };
  await env.SCHEDULE_KV.put(lockKey, "1", { expirationTtl: 180 });
  try {
    await dispatchWorkflow(env, workflow, inputs);
    await env.SCHEDULE_KV.put(key, new Date().toISOString(), { expirationTtl: 60 * 60 * 24 * 10 });
    return { dispatched: true, key };
  } finally {
    await env.SCHEDULE_KV.delete(lockKey);
  }
}

export default {
  async scheduled(controller, env, ctx) {
    const p = tehranParts(new Date(controller.scheduledTime));
    const date = `${p.year}-${p.month}-${p.day}`;
    const time = `${p.hour}:${p.minute}`;
    const contentSlots = {
      "09:00": "technical",
      "10:30": "news",
      "12:00": "periodic",
      "14:00": "comparison",
      "16:00": "macro",
      "18:00": "education",
      "20:00": "briefing"
    };
    const tasks = [];
    if (contentSlots[time]) {
      tasks.push(dispatchOnce(env, `${date}:content:${time}`, CONTENT_WORKFLOW, {
        content_type: contentSlots[time]
      }));
    }
    if (time === "09:00" || time === "17:00") {
      tasks.push(dispatchOnce(env, `${date}:price:${time}`, PRICE_WORKFLOW, {
        publish_now: "true"
      }));
    }
    if (!tasks.length) return;
    const results = await Promise.allSettled(tasks);
    const failures = results.filter(r => r.status === "rejected");
    if (failures.length) {
      console.error(JSON.stringify(failures.map(f => String(f.reason))));
      throw new Error(`${failures.length} scheduled task(s) failed at Tehran ${date} ${time}`);
    }
    console.log(JSON.stringify({ date, time, results: results.map(r => r.value) }));
  }
};
