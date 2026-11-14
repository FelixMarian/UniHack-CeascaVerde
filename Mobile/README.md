# SmartWaste — UniHack 2026

**Update 1.2.0:** IP `10.247.174.231`, categorii 1–4 (inclusiv deteriorat), HQ pentru companii, GPS la cerere, generare ordine de colectare și dovezi Solana Devnet pentru sesizările locatarilor. Instalare și activare: [docs/UPDATE-1.2.0.md](docs/UPDATE-1.2.0.md). APK-ul necesită și actualizarea backend-ului. Validare curentă: 61 teste backend și 6 teste Android, build reușit, lint fără erori. Solana este testată local cu semnare reală și RPC simulat; activarea portofelului și verificarea pe telefon/Pi rămân pașii de instalare. Informațiile de mai jos descriu și livrările anterioare.

Aplicație Android nativă Kotlin/Compose și extensie modulară pentru backend-ul FastAPI existent. Toate ecranele folosesc API-ul; nu există un mod mock în APK. Android nu se conectează la PostgreSQL și nu conține cheia dispozitivelor.

**Stare livrare:** APK compilat, 10 teste backend (inclusiv PostgreSQL) și 4 teste Android trecute; fluxuri verificate în emulator. Extensia trebuie instalată pe Raspberry Pi înainte de login în APK-ul livrat. Harta necesită cheia Google Maps proprie. Vezi `docs/VALIDATION.md` pentru limitele exacte.

## Structură

Update trei ultrasonici: vezi `lora/ULTRASONIC_SETUP.md`. FastAPI clasifică distanțele în 1=Gol, 2=Mediu, 3=Plin prin `/iot/ultrasonic-readings`. Necesită migrarea aditivă `002_ultrasonic.sql`, calibrarea pragurilor `#define` și APK-ul 1.1.0. Teste locale: 51 backend/parser + 5 Android. Praguri laterale 5 cm; validare de sus 10 cm pentru Mediu și 5 cm pentru Plin. Instalarea acestui update pe Pi nu a fost efectuată (SSH indisponibil).

- `android/`: proiect Android Studio, Material 3, MVVM, Navigation Compose, Retrofit/OkHttp, Google Maps.
- `backend/smartwaste/`: autentificare, autorizare, servicii și API-uri noi.
- `backend/main_mobile.py`: punct de pornire care **importă fișierul original `main.py`**, fără a-l rescrie.
- `backend/migrations/001_mobile.sql`: migrare PostgreSQL aditivă și repetabilă.
- `backend/reference/existing_schema.sql`: schema furnizată, exclusiv pentru referință.
- `backend/tests/`: teste de integrare ale API-ului și izolării datelor.
- `docs/API.md`: contractul API și permisiunile.
- `docs/VALIDATION.md`: verificări efectuate și limitele lor.

## Instalare pe Raspberry Pi

Se presupune structura existentă `~/smartwaste/backend/main.py` și `~/smartwaste/.env`. Nu copia un alt `main.py` peste cel existent. Fișierul livrat `main_mobile.py` reutilizează funcțiile `get_bins` și `record_collection` din codul furnizat în conversație.

1. Fă un backup al proiectului și un snapshot/backup al bazei Tiger Cloud înainte de instalare. Păstrează mediul Python vechi pentru rollback.
2. Copiază în `~/smartwaste/backend/` directoarele `smartwaste/`, `migrations/`, fișierele `main_mobile.py`, `requirements.txt` și, opțional, testele/documentația. Nu copia `reference/existing_schema.sql` în procesul de migrare.
3. Pe Raspberry Pi (Python 3.11+):

```bash
cd ~/smartwaste/backend
python3 -m venv ../.venv-mobile
source ../.venv-mobile/bin/activate
pip install -r requirements.txt
python -m smartwaste.manage inspect > schema-before-mobile.json
```

`python-dotenv` citește `.env` din directorul proiectului sau părintele său. Păstrează `TIGER_DATABASE_URL` existent, inclusiv SSL, și `SMARTWASTE_API_KEY` existent. Nu transmite aceste valori telefonului. `SMARTWASTE_SESSION_HOURS=12` este opțional.

4. Compară inspecția cu schema furnizată. Trebuie să existe `bins`, `bin_measurements`, `collections`, `reports`, inclusiv `bins.bin_id`, `latitude`, `longitude`. Apoi:

