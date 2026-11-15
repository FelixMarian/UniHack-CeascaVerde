# SmartWaste 1.3.0 — hartă gratuită, Gemini, Solana automată și statistici

Serverul APK-ului livrat: **http://10.247.174.231:8000/**.

## Instalare pe Raspberry Pi

Dezarhivează arhiva într-un folder separat de aplicația live, de exemplu `/home/djoldskull/Desktop/UniHack2026`, apoi:

```bash
bash /home/djoldskull/Desktop/UniHack2026/docs/install-v130.sh
```

Instalatorul citește explicit `/home/djoldskull/smartwaste/.env`, face backup codului backend, instalează dependențele și migrarea 004 și repornește serverul.
`main.py`, `.env`, receptorul LoRa, `.venv` și pragurile senzorilor rămân păstrate. Backend-ul folosește `.venv-mobile`.
Nu populează automat datele DEMO. Instalează apoi APK-ul 1.3.0 peste cel vechi.

## Hartă fără Maps Key și fără card

Aplicația folosește **OpenStreetMap**, cu hartă vizuală, markere HQ/tomberoane și geometria rutei pe drumuri.
Nu trebuie să creezi un proiect Google Maps, să activezi billing sau să introduci Maps Key. Nu mai există „Localizează-mă” sau permisiuni GPS în SmartWaste.
Punctul de plecare al planului este HQ. Google Maps/Waze își folosesc propria localizare în timpul navigării.

