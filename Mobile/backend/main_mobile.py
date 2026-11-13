"""Deployment entry point: uvicorn main_mobile:app --host 0.0.0.0 --port 8000.

The existing main.py stays intact beside this file. Its verified functions are
reused for sensor reads and collection writes; no second HTTP server is needed.
"""
import psycopg
from fastapi import HTTPException
from main import app, get_bins, record_collection, CollectionInput, API_KEY
from smartwaste.integration import install


class ExistingBackend:
    def readings(self):
        try:
            return {row['bin_id']: row for row in get_bins()}
        except psycopg.Error:
            raise HTTPException(503, 'Baza de date nu este disponibilă. Reîncearcă.') from None

    def collect(self, bin_id, username):
        try:
            return record_collection(CollectionInput(bin_id=bin_id, confirmed_by=username), x_api_key=API_KEY)
        except psycopg.errors.ForeignKeyViolation:
            raise HTTPException(404, 'Tomberonul nu mai există.') from None
        except psycopg.Error:
            raise HTTPException(503, 'Colectarea nu a putut fi confirmată. Verifică istoricul înainte de reîncercare.') from None


install(app, legacy=ExistingBackend())
