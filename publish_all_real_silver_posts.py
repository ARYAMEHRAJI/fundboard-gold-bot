"""Publish all seven AI-rewritten, Persian-only FundBoard Silver categories once with the required linked footer. Latest revision only."""
import os
import subprocess
import sys
import time

CATEGORIES = [
    ("technical", "تحلیل تکنیکال"),
    ("periodic", "بازدهی دوره‌ای"),
    ("news", "اخبار و تحلیل"),
    ("comparison", "مقایسه طلا و نقره"),
    ("macro", "تحلیل بنیادی و اقتصاد کلان"),
    ("education", "آموزش تخصصی"),
    ("briefing", "جمع‌بندی روزانه"),
]

def main():
    # Explicitly requested one-time restoration run: publish each existing content category once. Latest AI repair + resilient news-only generator.
    outcomes = []
    for key, label in CATEGORIES:
        env = os.environ.copy()
        env["SCHEDULE_KEY"] = key
        env["ALLOW_REVIEWED_SILVER_PUBLICATION"] = "true"
        env["TELEGRAM_SILVER_CHANNEL_ID"] = "@FundBoard_Silver"
        sent = False
        output = ""
        for attempt in range(1, 3):
            try:
                result = subprocess.run(
                    [sys.executable, "publish_silver_scheduled_content.py"],
                    env=env, capture_output=True, text=True, timeout=300
                )
                output = (result.stdout or "") + (result.stderr or "")
                sent = ("Published " in output and result.returncode == 0
                        and "AI_REWRITTEN=true" in output
                        and "PERSIAN_ONLY_CHECK=passed" in output
                        and "BOLD_LINKED_FOOTER=true" in output
                        and "ERROR:" not in output)
            except subprocess.TimeoutExpired as exc:
                output = f"ERROR: category timed out on attempt {attempt}: {exc}"
                sent = False
            print(f"===== {label} [{key}] attempt={attempt} sent={sent} =====", flush=True)
            print(output[-5000:], flush=True)
            if sent or "Published " in output:
                sent = sent and "ERROR:" not in output
                break
            if attempt < 2:
                print(f"Retrying {key} once after a failed generation/quality check.", flush=True)
                time.sleep(12)
        outcomes.append((key, label, sent))
        time.sleep(4)  # avoid hitting AI and Telegram rate limits
    print("===== PUBLICATION SUMMARY =====")
    for key, label, sent in outcomes:
        print(f"{'SENT_AND_CHECKED' if sent else 'FAILED_OR_REJECTED'} | {key} | {label}", flush=True)
    if not all(item[2] for item in outcomes):
        raise RuntimeError("Some real silver content categories could not be published; see logs.")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
