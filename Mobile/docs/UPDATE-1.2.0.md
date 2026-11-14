# SmartWaste 1.2.0 — instalare și utilizare

APK: `SmartWaste-1.2.0-10.247.174.231.apk`. Server: `http://10.247.174.231:8000/`.
Pachetul conține și extensia backend necesară noilor funcții. Instalarea numai a APK-ului nu adaugă coloanele/API-urile pe Raspberry Pi.

## 1. Actualizarea Raspberry Pi

Dezarhivează pachetul într-un folder separat, de exemplu `/home/djoldskull/Desktop/SmartWaste-1.2.0`.
Acest folder trebuie să conțină direct `backend`, `android`, `docs` și APK-ul.
Rulează:

```bash
bash /home/djoldskull/Desktop/SmartWaste-1.2.0/docs/install-v120.sh
```

Scriptul salvează codul backend vechi în `~/smartwaste/backups/mobile-DATA-ORA/backend`, aplică migrarea aditivă și repornește `smartwaste.service`.
Corecție instalator: migrarea primește explicit `--env-file /home/djoldskull/smartwaste/.env`; nu caută configurația în folderul dezarhivat de pe Desktop. Pentru `KeyError: TIGER_DATABASE_URL` din primul pachet, folosește pachetul corectat sau pornește instalatorul cu variabilele încărcate prin python-dotenv din fișierul serverului. Nu copia parolele în cod și nu trimite fișierul `.env`.
Nu suprascrie `main.py`, `.env`, pragurile ultrasonice existente, receptorul LoRa sau `.venv`.
Folosește `.venv-mobile` pentru backend. Migrarea nu rescrie măsurătorile, colectările sau rapoartele săptămânale.
Backup-ul de cod nu este un backup al bazei de date; folosește backup-ul furnizorului PostgreSQL/Tiger pentru recuperarea datelor.
Serviciul existent trebuie să fie deja configurat pentru `main_mobile:app`, așa cum funcționează acum la tine.

Instalează APK-ul peste versiunea existentă. Telefonul trebuie să poată accesa IP-ul de mai sus.

## 2. Stări și responsabilități

| Valoare API | Afișare | Sursă |
|---|---|---|
| 1 | Gol | ultima măsurătoare ultrasonică |
| 2 | Mediu | ultima măsurătoare ultrasonică |
| 3 | Plin | ultima măsurătoare ultrasonică |
| 4 | Deteriorat | `bins.is_damaged = true` |

`sw_ultrasonic_measurements.fill_category` rămâne 1–3: deteriorarea nu este o măsurătoare de nivel.
API-ul calculează categoria efectivă 4 când `is_damaged` este activ. Măsurătorile continuă să se salveze și nu anulează deteriorarea.
După „Marchează reparat”, reapare ultima stare măsurată. Tomberoanele fără măsurători noi păstrează afișarea procentuală veche; lipsa datelor nu este afișată ca „gol”.

Locatarul trimite o sesizare „Tomberon deteriorat”. Compania responsabilă gestionează sesizarea și folosește „Marchează deteriorat” / „Marchează reparat” în Tomberoane.
O sesizare nu schimbă automat starea tomberonului. Adminul gestionează conturile, asignările și metadatele; acțiunile operaționale sunt ale companiei.

## 3. HQ în baza de date

În modelul actual, compania este un cont în `sw_users` cu `role = 'Company'`; nu există un tabel separat `companies`.
Migrarea 003 adaugă `sw_users.hq_latitude` și `sw_users.hq_longitude`, coordonate WGS84 în grade zecimale.

Cel mai simplu: **Company → Hartă → Configurează HQ**. Alternativ: **Admin → Companii → HQ**.
Salvarea actualizează direct baza de date. Lăsarea ambelor câmpuri goale șterge HQ.

Pentru verificare în consola SQL a bazei Tiger/PostgreSQL:

```sql
SELECT id, username, display_name, hq_latitude, hq_longitude
FROM sw_users
WHERE role = 'Company';
```

Exemplu SQL (înlocuiește coordonatele demonstrative și username-ul înainte de executare):

```sql
UPDATE sw_users
SET hq_latitude = 45.7489, hq_longitude = 21.2087
WHERE username = 'company1' AND role = 'Company';
```

## 4. Hartă, GPS și rută

În Company → Hartă, „Localizează-mă” solicită permisiunea Android și citește poziția telefonului, cu precizia raportată.
Poziția nu este trimisă în baza de date și nu schimbă automat HQ. Fără permisiune poți folosi în continuare HQ și generarea rutei.
Localizarea este anulată când părăsești ecranul și expiră după 20 secunde. Nu există urmărire în fundal.

