"""Use verified existing HTTP contracts, never guess measurement/collection SQL."""
import httpx
from fastapi import HTTPException


class LegacyGateway:
    def __init__(self, url, api_key):
        self.url, self.api_key = url.rstrip('/'), api_key

    def request(self, method, path, **kwargs):
        try:
            response = httpx.request(method, self.url + path,
                headers={'X-API-Key': self.api_key}, timeout=10, **kwargs)
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError):
            raise HTTPException(502, 'Serviciul de senzori nu răspunde. Reîncearcă mai târziu.') from None

    def readings(self):
        data = self.request('GET', '/bins')
        if not isinstance(data, list) or any(not isinstance(b, dict) or 'bin_id' not in b for b in data):
            raise HTTPException(502, 'Format incompatibil pentru datele senzorilor.')
        return {b['bin_id']: b for b in data}

    def collect(self, bin_id, username):
        # confirmed_by is derived from the authenticated identity, never supplied by the client.
        return self.request('POST', '/collections', json={'bin_id': bin_id, 'confirmed_by': username})
