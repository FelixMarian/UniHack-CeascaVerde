# API mobil v1

## Extensii 1.2.0

Toate endpoint-urile de mai jos cer Bearer și verifică rolul/asignarea în baza de date.

| Metodă | Rută | Contract |
|---|---|---|
| PUT | `/api/v1/companies/{id}/hq` | Company proprie / Admin; `{latitude, longitude}` ambele numere valide sau ambele null |
| PATCH | `/api/v1/bins/{id}/damage` | Doar Company responsabilă; `{damaged: true/false}` |
| POST | `/api/v1/company/route` | Doar Company; HQ obligatoriu; returnează HQ, `stops`, `straight_line_meters`, `skipped_bin_ids` |
| POST | `/api/v1/incidents/{id}/proof` | Autor Resident / Company responsabilă / Admin; pregătește dovada lipsă și verifică Solana Devnet |

`/auth/me`, login și lista de utilizatori includ `hq_latitude`, `hq_longitude` nullable.
`/bins.fill_category` poate fi 4 când `bins.is_damaged` este activ; altfel se păstrează clasificarea ultrasonică 1–3 / fallback legacy.
Starea deteriorată nu este modificată de ingestia IoT. Confirmarea colectării și actualizarea statusului sesizării sunt rezervate Company.
Ruta este ordine aproximativă a opririlor cu întoarcere la HQ, fără rutare pe străzi. Include numai tomberoanele pline proprii și exclude deterioratele.
Răspunsul dovezii conține `sha256`, `signature`, `network: devnet`, `status`, `explorer_url`. Statusuri: `prepared`, `pending`, `verified`, `invalid`, `content_changed`, `unavailable`.
Doar `verified` implică o tranzacție finalizată fără erori și Memo cu hash exact. Publicarea este realizată separat de `smartwaste.solana_worker`, nu de telefon.

Prefix: `/api/v1`. JSON UTF-8. Cu excepția login-ului, toate cererile necesită `Authorization: Bearer <access_token>`. Tokenul este opac, aleator și revocabil; nu este cheia dispozitivelor. Rolurile și activarea se citesc din DB la fiecare cerere.

Extensie IoT separată: `POST /iot/readings`, autentificată prin `X-API-Key`, primește `bin_id`, `latitude`, `longitude`, `fill_level`, opțional `battery`. Compară cu ultima stare din PostgreSQL și scrie numai schimbările. Vezi `lora/README.md` pentru formatul radio, instalare și semantica timpului ultimei schimbări. `/readings` original rămâne disponibil cu comportamentul său anterior.

Noul protocol cu trei senzori: `POST /iot/ultrasonic-readings`, tot cu `X-API-Key`, primește `bin_id`, `latitude`, `longitude`, `distance_mid_cm`, `distance_full_cm`, `distance_top_cm`, opțional `battery`. Calculează `fill_category` (1=Gol, 2=Mediu, 3=Plin). 503 înseamnă și calibrare lipsă/invalidă; 422 poate indica senzori contradictorii. Nicio stare nu se modifică în aceste cazuri. Detalii în `lora/ULTRASONIC_SETUP.md`.

Pentru coșurile cu o clasificare ultrasonică validă, `/api/v1/bins` returnează `fill_category` numeric și `fill_level: null`; nu sunt procente. Data și bateria provin din ultima stare categorică salvată. Pentru celelalte coșuri `fill_category` este null și procentul legacy rămâne disponibil. Clientul trebuie actualizat la APK 1.1.0 pentru afișarea categoriilor.

