import os
import time
import json
import requests
import subprocess

TELEGRAM_TOKEN = "8559008270:AAHZxRvoPDLwf-py8nbyumhJKVoU9iIyzCI"
ALLOWED_CHAT_IDS = [744774352]  # твій chat_id

BASE_DIR = os.path.dirname(__file__)
SCRIPT = os.path.join(BASE_DIR, "daily_report.py")
OFFSET_FILE = os.path.join(BASE_DIR, "bot_offset.json")


def load_offset():
    try:
        with open(OFFSET_FILE, "r", encoding="utf-8") as f:
            return int(json.load(f).get("offset", 0))
    except:
        return 0


def save_offset(offset: int):
    with open(OFFSET_FILE, "w", encoding="utf-8") as f:
        json.dump({"offset": offset}, f)


def send(chat_id: int, text: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": chat_id, "text": text}, timeout=20)


def run_report(chat_id: int, date_str: str):
    # запускаємо твій daily_report.py з датою
    p = subprocess.run(
        ["/usr/bin/python3", SCRIPT, date_str],
        capture_output=True,
        text=True
    )
    if p.returncode == 0:
        send(chat_id, f"✅ Запит виконано: {date_str}")
    else:
        send(chat_id, f"❌ Помилка для {date_str}:\n{p.stderr[-800:]}")


def handle(chat_id: int, text: str):
    t = (text or "").strip()

    if t in ("/start", "/help"):
        send(chat_id,
             "✅ Бот працює.\n\nКоманди:\n"
             "/today — звіт за сьогодні\n"
             "/yesterday — звіт за вчора\n"
             "/date DD.MM.YYYY — звіт за дату (напр. /date 03.02.2026)"
        )
        return

    if t == "/today":
        # дата в форматі як у твоїй таблиці
        from datetime import date
        run_report(chat_id, date.today().strftime("%d.%m.%Y"))
        return

    if t == "/yesterday":
        from datetime import date, timedelta
        run_report(chat_id, (date.today() - timedelta(days=1)).strftime("%d.%m.%Y"))
        return

    if t.startswith("/date"):
        parts = t.split()
        if len(parts) != 2:
            send(chat_id, "❗ Формат: /date 03.02.2026")
            return
        run_report(chat_id, parts[1])
        return

    send(chat_id, "❓ Невідома команда. Напиши /help")


def main():
    print("🤖 Bot is running... (Ctrl+C to stop)")
    offset = load_offset()

    while True:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
        r = requests.get(url, params={"offset": offset, "timeout": 30}, timeout=35).json()

        for upd in r.get("result", []):
            offset = upd["update_id"] + 1
            save_offset(offset)

            msg = upd.get("message")
            if not msg:
                continue

            chat_id = msg["chat"]["id"]
            if chat_id not in ALLOWED_CHAT_IDS:
                continue

            handle(chat_id, msg.get("text", ""))

        time.sleep(1)


if __name__ == "__main__":
    main()
