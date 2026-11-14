
import os
import json
import hashlib
import uuid

from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

DB_URL = os.environ["TIGER_DATABASE_URL"]
API_KEY = os.environ["SMARTWASTE_API_KEY"]

app = FastAPI(title="SmartWaste Server")

class Reading(BaseModel):
    bin_id: str
    fill_level: int = Field(ge=0, le=100)
    battery: int | None = Field(default=None, ge=0, le=100)

class CollectionInput(BaseModel):
    bin_id: str
    confirmed_by: str

def authorize(key):
    if key != API_KEY:
        raise HTTPException(401, "Invalid API key")

@app.get("/health")
def health():
    return {"status": "online", "service": "SmartWaste"}

@app.post("/readings")
def add_reading(
    reading: Reading,
    x_api_key: str = Header(default="")
):
    authorize(x_api_key)

    try:
        with psycopg.connect(DB_URL) as conn:
            conn.execute("""
                INSERT INTO bin_measurements
                    (bin_id, fill_level, battery)
                VALUES (%s, %s, %s)
            """, (
                reading.bin_id,
                reading.fill_level,
                reading.battery
            ))
    except psycopg.errors.ForeignKeyViolation:
        raise HTTPException(404, "Bin not registered")

    return {"saved": True, "bin_id": reading.bin_id}

@app.get("/bins")
def get_bins():
    with psycopg.connect(DB_URL) as conn:
        rows = conn.execute("""
            SELECT b.bin_id, m.fill_level, m.recorded_at
            FROM bins b
            LEFT JOIN LATERAL (
                SELECT fill_level, recorded_at
                FROM bin_measurements
                WHERE bin_id = b.bin_id
                ORDER BY recorded_at DESC
                LIMIT 1
            ) m ON TRUE
            ORDER BY b.bin_id
        """).fetchall()

    return [
        {
            "bin_id": row[0],
            "fill_level": row[1],
            "recorded_at": row[2]
        }
        for row in rows
    ]

@app.post("/collections")
def record_collection(
    data: CollectionInput,
    x_api_key: str = Header(default="")
):
    authorize(x_api_key)
    collection_id = uuid.uuid4()

    with psycopg.connect(DB_URL) as conn:
        conn.execute("""
            INSERT INTO collections
                (collection_id, bin_id, confirmed_by)
            VALUES (%s, %s, %s)
        """, (
            collection_id,
            data.bin_id,
            data.confirmed_by
        ))

    return {"collection_id": str(collection_id)}

@app.post("/reports/generate")
def generate_report(x_api_key: str = Header(default="")):
    authorize(x_api_key)

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=7)

    with psycopg.connect(DB_URL) as conn:
        readings = conn.execute("""
            SELECT bin_id,
                   COUNT(*),
                   ROUND(AVG(fill_level), 2),
                   MAX(fill_level)
            FROM bin_measurements
            WHERE recorded_at >= %s
              AND recorded_at < %s
            GROUP BY bin_id
            ORDER BY bin_id
        """, (start, end)).fetchall()

        collections = conn.execute("""
            SELECT COUNT(*)
            FROM collections
            WHERE collected_at >= %s
              AND collected_at < %s
        """, (start, end)).fetchone()[0]

        report_id = uuid.uuid4()

        report = {
            "report_id": str(report_id),
            "type": "weekly",
            "period_start": start.isoformat(),
            "period_end": end.isoformat(),
            "collections": collections,
            "bins": [
                {
                    "bin_id": row[0],
                    "measurements": row[1],
                    "average_fill": str(row[2]),
                    "maximum_fill": row[3]
                }
                for row in readings
            ]
        }

        canonical = json.dumps(
            report,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False
        )

        digest = hashlib.sha256(
            canonical.encode("utf-8")
        ).hexdigest()

        conn.execute("""
            INSERT INTO reports
                (report_id, report_type, content, sha256_hash)
            VALUES (%s, %s, %s::jsonb, %s)
        """, (report_id, "weekly", canonical, digest))

    return {
        "report_id": str(report_id),
        "report": report,
        "sha256": digest,
        "blockchain_status": "pending"
    }

@app.get("/reports/{report_id}")
def get_report(report_id: uuid.UUID):
    with psycopg.connect(DB_URL) as conn:
        row = conn.execute("""
            SELECT content, sha256_hash,
                   solana_signature, blockchain_status
            FROM reports
            WHERE report_id = %s
        """, (report_id,)).fetchone()

    if row is None:
        raise HTTPException(404, "Report not found")

    return {
        "report": row[0],
        "sha256": row[1],
        "solana_signature": row[2],
        "blockchain_status": row[3]
    }
