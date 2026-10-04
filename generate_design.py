"""
Atölye Vakti — Script 2 (Parça 1): Canva Görsel Oluşturma

Airtable'daki "Atölyeler" tablosunda Durum = "Hazır" olan ve henüz
Canva Tasarım Linki boş olan satırları bulur, her biri için Canva
Autofill API'si üzerinden 2 sayfalı (kategori kapağı + detaylar)
tasarımı otomatik oluşturur, sonucu Airtable'a geri yazar.

Bu script'in henüz yapmadığı şeyler (sıradaki parçalarda eklenecek):
- Instagram'a otomatik yayınlama
- AI ile caption yazma
"""

import os
import sys
import time
import urllib.parse
import urllib.request
import json
from pyairtable import Api

AIRTABLE_TOKEN = os.environ["AIRTABLE_TOKEN"]
AIRTABLE_BASE_ID = os.environ["AIRTABLE_BASE_ID"]
WORKSHOPS_TABLE_NAME = os.environ.get("WORKSHOPS_TABLE_NAME", "Atölyeler")

CANVA_CLIENT_ID = os.environ["CANVA_CLIENT_ID"]
CANVA_CLIENT_SECRET = os.environ["CANVA_CLIENT_SECRET"]
CANVA_REFRESH_TOKEN = os.environ["CANVA_REFRESH_TOKEN"]
CANVA_TEMPLATE_ID = os.environ["CANVA_TEMPLATE_ID"]

CANVA_TOKEN_URL = "https://api.canva.com/rest/v1/oauth/token"
CANVA_AUTOFILL_URL = "https://api.canva.com/rest/v1/autofills"

POLL_INTERVAL_SECONDS = 3
MAX_POLL_ATTEMPTS = 20


def get_canva_access_token():
    """Refresh token'ı kullanarak taze bir access token alır."""
    data = urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "refresh_token": CANVA_REFRESH_TOKEN,
        "client_id": CANVA_CLIENT_ID,
        "client_secret": CANVA_CLIENT_SECRET,
    }).encode("ascii")

    req = urllib.request.Request(CANVA_TOKEN_URL, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")

    with urllib.request.urlopen(req) as response:
        result = json.loads(response.read().decode("utf-8"))
    return result["access_token"]


def fetch_ready_workshops(table):
    """Durum='Hazır' ve Canva linki boş olan satırları çeker."""
    all_records = table.all()
    ready = []
    for record in all_records:
        fields = record["fields"]
        if fields.get("Durum") == "Hazır" and not fields.get("Canva Tasarım Linki"):
            ready.append(record)
    return ready


def build_autofill_data(fields):
    """Airtable alanlarını Canva'nın beklediği veri alanlarına eşler."""
    return {
        "atolye_adi": {"type": "text", "text": fields.get("Atölye Adı", "")},
        "tarih": {"type": "text", "text": fields.get("Tarih", "")},
        "fiyat": {"type": "text", "text": f"{fields.get('Fiyat', '')} TL" if fields.get("Fiyat") else ""},
        "organizator": {"type": "text", "text": (fields.get("Organizatör Adı") or [""])[0]},
        "link": {"type": "text", "text": fields.get("Bilet Linki", "")},
    }


def create_autofill_job(access_token, data):
    payload = json.dumps({
        "brand_template_id": CANVA_TEMPLATE_ID,
        "data": data,
    }).encode("utf-8")

    req = urllib.request.Request(CANVA_AUTOFILL_URL, data=payload, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {access_token}")

    with urllib.request.urlopen(req) as response:
        result = json.loads(response.read().decode("utf-8"))
    return result["job"]["id"]


def poll_autofill_job(access_token, job_id):
    url = f"{CANVA_AUTOFILL_URL}/{job_id}"
    for attempt in range(MAX_POLL_ATTEMPTS):
        req = urllib.request.Request(url, method="GET")
        req.add_header("Authorization", f"Bearer {access_token}")
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode("utf-8"))

        status = result["job"]["status"]
        if status == "success":
            return result["job"]["result"]["design"]
        if status == "failed":
            error = result["job"].get("error", {})
            raise RuntimeError(f"Canva autofill başarısız: {error}")

        time.sleep(POLL_INTERVAL_SECONDS)

    raise TimeoutError("Canva autofill zaman aşımına uğradı (çok uzun sürdü).")


def main():
    api = Api(AIRTABLE_TOKEN)
    table = api.table(AIRTABLE_BASE_ID, WORKSHOPS_TABLE_NAME)

    ready_workshops = fetch_ready_workshops(table)
    if not ready_workshops:
        print("İşlenecek yeni atölye yok (Durum='Hazır' ve linki boş olan satır bulunamadı).")
        sys.exit(0)

    access_token = get_canva_access_token()
    print(f"{len(ready_workshops)} atölye bulundu, işleniyor...")

    for record in ready_workshops:
        fields = record["fields"]
        name = fields.get("Atölye Adı", "(isimsiz)")
        print(f"→ İşleniyor: {name}")

        data = build_autofill_data(fields)
        job_id = create_autofill_job(access_token, data)
        design = poll_autofill_job(access_token, job_id)

        design_url = design["urls"]["view_url"]
        table.update(record["id"], {"Canva Tasarım Linki": design_url})
        print(f"  ✓ Tasarım oluşturuldu: {design_url}")

    print("\nTamamlandı.")


if __name__ == "__main__":
    main()