„Generare rută” produce **HQ → tomberoane pline proprii → HQ**. Folosește următorul punct cel mai apropiat după distanța geografică directă; nu garantează traseul optim.
Exclude tomberoanele deteriorate și raportează explicit tomberoanele pline fără coordonate.
Lista este o propunere de ordine a opririlor, fără drumuri, trafic, sensuri unice, timp de deplasare sau navigație rutieră.
Regenerează după schimbarea stărilor/asignărilor. „Actualizează” șterge ruta veche.

APK-ul livrat nu conține o cheie Google Maps. GPS-ul și lista opririlor funcționează; pentru fundalul Google Maps, adaugă `MAPS_API_KEY` în `android/local.properties` și reconstruiește.
Acest pas rămâne pentru etapa următoare a hărții.

## 5. Solana Devnet — rapoartele locatarilor

Integrarea publică un Memo cu prefixul `smartwaste:incident:v1:` și SHA-256 al conținutului sesizării plus un nonce aleatoriu.
Comentariul, identitatea și coordonatele nu apar în tranzacție. Nonce-ul împiedică ghicirea conținutului prin compararea unor hash-uri simple.
Sesizarea inițială este protejată; schimbarea statusului în „rezolvată” nu modifică dovada.
Tabelul `sw_incidents` primește `proof_nonce`, `proof_hash`, `solana_signature`, `proof_transaction`.
Ultimul câmp păstrează tranzacția deja semnată pentru reluare fără semnături noi la fiecare eroare de rețea.

În aplicație, „Verifică pe Solana” interoghează serverul, care verifică **tranzacția finalizată, lipsa erorilor, programul Memo și hash-ul exact**.
Hash pregătit / tranzacție trimisă / rețea indisponibilă NU înseamnă verificat. Integritatea nu dovedește adevărul sesizării.
Implementarea este exclusiv Devnet; nu transferă SOL către alte conturi. Sunt necesare monede Devnet pentru taxa de tranzacție.

### Activare pe Raspberry Pi

După instalarea backend-ului:

```bash
cd /home/djoldskull/smartwaste/backend
../.venv-mobile/bin/python -m pip install -r requirements-solana.txt
../.venv-mobile/bin/python -m smartwaste.solana_setup
```

Comanda creează sau păstrează un portofel Devnet local și afișează **adresa publică**. Cheia privată rămâne în `/home/djoldskull/.config/smartwaste/solana-devnet.json` cu permisiuni restrictive.
Nu trimite nimănui acel fișier. Copiază doar adresa publică în [faucet-ul Solana](https://faucet.solana.com/) și cere SOL de test pentru **Devnet**.

După alimentare:

```bash
sudo cp /home/djoldskull/smartwaste/backend/smartwaste-solana.service /etc/systemd/system/smartwaste-solana.service
sudo systemctl daemon-reload
sudo systemctl enable --now smartwaste-solana.service
sudo journalctl -u smartwaste-solana.service -n 30 --no-pager
```

Serviciul verifică sesizările la fiecare 30 secunde și publică inclusiv sesizările mai vechi. Apasă apoi „Verifică pe Solana” în aplicație.
`submitted` în log înseamnă doar trimis; `verified` înseamnă finalizat și verificat.
Portofelul nu este inclus în APK sau în arhivă. Nu a fost creat/finanțat pe Raspberry Pi din această sesiune.

Limită a primei versiuni: o tranzacție al cărei blockhash a expirat rămâne cu semnătura păstrată; serviciul nu creează automat o tranzacție nouă și aplicația nu o declară verificată. Necesită diagnostic/republicare controlată într-o etapă ulterioară.
RPC-ul public poate limita cererile. Serviciul este destinat demonstrației și unui volum mic, nu unei cozi de producție.

## Verificare și limite

Build Android, teste JVM, lint și teste backend SQLite/PostgreSQL local. Semnarea reală a tranzacțiilor este verificată local cu solders; RPC este simulat în teste.
Nu s-a efectuat o publicare reală Devnet, nu s-a instalat această versiune pe Raspberry Pi și GPS-ul nu a fost testat pe telefonul Samsung.
Nu este inclus un portofel ori o cheie Maps. Configurarea lor este descrisă mai sus.

Surse tehnice: [Solana getTransaction](https://solana.com/docs/rpc/http/gettransaction), [Memo Program](https://www.solana-program.com/docs/memo), [solders Transaction](https://kevinheavey.github.io/solders/api_reference/transaction.html), [Android LocationManager](https://developer.android.com/reference/android/location/LocationManager).
