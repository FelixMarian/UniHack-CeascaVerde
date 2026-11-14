# Validare — 13 noiembrie 2026

## Update ulterior: clasificare cu trei ultrasonici

51 teste backend/parser trecute, inclusiv migrare aditivă și tranzacții pe PostgreSQL local; 5 teste Android trecute, APK 1.1.0 compilat, Android Lint 0 erori / 9 avertismente. Testele acoperă categorii 1/2/3, contradicții, praguri necalibrate, coordonate, restart, cereri simultane și păstrarea procentelor anterioare. Raportul specific și instrucțiunile sunt în pachetul `SmartWaste-Ultrasonic-update.zip` și `lora/ULTRASONIC_SETUP.md`.

Accesul SSH la Pi a expirat; acest update nu a fost instalat acolo. Pragurile au fost confirmate de utilizator: laterali 5 cm, validare de sus 10 cm pentru Mediu și 5 cm pentru Plin; sunt configurate în fișierul .h. Nu s-a efectuat test fizic LoRa sau calibrare. Dovezile de emulator din secțiunile următoare aparțin versiunii anterioare cu procente, nu sunt o validare fizică a acestei clasificări.

## Rezultat și distincția dintre medii

Codul Android și extensia backend sunt implementate și au fost verificate împreună pe **emulator Android → FastAPI local → PostgreSQL local**. Nu sunt doar mockup-uri. Nu am instalat extensia pe Raspberry Pi și nu am modificat Tiger Cloud. Acceptarea completă pe infrastructura reală rămâne condiționată de instalare, configurarea Maps și testarea pe telefon.

### Serverul Raspberry Pi — verificare live, numai citire

La `http://10.253.97.231:8000`:

- `GET /health`: 200, `{"status":"online","service":"SmartWaste"}`.
- `GET /bins`: 200; `BIN_001`, nivel 85%, moment `2026-11-13T15:30:20.025501+00:00`.
- `GET /openapi.json`: citit pentru verificarea contractelor Reading și CollectionInput.
- Sursa `main.py` și schema au fost furnizate ulterior de utilizator; nu s-a pretins acces SSH sau acces direct la DB.

Nu s-au trimis măsurători, colectări, incidente sau migrații către serverul real.

### Backend local

**10 teste trecute**, Python 3.14.3, dependențele directe fixate în requirements. Nouă teste API folosesc SQLite temporar; al zecelea folosește PostgreSQL 16.4 real și o schemă izolată, creată și eliminată numai pentru test.

Testul PostgreSQL execută schema furnizată fără clauza Timescale hypertable, aplică SQL-ul de migrare de două ori și seed-ul de două ori, apoi încarcă copia funcțională a backend-ului furnizat împreună cu `main_mobile.py`.

Verificat:

- Login Admin, Resident, Company; hash Argon2 și sesiuni stocate numai prin hash.
- Respingerea accesului la tomberoane și incidente neasignate.
- Resident nu poate modifica statusuri sau confirma colectări.
- Company nu poate confirma colectarea tomberonului altei companii.
- Admin creează conturi și tomberoane, modifică asignări; acestea se reflectă la citire.
- Conturile dezactivate și token-urile revocate/expirate nu mai sunt acceptate.
- Schimbarea parolei și logout revocă sesiuni; unicitatea Admin este impusă în DB.
- Comentariile goale, coordonatele invalide, rolul Admin la creare și ID-urile duplicate sunt respinse.
- Migrarea și seed-ul păstrează măsurătoarea 85%, bateria 99 și capacitatea originală a unui `BIN_001` din fixture.
- Incidente, statusuri și colectări sunt scrise și recitite din PostgreSQL.
- Endpoint-urile originale `/health`, `/bins`, `/readings`, `/collections`, `/reports/generate`, `/reports/{id}` funcționează împreună cu extensia; citirile legacy sunt acum protejate prin cheia de serviciu.

**Nu a fost testată extensia TimescaleDB propriu-zisă sau Tiger Cloud.** Migrarea nu schimbă tabela de măsurători/hypertable; verificarea acestei compatibilități pe infrastructura reală rămâne un pas de instalare.