```bash
python -m smartwaste.manage migrate
python -m smartwaste.manage seed
```

Migrarea folosește SQL-ul livrat, într-o tranzacție cu advisory lock. Creează `sw_users`, `sw_sessions`, `sw_resident_bins`, `sw_incidents`. Adaugă în `bins` numai `name`, `company_id`, `demo`. **Nu rescrie coordonatele, capacitatea, măsurătorile, colectările sau rapoartele existente. Nu șterge `BIN_001`.** Coloanele geografice existente sunt reutilizate.

Seed-ul nu schimbă parolele/asignările conturilor demo deja create. Creează două tomberoane `DEMO_BIN_001/002`, cu coordonate demonstrative în Timișoara, și le asignează. Nu introduce măsurători fictive: până la prima citire, acestea afișează „Fără date”. `BIN_001` devine vizibil Admin-ului și poate fi asignat explicit din aplicație. Seed-ul refuză coliziuni cu conturi sau tomberoane nedemonstrative.

5. Oprește instanța Uvicorn existentă care ocupă portul 8000 și pornește, din același director:

```bash
uvicorn main_mobile:app --host 0.0.0.0 --port 8000 --workers 1
```

Pentru systemd, schimbă **doar** executabilul/mediul virtual și ținta din `main:app` în `main_mobile:app`, păstrând utilizatorul, directorul de lucru și configurația serviciului existente. Nu porni două servere pe același port. Nu utiliza `--reload` la demonstrație.

### Compatibilitate și închiderea accesului public

`/health`, `/readings`, `/collections`, `/reports/generate` și `/reports/{id}` păstrează implementarea și formatele originale. POST-urile IoT folosesc în continuare `X-API-Key`.

**Schimbare de securitate necesară:** citirile legacy `/bins` și `/reports/{id}` necesită acum `X-API-Key`. Anterior, accesul anonim la acestea permitea oricărui locatar să ocolească filtrarea aplicației. Actualizează clienții serviciu care citeau anonim să trimită cheia existentă. Android folosește exclusiv tokenul de sesiune și `/api/v1/bins`. `/health` rămâne public. Nu există un mod care reactivează citirile anonime.

O confirmare de colectare folosește chiar funcția originală `record_collection`, cu `confirmed_by` derivat din contul autentificat. Nu resetează artificial măsurătoarea senzorului. Nu se fac retry-uri automate pentru scrieri; dacă legătura cade după confirmarea în DB, verifică istoricul înainte de retrimitere, deoarece endpoint-ul legacy nu oferă idempotency keys.

Rollback de aplicație: revino la mediul vechi și `main:app`. Datele originale rămân disponibile, coloanele noi au valori implicite pentru inserările legacy. Nu este nevoie să ștergi tabelele noi; un rollback la serverul vechi reactivează însă citirile publice vechi.

## Conturi demo

| Rol | Username | Parolă | Asignare inițială |
|---|---|---|---|
| Admin | `admin` | `admin` | Toate tomberoanele |
| Resident | `resident1` | `resident1` | `DEMO_BIN_001` |
| Resident | `resident2` | `resident2` | `DEMO_BIN_002` |
| Company | `company1` | `company1` | `DEMO_BIN_001` |
| Company | `company2` | `company2` | `DEMO_BIN_002` |

Acestea sunt exclusiv credențiale demonstrative. Parolele se stochează prin Argon2. În Profil poți schimba parola, inclusiv cea a Admin-ului; schimbarea revocă sesiunile. API-ul public nu creează roluri Admin, iar un index unic parțial permite un singur Admin în DB. În MVP, un cont Company reprezintă o companie; conturile multiple per companie nu sunt încă implementate.

## Android Studio și compilare

1. Deschide directorul `android/` în Android Studio. Folosește **JDK 17**, SDK Android 35 și acceptă licențele SDK. Gradle Wrapper este inclus.
2. Copiază proprietățile din `android/local.properties.example` în propriul `android/local.properties`; păstrează `sdk.dir` generat de IDE.
3. URL-ul implicit este `http://10.253.97.231:8000/`. Se configurează o singură dată prin `API_BASE_URL`, cu `/` final. Poate fi suprascris și prin `-PAPI_BASE_URL=https://api.example.com/`.
4. Pentru hartă, activează Google Maps SDK for Android în proiectul Google Cloud și adaugă `MAPS_API_KEY` în `local.properties`. Restricționează cheia la pachetul `ro.unihack.smartwaste` și SHA-1 al certificatului de semnare, apoi la Maps SDK for Android. Află SHA-1 cu `./gradlew :app:signingReport`. Configurația și eventualul billing sunt responsabilitatea proiectului Google Cloud. Fără cheie, aplicația funcționează și afișează un mesaj explicit în ecranul Hartă.
5. Compilează:

