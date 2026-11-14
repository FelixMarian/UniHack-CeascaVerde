
import os
import psycopg
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = "postgres://tsdbadmin:kq8cdcq9ejyczba2@vfqrd6dfos.v0oqpmdk7f.tsdb.cloud.timescale.com:31750/tsdb?sslmode=require"

with psycopg.connect(DATABASE_URL) as conn:
    result = conn.execute(
        "SELECT NOW()"
    ).fetchone()

    print("TigerData connected!")
    print("Database time:", result[0])

