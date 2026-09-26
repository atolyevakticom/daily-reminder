"""
Atölye Vakti — Günlük Hesap Kontrol Hatırlatıcısı

Bu script her gün çalışır, Airtable'daki "Hedef Hesaplar" tablosundan
en uzun süredir kontrol edilmemiş 5 hesabı seçer ve Telegram üzerinden
size bir hatırlatma mesajı gönderir.

Instagram'a HİÇBİR şekilde bağlanmaz, hiçbir hesabı takip etmez veya
içerik çekmez — sadece kendi Airtable verinizi okur ve size mesaj atar.
"""

import os
import sys
from datetime import date
from pyairtable import Api
import requests

# ---- Ortam değişkenlerinden ayarları oku (GitHub Secrets'tan gelecek) ----
AIRTABLE_TOKEN = os.environ["AIRTABLE_TOKEN"]
AIRTABLE_BASE_ID = os.environ["AIRTABLE_BASE_ID"]
TARGET_TABLE_NAME = os.environ.get("TARGET_TABLE_NAME", "Hedef Hesaplar")
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

NUMBER_OF_ACCOUNTS_TO_PICK = 5
NEVER_CHECKED_PRIORITY = 99999  # hiç kontrol edilmemiş hesapları en öne al


def fetch_target_accounts():
    """Hedef Hesaplar tablosundaki aktif tüm satırları çeker."""
    api = Api(AIRTABLE_TOKEN)
    table = api.table(AIRTABLE_BASE_ID, TARGET_TABLE_NAME)
    all_records = table.all()

    active_accounts = []
    for record in all_records:
        fields = record["fields"]
        is_active = fields.get("Aktif mi", True)  # checkbox yoksa aktif say
        if not is_active:
            continue
        active_accounts.append({
            "record_id": record["id"],
            "username": fields.get("Kullanıcı Adı", "").lstrip("@"),
            "category": fields.get("Kategori", ""),
            "days_since_check": fields.get("Gün Sayısı", NEVER_CHECKED_PRIORITY),
        })
    return active_accounts


def pick_least_recently_checked(accounts, count):
    """Gün Sayısı en yüksek olan (= en uzun süredir kontrol edilmeyen) hesapları seçer."""
    sorted_accounts = sorted(
        accounts, key=lambda a: a["days_since_check"], reverse=True
    )
    return sorted_accounts[:count]


def build_message(accounts):
    today_str = date.today().strftime("%d.%m.%Y")
    lines = [f"📋 *Bugünün kontrol listesi* — {today_str}", ""]
    for acc in accounts:
        category_part = f" ({acc['category']})" if acc["category"] else ""
        lines.append(f"• @{acc['username']}{category_part}")
    lines.append("")
    lines.append("Kontrol ettikten sonra Hedef Hesaplar tablosunda 'Son Kontrol' "
                  "tarihini bugüne güncellemeyi unutma.")
    return "\n".join(lines)


def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    response = requests.post(url, json={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
    }, timeout=15)
    response.raise_for_status()


def main():
    accounts = fetch_target_accounts()
    if not accounts:
        print("Hedef Hesaplar tablosunda aktif hesap bulunamadı.")
        sys.exit(0)

    selected = pick_least_recently_checked(accounts, NUMBER_OF_ACCOUNTS_TO_PICK)
    message = build_message(selected)
    send_telegram_message(message)
    print(f"Gönderildi: {[a['username'] for a in selected]}")


if __name__ == "__main__":
    main()
