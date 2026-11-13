# API mobil v1

Prefix: `/api/v1`. JSON UTF-8. Cu excepția login-ului, toate cererile necesită `Authorization: Bearer <access_token>`. Tokenul este opac, aleator și revocabil; nu este cheia dispozitivelor. Rolurile și activarea se citesc din DB la fiecare cerere.

| Metodă | Rută | Acces / efect |
|---|---|---|
| POST | `/auth/login` | `{username,password}` → `{access_token,token_type,expires_at,user}` |
| GET | `/auth/me` | Identitatea curentă, fără hash/parolă |
| POST | `/auth/logout` | Revocă tokenul curent, 204 |
| POST | `/auth/password` | `{current_password,new_password}`, revocă toate sesiunile, 204 |
| GET | `/bins` | Resident: asignările proprii; Company: compania proprie; Admin: toate |
| POST | `/bins/{bin_id}/collections` | Company responsabilă sau Admin; scrie prin implementarea legacy |
| GET | `/incidents` | Resident: incidentele proprii; Company: incidentele tomberoanelor sale; Admin: toate |
| POST | `/incidents` | Doar Resident, pentru un tomberon asignat, 201 |
| PATCH | `/incidents/{id}` | `{status}`; Company responsabilă/Admin |
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

Categorii: `damaged`, `overflow`, `missed_collection`, `other`. Comentariu obligatoriu, 1–2000 caractere după eliminarea spațiilor marginale. Autorul, timpul și statusul inițial `open` sunt stabilite de server. Stări: `open`, `in_progress`, `resolved`. Company/Admin poate trece între aceste stări.

## Erori și securitate

- 401: autentificare incorectă, token absent/expirat/revocat sau cont inactiv.
- 403: rol neautorizat.
- 404: resursă inexistentă sau neasignată; nu dezvăluie apartenența altuia.
- 409: cont/ID duplicat sau conflict de relații.
- 422: format invalid ori companie/locatar nevalid.
- 429: prea multe încercări de autentificare, `Retry-After: 60`.
- 502/503: serviciul legacy sau baza de date indisponibilă.

Răspunsurile `/api/v1` folosesc `Cache-Control: no-store`. Nu există token-uri în URL-uri, logare HTTP a credențialelor sau returnare a hash-urilor parolelor. Definiția OpenAPI completă, generată de FastAPI, este disponibilă în `/docs` după instalare.
