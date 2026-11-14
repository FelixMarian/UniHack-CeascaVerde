import os
import secrets
import time
from collections import OrderedDict
from threading import Lock
from fastapi import FastAPI, HTTPException
from starlette.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from dotenv import load_dotenv
from .db import make_engine, sessions
from .legacy import LegacyGateway
from .routes import router
from .iot import router as iot_router
from .ultrasonic import router as ultrasonic_router
from .company import router as company_router
from .proofs import router as proofs_router
from .statistics import router as statistics_router


class LoginLimiter:
    """Small single-worker demo limiter. Use a shared limiter for multiple workers."""
    def __init__(self):
        self.attempts, self.lock = OrderedDict(), Lock()

    def check(self, key):
        with self.lock:
            now = time.monotonic()
            recent = [t for t in self.attempts.pop(key, []) if now - t < 60]
            self.attempts[key] = recent
            if len(recent) >= 10:
                raise HTTPException(429, 'Prea multe încercări. Așteaptă un minut.', headers={'Retry-After': '60'})
            recent.append(now)
            if len(self.attempts) > 10000:
                self.attempts.popitem(last=False)

    def clear(self, key):
        with self.lock:
            self.attempts.pop(key, None)


def install(app: FastAPI, *, engine=None, legacy=None, device_key=None):
    """Call once, AFTER the original routes in main.py. No writes during install."""
    load_dotenv()
    device_key = device_key if device_key is not None else os.environ['SMARTWASTE_API_KEY']
    if not device_key:
        raise ValueError('SMARTWASTE_API_KEY must not be empty')
    app.state.sw_sessions = sessions(engine if engine is not None else make_engine())
    app.state.sw_legacy = legacy or LegacyGateway(os.getenv('SMARTWASTE_LEGACY_URL', 'http://127.0.0.1:8000'), device_key)
    app.state.sw_limiter = LoginLimiter()
    app.state.sw_device_key = device_key
    app.include_router(router)
    app.include_router(iot_router)
    app.include_router(ultrasonic_router)
    app.include_router(company_router)
    app.include_router(proofs_router)
    app.include_router(statistics_router)

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request, exc):
        # Do not expose SQL, database URLs or bound parameters in client responses.
        return JSONResponse({'detail': 'Baza de date nu este disponibilă sau migrarea lipsește.'}, status_code=503)

    @app.middleware('http')
    async def legacy_read_boundary(request, call_next):
        # The legacy public read endpoints otherwise bypass all resident/company scoping.
        # Devices/services retain the same response contracts using their existing key.
        path = request.url.path.rstrip('/')
        if path == '/bins' or path == '/reports' or path.startswith('/reports/'):
            if not secrets.compare_digest(request.headers.get('X-API-Key', ''), device_key):
                return JSONResponse({'detail': 'Utilizează API-ul autentificat /api/v1.'}, status_code=401)
        response = await call_next(request)
        if path.startswith('/api/v1'):
            response.headers['Cache-Control'] = 'no-store'
        return response


def create_app():
    app = FastAPI(title='SmartWaste Mobile API', version='1.0.0')
    install(app)
    return app