Comandă reproductibilă (numai pe o bază de test unde utilizatorul poate crea o schemă):

```bash
export SMARTWASTE_TEST_DATABASE_URL='postgresql://TEST_USER:TEST_PASSWORD@127.0.0.1:5432/TEST_DB'
python -m pytest -c backend/pytest.ini backend/tests -q
```

În PowerShell folosește `$env:SMARTWASTE_TEST_DATABASE_URL='...'`. Fără această variabilă, testul PostgreSQL este marcat skipped, nu passed. Schema testului are prefix `sw_test_` și UUID aleator; nu se folosesc tabelele existente din `public`.

### Android

- Compilare efectivă `:app:assembleDebug`: reușită, AGP 8.9.2 / Gradle 8.13 / Kotlin 2.1.20 / JDK 17.
- **4 teste JVM trecute**: pragurile 59/60/79/80 și null, navigarea pe roluri, contractul Retrofit/Bearer/fără X-API-Key, acceptarea răspunsurilor 204 la logout și schimbarea parolei.
- Android Lint: **0 erori, 9 avertismente**. Avertismentele rămase privesc target SDK 35, versiuni mai noi disponibile și preferința stilistică pentru KTX; rezultatul exact este în raportul livrat.
- Gradle Wrapper inclus, cu SHA-256 oficial al distribuției.
- APK-ul livrat este debug și configurat pentru `http://10.253.97.231:8000/`. Nu conține cheia serviciului sau stringul PostgreSQL.
- Cu APK-ul final, emulatorul nu a putut ruta către Pi și a afișat mesajul de conexiune inteligibil, fără crash. Accesul HTTP la Pi a fost confirmat de pe calculator, nu din emulator. Fluxul complet din emulator a fost verificat separat către serverul local de test.

### Emulator

AVD `Medium_Phone_API_36.1`, fără telefon fizic conectat. Pentru test s-a folosit o compilare separată cu URL `http://10.0.2.2:18000/` și un backend local cu o schemă `sw_emulator_<UUID>`. Valorile demonstrative de 85% și 45% au existat numai în această bază locală, nu în APK sau Tiger Cloud.

Verificat prin interfața instalată:

- Login Resident, dashboard cu nivelul primit din API și data măsurătorii.
- Selectare tomberon, creare sesizare, afișare în istoricul propriu.
- Login Company, preluarea aceleiași sesizări, schimbarea în „Rezolvată”.
- Resident vede noul status după autentificare/refresh.
- Login Admin, creare cont Resident din formular și persistență în PostgreSQL.
- Restaurarea sesiunii după repornirea aplicației.
- Logout revocă sesiunea pe server (204), șterge sesiunea locală și revine la login.
- Fără cheia Google Maps, ecranul Hartă explică explicit configurația lipsă, fără a încerca încărcarea SDK-ului.

Capturile din `docs/previews/` provin din aplicația rulată pe emulator și folosesc datele bazei locale de test. Nu reprezintă validare vizuală a hărții cu o cheie Google Maps reală. Un mesaj tranzitoriu de revocare neconfirmată a apărut în testarea inițială; retestarea a confirmat cererea 204 și eliminarea mesajului.

## Funcționalități rămase / acceptare pe infrastructura reală

1. Copierea extensiei pe Pi, migrarea și seed-ul în Tiger Cloud, pornirea `main_mobile:app`.
2. Adăugarea unei chei Google Maps restricționate și testarea markerelor interactive cu servicii Google disponibile.
3. Verificarea pe telefon real în rețeaua Pi, pentru toate rolurile și scrierile autorizate.
4. Schimbarea parolelor demo; pentru utilizare reală, HTTPS și build release semnat.

APK-ul pentru Pi nu poate autentifica utilizatori cât timp serverul rulează numai backend-ul original, fără endpoint-urile `/api/v1`. Nu declarăm integrarea Pi/Tiger Cloud complet verificată înainte de acești pași.
