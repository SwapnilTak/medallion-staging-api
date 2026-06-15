"""
Python Data Generator
---------------------
Generates mock records every 50 minutes and POSTs them
to the FastAPI staging API on Render.
"""

import time
import uuid
import random
import requests
from datetime import datetime

# ── Config ────────────────────────────────────────────────────────────────────
STAGING_API_URL = "https://YOUR-APP-NAME.onrender.com"   # ← replace after deploy
API_KEY         = "change-me-in-render-env"               # ← must match Render env var
BATCH_INTERVAL  = 50 * 60                                 # 50 minutes in seconds
RECORDS_PER_BATCH = 100


# ── Mock record generator ─────────────────────────────────────────────────────
DEPARTMENTS  = ["Engineering", "Sales", "HR", "Finance", "Marketing"]
STATUSES     = ["active", "inactive", "pending"]

def generate_record() -> dict:
    return {
        "id": str(uuid.uuid4()),
        "payload": {
            "employee_id": random.randint(1000, 9999),
            "name": f"Employee_{random.randint(1, 500)}",
            "department": random.choice(DEPARTMENTS),
            "salary": round(random.uniform(40000, 120000), 2),
            "status": random.choice(STATUSES),
            "joining_date": f"202{random.randint(0,4)}-{random.randint(1,12):02d}-{random.randint(1,28):02d}",
        },
        "generated_at": datetime.utcnow().isoformat(),
    }


def generate_batch(n: int = RECORDS_PER_BATCH) -> list:
    return [generate_record() for _ in range(n)]


# ── Push to staging API ───────────────────────────────────────────────────────
def push_batch(records: list) -> dict:
    payload = {
        "source": "python-generator-v1",
        "records": records,
    }
    headers = {
        "Content-Type": "application/json",
        "x-api-key": API_KEY,
    }
    response = requests.post(
        f"{STAGING_API_URL}/batches",
        json=payload,
        headers=headers,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


# ── Main loop ─────────────────────────────────────────────────────────────────
def main():
    print(f"[Generator] Starting — pushing {RECORDS_PER_BATCH} records every 50 minutes")
    print(f"[Generator] Target API: {STAGING_API_URL}")

    while True:
        try:
            print(f"\n[{datetime.utcnow().isoformat()}] Generating batch...")
            records = generate_batch()

            print(f"[Generator] Pushing {len(records)} records to staging API...")
            result = push_batch(records)

            print(f"[Generator] ✅ Success — batch_id: {result['batch_id']} | "
                  f"records: {result['record_count']} | status: {result['status']}")

        except requests.exceptions.RequestException as e:
            print(f"[Generator] ❌ Push failed: {e}")
        except Exception as e:
            print(f"[Generator] ❌ Unexpected error: {e}")

        print(f"[Generator] Sleeping for 50 minutes...")
        time.sleep(BATCH_INTERVAL)


if __name__ == "__main__":
    main()