Harta necesită internet. Tile-urile OSM sunt folosite cu identificarea aplicației, cache și atribuire vizibilă, fără descărcări în masă/offline. Serviciul comunitar nu garantează disponibilitatea; pentru utilizare la scară mare este necesar un furnizor de hărți adecvat.
Vezi [politica oficială OSM](https://operations.osmfoundation.org/policies/tiles/).

## Cele două chei gratuite pentru generarea rutelor

Harta funcționează și înainte de configurarea acestor chei. Generarea rutelor are nevoie de ele pe Raspberry Pi.

### A. openrouteservice

1. Deschide [contul openrouteservice / HeiGIT](https://account.heigit.org/).
2. Creează contul și confirmă adresa de email.
3. Alege planul gratuit **Standard** disponibil în cont și creează o cheie API pentru SmartWaste.
4. Păstrează cheia pentru configurarea de mai jos. Nu o pune în APK și nu o trimite în chat.

Planul are cote de utilizare; verifică valorile din [pagina planurilor](https://openrouteservice.org/plans/). Aplicația afișează eroare la depășirea cotei, nu activează un plan plătit.

### B. Gemini API

1. Deschide [Google AI Studio — API keys](https://aistudio.google.com/apikey) cu contul Google.
2. Creează o cheie API într-un proiect nou sau disponibil.
3. Păstrează proiectul pe **Free Tier**; nu apăsa „Set up billing” / „Upgrade”.
4. În AI Studio verifică modelul text cu cotă gratuită disponibilă pentru proiectul tău și copiază identificatorul exact al modelului. Disponibilitatea și limitele diferă între modele și conturi.

Nu este necesar un abonament Gemini pentru consumatori. Gemini Developer API are propriul [Free Tier](https://ai.google.dev/gemini-api/docs/billing) și [tabel de modele/prețuri](https://ai.google.dev/gemini-api/docs/pricing).
În această integrare Gemini primește numai o matrice de distanțe și numerele opririlor, fără comentariile sesizărilor sau identitatea locatarilor.

### C. Salvează cheile pe Raspberry Pi

```bash
cd /home/djoldskull/smartwaste/backend
../.venv-mobile/bin/python -m smartwaste.configure_routes
sudo systemctl restart smartwaste.service
```

Programul cere cele două chei fără să le afișeze și identificatorul modelului. Le salvează în `.env` ca:

```dotenv
OPENROUTESERVICE_API_KEY=cheia_ta_ors
GEMINI_API_KEY=cheia_ta_gemini
GEMINI_MODEL=identificatorul_exact_al_modelului_gratuit
```

Acestea sunt exemple de nume, nu valori funcționale. Nu adăuga variantele placeholder peste cheile tale.
Nu trebuie reconstruit APK-ul după configurarea lor.

## HQ și generarea rutei

Company → Hartă → Configurează HQ. Coordonatele se salvează în `sw_users.hq_latitude` și `hq_longitude`.
Introdu consumul mediu estimat al vehiculului în L/100 km și apasă „Generează ruta cu Gemini”.

Fluxul serverului:

1. Selectează numai tomberoanele pline ale companiei, exclude deterioratele și anunță coordonatele lipsă.
2. Cere matricea distanțelor rutiere de la openrouteservice.
3. Gemini propune ordinea opririlor pe baza matricei.
4. Serverul validează că nu lipsește și nu se repetă nicio oprire și îmbunătățește determinist ordinea unde distanța scade.
5. openrouteservice furnizează traseul rutier, distanța și timpul estimat. Aplicația desenează geometria pe hartă.

Maximum 12 opriri/rută în această versiune. Este o optimizare euristică, nu o garanție a optimului global.
Profilul demonstrativ este `driving-car`: nu modelează dimensiunile camionului, restricțiile de tonaj, traficul live sau timpul de colectare. Verifică accesul pentru vehiculul real.
La o eroare Gemini/ORS nu se fabrică un traseu și nu se adaugă o cursă în statistici.

## Navigare din oprire în oprire

„Începe navigarea în Google Maps” deschide un segment cu maximum 4 opriri, în ordinea calculată. Segmentele respectă și limita de 3 puncte intermediare a variantei web mobile.
După parcurgere revino în SmartWaste și apasă „Am parcurs segmentul → următorul”, apoi deschide următorul segment. HQ este ultima destinație.
„Waze → următoarea oprire” deschide câte o destinație. Waze Deep Links nu oferă o listă completă de checkpoint-uri.

Google Maps/Waze pot recalcula drumul între opriri. Nu garantăm păstrarea fiecărui segment rutier al ORS în alt navigator.
Navigarea începe din poziția curentă a navigatorului; planul statistic pleacă din HQ. Dacă nu ești la HQ, mergi întâi acolo.
Avansarea checkpoint-urilor nu confirmă colectările. Confirmă golirea separat în Tomberoane.
Rutele sunt salvate pe server și pot fi redeschise; poziția din lista segmentelor este stare UI și trebuie verificată dacă aplicația este închisă complet.

Surse: [Google Maps URLs](https://developers.google.com/maps/documentation/urls/get-started), [Waze Deep Links](https://developers.google.com/waze/deeplinks).

## 10 tomberoane în Timișoara și statistici DEMO

Fișierul `backend/demo_timisoara.sql` poate fi copiat integral în editorul SQL Tiger Cloud și executat după migrarea 004.
Alternativ, din terminalul Pi:

```bash
cd /home/djoldskull/smartwaste/backend
../.venv-mobile/bin/python -m smartwaste.manage demo-timisoara --env-file /home/djoldskull/smartwaste/.env
```

Scriptul creează exact `DEMO_TM_001`…`DEMO_TM_010`, toate pentru **company1**, cu stări gol/mediu/plin/deteriorat.
Locațiile sunt aproximative și demonstrative, nu inventarul real al primăriei. Istoricul senzorilor și colectărilor acoperă 35 de zile, iar cursele sintetice 31 de zile.
HQ demonstrativ este introdus numai dacă firma nu are deja HQ. Datele reale și `BIN_001` nu sunt rescrise.
Executarea repetată a scriptului nu dublează setul. Un conflict parțial de identificatori oprește tranzacția.

Verificare SQL:

```sql
SELECT b.bin_id,b.name,b.latitude,b.longitude,b.is_damaged,u.username
FROM bins b JOIN sw_users u ON u.id=b.company_id
WHERE b.bin_id LIKE 'DEMO_TM_%'
ORDER BY b.bin_id;
```

Asignarea unui locatar la aceste tomberoane se poate face din Admin. Scriptul conține la final și o comandă SQL opțională, comentată, pentru `resident1`.

## Statisticile companiei

Ecranul „Statistici” citește prin backend baza Tiger/PostgreSQL configurată în `TIGER_DATABASE_URL`; telefonul nu se conectează direct la DB.
Nu trebuie creat un dashboard sau serviciu separat în Tiger Cloud.

- Astăzi, săptămâna curentă de luni și luna curentă, în fusul Europe/Bucharest: colectări, curse finalizate, km declarați și combustibil estimat.
- Grafic simplu cu colectările din ultimele 14 zile.
- Pentru fiecare tomberon, pe ultimele 90 de zile: colectări, treceri observate de la gol/mediu la plin, intervalul mediu între colectări și ultima colectare.
- Datele DEMO sunt semnalate explicit. Setul demonstrativ este inclus în totaluri; nu prezenta aceste totaluri ca activitate reală.

Colectările sunt evenimente din tabela `collections`, atribuite contului care le-a confirmat. Nu există măsurători de greutate, deci nu afișăm kilograme inventate.
Repetarea stării „plin” nu este numărată ca umplere nouă; fără istoric suficient, intervalul mediu rămâne indisponibil.
La „Finalizează cursa / kilometraj”, introdu diferența reală de kilometraj a mașinii. Sunt **km declarați**, fără GPS în SmartWaste.
Combustibilul este estimat: km declarați × consum L/100 km ÷ 100. O rută doar calculată sau pornită nu este contorizată drept cursă finalizată.
Noua tabelă `sw_trips` stochează aceste date. Interogări SQL de analiză sunt în `backend/company_statistics.sql`.

## Solana automată la trimiterea sesizării

Cetățeanul apasă „Trimite sesizarea”. Serverul salvează sesizarea și începe automat publicarea/verificarea pe Raspberry Pi; aplicația urmărește rezultatul fără apăsarea butonului vechi „Verifică”.
La succes apare confirmarea Solana Devnet. La eșec apare un cod specific și faptul că sesizarea a fost salvată.
Reîncercarea verificării nu creează o sesizare nouă. Un ID de trimitere previne dublarea la reluarea aceleiași cereri din formular în sesiunea curentă.

Coduri: `SOLANA_NOT_CONFIGURED`, `SOLANA_WALLET_INVALID`, `SOLANA_INSUFFICIENT_FUNDS`, `SOLANA_TRANSACTION_EXPIRED`, `SOLANA_UNAVAILABLE`, `SOLANA_INVALID_PROOF`, `SOLANA_PUBLICATION_FAILED`, `SOLANA_CONFIRMATION_PENDING`.
Un timeout de confirmare nu este declarat fraudă: sesizarea este păstrată și serviciul de fundal continuă verificarea. „Verified” necesită tranzacție finalizată fără erori și Memo cu hash exact.

Pentru prima activare:

```bash
cd /home/djoldskull/smartwaste/backend
../.venv-mobile/bin/python -m smartwaste.solana_setup
```

Introdu doar adresa publică afișată în [faucet-ul Solana Devnet](https://faucet.solana.com/) și cere SOL de test, apoi:

```bash
sudo systemctl enable --now smartwaste-solana.service
sudo journalctl -u smartwaste-solana.service -n 30 --no-pager
```

Nu este nevoie de bani reali. Cheia privată rămâne în `/home/djoldskull/.config/smartwaste/solana-devnet.json`.
Tranzacțiile expirate necesită diagnostic și republicare controlată; nu se schimbă automat semnătura unei trimiteri cu rezultat incert.
Dovada verifică integritatea conținutului raportat, nu adevărul afirmațiilor cetățeanului.

## Limite de verificare

Testele backend folosesc SQLite și PostgreSQL local; Gemini, ORS și Solana RPC sunt simulate în testele de integrare. Semnarea Solana este verificată cu biblioteca reală.
Nu au fost introduse chei reale Gemini/ORS, nu s-a publicat o tranzacție Devnet reală și nu s-a instalat această versiune pe Raspberry Pi în această sesiune.
În emulator am verificat încărcarea hărții OpenStreetMap, afișarea statisticilor din PostgreSQL și salvarea sesizării cu mesajul `SOLANA_NOT_CONFIGURED` afișat automat. Capturile sunt în `validation/` din arhivă. Verifică un traseu rutier real și navigarea între aplicații pe telefon după configurarea cheilor.