```bash
cd android
./gradlew :app:assembleDebug :app:testDebugUnitTest :app:lintDebug
```

Windows: `gradlew.bat` în loc de `./gradlew`. APK: `android/app/build/outputs/apk/debug/app-debug.apk`.

HTTP este permis numai în build-ul **debug**, pentru demonstrația LAN. Build-ul release refuză cleartext; configurează HTTPS și semnarea înainte de distribuție. Cheia Google Maps este un identificator client restricționat și va exista în APK conform SDK-ului; **nu** este cheia secretă `SMARTWASTE_API_KEY`, care nu intră în proiectul Android.

Tokenul aleator de sesiune este păstrat criptat AES-GCM, cu o cheie în Android Keystore. Backup-ul aplicației este dezactivat. Parolele nu sunt salvate local. Backend-ul păstrează numai SHA-256 al tokenului, expirarea și utilizatorul. Logout șterge local sesiunea chiar dacă serverul nu răspunde; aplicația anunță dacă revocarea de pe server nu a fost confirmată.

## Verificarea conexiunii și demonstrația

1. Pe telefon, deschide `http://10.253.97.231:8000/health`: trebuie să apară `status: online`. Telefonul trebuie să poată ruta către Pi; Wi-Fi guest/client isolation, VPN-ul și firewall-ul pot bloca legătura.
2. După instalarea extensiei, `http://10.253.97.231:8000/docs` trebuie să includă `/api/v1/auth/login`. Un 404 pe acest endpoint înseamnă că rulează încă backend-ul original.
3. Instalează APK-ul debug. Autentifică Admin, verifică existența `BIN_001`, editează numele/coordonatele dacă este necesar și asignează-l companiei și locatarului dorit.
4. Login `resident1`: verifică numai asignările sale, trimite un incident cu comentariu, apoi verifică „Sesizările mele”.
5. Login `resident2`: incidentul și tomberoanele celuilalt locatar nu trebuie să fie accesibile.
6. Login `company1`: verifică lista, markerul pe hartă (după configurarea cheii), detaliile, incidentul și schimbarea statusului. Confirmă o colectare doar după ce verifici că este o operație demo autorizată.
7. Login Admin: creează și dezactivează un cont, schimbă asignările. La refresh, conturile afectate trebuie să reflecte modificările; sesiunile conturilor editate sunt revocate.
8. Oprește temporar conexiunea telefonului și verifică mesajele de eroare. Nu se inserează date locale false.

Actualizarea este manuală prin „Actualizează”; nu rulează polling în fundal. Istoricul propriu de incidente rămâne vizibil Resident-ului chiar după retragerea asignării, dar nu mai poate trimite incidente noi pentru acel tomberon.

## Teste backend

```bash
cd backend
pip install -r requirements-dev.txt
python -m pytest -q
```

Testele rapide folosesc SQLite temporar și un adaptor de senzori de test, separat de aplicația livrată. Pentru testul de integrare PostgreSQL consultă `docs/VALIDATION.md`. Nu folosi baza de producție ca bază de teste.

## Limite înainte de utilizarea reală

MVP-ul folosește un singur worker și limitare locală a încercărilor de login (10/minut/username). Pentru mai mulți workeri folosește un limiter comun. Nu include recuperare parole prin e-mail, notificări push, WebSocket sau firmware ESP32. Receptorul LoRa și clasificarea sunt în directorul `lora/`; necesită calibrare și testare fizică. Nu oferă editarea username-ului/rolului după creare; Admin modifică numele, parola și starea activă, iar identitatea rămâne stabilă. Nu șterge fizic utilizatori sau tomberoane pentru a păstra relațiile istorice.

Referințe tehnice: [Compose Compiler](https://developer.android.com/develop/ui/compose/compiler), [Android Keystore](https://developer.android.com/privacy-and-security/keystore), [Maps Compose](https://github.com/googlemaps/android-maps-compose), [FastAPI password hashing](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/).
