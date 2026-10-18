"""Publish the seven editorially cleaned Persian silver content categories once."""
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
    # Explicitly requested one-time restoration run: publish each existing content category once.
    outcomes = []
    for key, label in CATEGORIES:
        env = os.environ.copy()
        env["SCHEDULE_KEY"] = key
        env["ALLOW_REVIEWED_SILVER_PUBLICATION"] = "true"
        env["TELEGRAM_SILVER_CHANNEL_ID"] = "@FundBoard_Silver"
        result = subprocess.run(
            [sys.executable, "publish_silver_scheduled_content.py"],
            env=env, capture_output=True, text=True, timeout=240
        )
        output = (result.stdout or "") + (result.stderr or "")
        print(f"===== {label} [{key}] exit={result.returncode} =====")
        print(output[-5000:])
        sent = "Published " in output and result.returncode == 0
        outcomes.append((key, label, sent))
        time.sleep(3)
    print("===== PUBLICATION SUMMARY =====")
    for key, label, sent in outcomes:
        print(f"{'SENT' if sent else 'FAILED'} | {key} | {label}")
    if not all(item[2] for item in outcomes):
        raise RuntimeError("Some real silver content categories could not be published; see logs.")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
