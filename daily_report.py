import re
import sys
import json
import os
import gspread
import requests
from oauth2client.service_account import ServiceAccountCredentials

# ====== НАЛАШТУВАННЯ ======
TELEGRAM_TOKEN = "8559008270:AAHZxRvoPDLwf-py8nbyumhJKVoU9iIyzCI"
TELEGRAM_CHAT_IDS = [744774352]

GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/18e7vIVOlDj9lRLTN7lr2w6A9rH3SQAjKJi2Hz1u31aQ/edit?gid=0#gid=0"
WORKSHEET_NAME = "2026"
JSON_CREDENTIALS_PATH = "/Users/artemhudyma/meters_bot/fourth-outpost-446813-e4-08753ff229b2.json"

STATE_FILE = os.path.join(os.path.dirname(__file__), "state.json")

# ====== КОЛОНКИ (A=1) — ТВОЇ РЕАЛЬНІ З ЧАТУ ======
COL_DATE = 1  # A

COL_EL1_MORNING, COL_EL1_EVENING = 4, 6      # D, F
COL_EL2_MORNING, COL_EL2_EVENING = 9, 10     # I, J
COL_WATER_MORNING, COL_WATER_EVENING = 13, 14  # M, N
COL_WATER_PILOT_MORNING, COL_WATER_PILOT_EVENING = 18, 19  # R, S
COL_STOCK_PILOT_MORNING, COL_STOCK_PILOT_EVENING = 21, 22  # U, V

TARGET_DATE = sys.argv[1] if len(sys.argv) > 1 else None  # напр. 02.02.2026


def sheet_id_from_url(url: str) -> str:
    m = re.search(r"/d/([a-zA-Z0-9-_]+)", url)
    if not m:
        raise Exception("GOOGLE_SHEET_URL не містить /d/... Встав ПОВНЕ посилання на таблицю.")
    return m.group(1)

def cell(row, col):
    i = col - 1
    return row[i] if 0 <= i < len(row) else ""

def is_filled(v) -> bool:
    # "0" вважається заповненим
    return str(v).strip() != ""

def to_num(v) -> float:
    s = str(v).strip().replace(",", ".")
    if s == "":
        return 0.0
    try:
        return float(s)
    except:
        return 0.0

def diff(morning, evening) -> float:
    return round(to_num(evening) - to_num(morning), 2)

def fmt(x: float) -> str:
    s = f"{x:.2f}".rstrip("0").rstrip(".")
    if s == "":
        s = "0"
    return s.replace(".", ",")

def load_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def send_telegram(message_html: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    for chat_id in TELEGRAM_CHAT_IDS:
        r = requests.post(
            url,
            json={"chat_id": chat_id, "text": message_html, "parse_mode": "HTML"},
            timeout=20
        )
        print("Telegram status:", r.status_code, "chat_id:", chat_id)
        if r.status_code != 200:
            print(r.text)

def row_is_full(r) -> bool:
    pairs = [
        (COL_EL1_MORNING, COL_EL1_EVENING),
        (COL_EL2_MORNING, COL_EL2_EVENING),
        (COL_WATER_MORNING, COL_WATER_EVENING),
        (COL_WATER_PILOT_MORNING, COL_WATER_PILOT_EVENING),
        (COL_STOCK_PILOT_MORNING, COL_STOCK_PILOT_EVENING),
    ]
    if not is_filled(cell(r, COL_DATE)):
        return False
    for a, b in pairs:
        if not is_filled(cell(r, a)) or not is_filled(cell(r, b)):
            return False
    return True

def main():
    # Google auth
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name(JSON_CREDENTIALS_PATH, scope)
    gc = gspread.authorize(creds)

    ws = gc.open_by_key(sheet_id_from_url(GOOGLE_SHEET_URL)).worksheet(WORKSHEET_NAME)
    rows = ws.get_all_values()
    if len(rows) < 2:
        raise Exception("Таблиця пуста або тільки заголовок.")

    data = rows[1:]  # без заголовка
    state = load_state()
    last_sent = state.get("last_sent_date")

    # 1) Якщо передали дату — шукаємо ІМЕННО її і шлемо (ігноруємо last_sent)
    if TARGET_DATE:
        for r in data:
            if str(cell(r, COL_DATE)).strip() == TARGET_DATE:
                if not row_is_full(r):
                    raise Exception(f"Рядок {TARGET_DATE} знайдено, але він НЕ повний (немає всіх ран/веч).")
                date_str = TARGET_DATE
                el1 = diff(cell(r, COL_EL1_MORNING), cell(r, COL_EL1_EVENING))
                el2 = diff(cell(r, COL_EL2_MORNING), cell(r, COL_EL2_EVENING))
                water = diff(cell(r, COL_WATER_MORNING), cell(r, COL_WATER_EVENING))
                water_pilot = diff(cell(r, COL_WATER_PILOT_MORNING), cell(r, COL_WATER_PILOT_EVENING))
                stock_pilot = diff(cell(r, COL_STOCK_PILOT_MORNING), cell(r, COL_STOCK_PILOT_EVENING))

                report = (
                    f"📊 <b>Звіт по лічильниках</b>\n"
                    f"📅 <b>Дата:</b> {date_str}\n\n"
                    f"⚡ <b>Ел. лічильник 1:</b> {fmt(el1)}\n"
                    f"⚡ <b>Ел. лічильник 2:</b> {fmt(el2)}\n"
                    f"🚰 <b>Вода:</b> {fmt(water)}\n"
                    f"🚰 <b>Вода Pilot:</b> {fmt(water_pilot)}\n"
                    f"🛢 <b>Сток Pilot:</b> {fmt(stock_pilot)}"
                )
                send_telegram(report)
                print("✅ Sent for", date_str)
                return
        raise Exception(f"Не знайшов дату {TARGET_DATE} у колонці A.")

    # 2) Авто-режим: шлемо ПЕРШИЙ “повний” день після last_sent_date
    selected = None
    for r in data:
        if not row_is_full(r):
            continue
        date_str = str(cell(r, COL_DATE)).strip()
        if last_sent and date_str <= last_sent:
            continue
        selected = (date_str, r)
        break

    if not selected:
        print("ℹ️ Немає нового повного дня після last_sent_date. Нічого не відправляю.")
        return

    date_str, r = selected
    el1 = diff(cell(r, COL_EL1_MORNING), cell(r, COL_EL1_EVENING))
    el2 = diff(cell(r, COL_EL2_MORNING), cell(r, COL_EL2_EVENING))
    water = diff(cell(r, COL_WATER_MORNING), cell(r, COL_WATER_EVENING))
    water_pilot = diff(cell(r, COL_WATER_PILOT_MORNING), cell(r, COL_WATER_PILOT_EVENING))
    stock_pilot = diff(cell(r, COL_STOCK_PILOT_MORNING), cell(r, COL_STOCK_PILOT_EVENING))

    report = (
        f"📊 <b>Звіт по лічильниках</b>\n"
        f"📅 <b>Дата:</b> {date_str}\n\n"
        f"⚡ <b>Ел. лічильник 1:</b> {fmt(el1)}\n"
        f"⚡ <b>Ел. лічильник 2:</b> {fmt(el2)}\n"
        f"🚰 <b>Вода:</b> {fmt(water)}\n"
        f"🚰 <b>Вода Pilot:</b> {fmt(water_pilot)}\n"
        f"🛢 <b>Сток Pilot:</b> {fmt(stock_pilot)}"
    )

    send_telegram(report)
    state["last_sent_date"] = date_str
    save_state(state)
    print("✅ Sent and saved last_sent_date =", date_str)

if __name__ == "__main__":
    main()