| Metodă | Rută | Acces / efect |
|---|---|---|
| POST | `/auth/login` | `{username,password}` → `{access_token,token_type,expires_at,user}` |
| GET | `/auth/me` | Identitatea curentă, fără hash/parolă |
| POST | `/auth/logout` | Revocă tokenul curent, 204 |
| POST | `/auth/password` | `{current_password,new_password}`, revocă toate sesiunile, 204 |
| GET | `/bins` | Resident: asignările proprii; Company: compania proprie; Admin: toate |
| POST | `/bins/{bin_id}/collections` | Company responsabilă; scrie prin implementarea legacy |
| GET | `/incidents` | Resident: incidentele proprii; Company: incidentele tomberoanelor sale; Admin: toate |
| POST | `/incidents` | Doar Resident, pentru un tomberon asignat, 201 |
| PATCH | `/incidents/{id}` | `{status}`; Company responsabilă |
| GET | `/admin/users` | Admin, toate conturile fără parole |
| POST | `/admin/users` | Admin; creează doar Resident/Company, 201 |
| PUT | `/admin/users/{id}` | Admin; nume, activare și parolă opțională; revocă sesiunile contului |
| POST | `/admin/bins` | Admin; înregistrează în tabela existentă `bins`, 201 |
| PUT | `/admin/bins/{bin_id}` | Admin; nume, coordonate, companie; ID imuabil |
| GET | `/admin/users/{id}/bins` | Admin; lista ID-urilor asignate unui Resident |
| PUT | `/admin/users/{id}/bins` | Admin; înlocuiește atomic lista completă, deduplicată |

## Formate

Bin:

```json
{"bin_id":"BIN_001","name":"Tomberon","latitude":45.748,"longitude":21.208,"company_id":4,"demo":false,"fill_level":85,"recorded_at":"2026-11-13T15:30:20.025501+00:00","battery":null}
```

`fill_level` și `recorded_at` pot fi `null`. Bateria rămâne `null` dacă endpoint-ul legacy nu o furnizează. Cele două coordonate trebuie furnizate împreună sau ambele `null`. Nicio valoare fictivă nu este substituită măsurătorilor lipsă.

Creare utilizator:

```json
{"username":"locatar_nou","password":"demo-pass-123","display_name":"Locatar Demo","role":"Resident"}
```

Editare: `{"display_name":"Nume nou","active":true,"password":null}`. Parola nouă are 8–128 caractere. Username-ul are 3–80 caractere alfanumerice, `_`, `.` sau `-`. Admin-ul nu se editează/dezactivează prin această rută; schimbarea parolei este disponibilă în profil.

Creare/editare tomberon:

```json
{"bin_id":"BIN_002","name":"Intrarea principală","latitude":45.748,"longitude":21.208,"company_id":4}
```

`company_id: null` retrage compania. ID-urile companiei sunt ID-uri de utilizatori cu rol Company activ. Capacitatea, data înregistrării și măsurătorile existente nu sunt rescrise de editarea metadatelor.

Asignare Resident: `{"bin_ids":["BIN_001","BIN_002"]}`. Lista goală retrage toate asignările. O listă cu ID inexistent este respinsă integral.

Creare incident:

```json
{"bin_id":"BIN_001","category":"damaged","comment":"Capacul este rupt."}
```

Categorii: `damaged`, `overflow`, `missed_collection`, `other`. Comentariu obligatoriu, 1–2000 caractere după eliminarea spațiilor marginale. Autorul, timpul și statusul inițial `open` sunt stabilite de server. Stări: `open`, `in_progress`, `resolved`. Compania responsabilă poate trece între aceste stări.

## Erori și securitate

- 401: autentificare incorectă, token absent/expirat/revocat sau cont inactiv.
- 403: rol neautorizat.
- 404: resursă inexistentă sau neasignată; nu dezvăluie apartenența altuia.
- 409: cont/ID duplicat sau conflict de relații.
- 422: format invalid ori companie/locatar nevalid.
- 429: prea multe încercări de autentificare, `Retry-After: 60`.
- 502/503: serviciul legacy sau baza de date indisponibilă.

Răspunsurile `/api/v1` folosesc `Cache-Control: no-store`. Nu există token-uri în URL-uri, logare HTTP a credențialelor sau returnare a hash-urilor parolelor. Definiția OpenAPI completă, generată de FastAPI, este disponibilă în `/docs` după instalare.
