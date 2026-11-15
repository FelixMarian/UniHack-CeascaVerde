"""Keep radio reception independent of HTTP and retain pending packets across restarts."""
import json
import sqlite3
import threading

import requests


class Outbox:
    def __init__(self, path, url, key):
        self.path, self.url, self.key = path, url, key
        self.stop = threading.Event()
        self.writer = sqlite3.connect(path)
        self.writer.execute("PRAGMA journal_mode=WAL")
        self.writer.execute("CREATE TABLE IF NOT EXISTS pending (id INTEGER PRIMARY KEY, payload TEXT NOT NULL)")
        self.writer.commit()
        self.worker = threading.Thread(target=self.deliver, daemon=True)
        self.worker.start()

    def enqueue(self, reading):
        with self.writer:
            self.writer.execute("INSERT INTO pending(payload) VALUES (?)", (json.dumps(reading),))

    def deliver(self):
        connection = sqlite3.connect(self.path)
        delay = 1
        try:
            with requests.Session() as http:
                while not self.stop.is_set():
                    row = connection.execute("SELECT id,payload FROM pending ORDER BY id LIMIT 1").fetchone()
                    if row is None:
                        self.stop.wait(.25)
                        continue
                    reading = json.loads(row[1])
                    try:
                        response = http.post(self.url, json=reading, headers={"x-api-key": self.key},
                                             timeout=(3, 5), allow_redirects=False)
                        if response.status_code == 200:
                            result = response.json()
                            print(f"{reading['bin_id']}: {result.get('previous_category')} → "
                                  f"{result['fill_category']} ({result['reason']})", flush=True)
                        elif response.status_code in (400, 404, 422):
                            print(f"{reading['bin_id']}: pachet respins ({response.status_code}) "
                                  f"{response.text[:300]}", flush=True)
                        else:
                            raise ValueError(f"HTTP {response.status_code}")
                    except (requests.RequestException, ValueError, KeyError, TypeError) as error:
                        print(f"{reading['bin_id']}: pachet păstrat; reîncerc în {delay}s ({error})", flush=True)
                        self.stop.wait(delay)
                        delay = min(delay * 2, 30)
                        continue
                    with connection:
                        connection.execute("DELETE FROM pending WHERE id=?", (row[0],))
                    delay = 1
        finally:
            connection.close()

    def close(self):
        self.stop.set()
        self.worker.join(timeout=9)
        self.writer.close()
