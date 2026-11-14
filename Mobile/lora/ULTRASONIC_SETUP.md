# Trei ultrasonici → 1 Gol / 2 Mediu / 3 Plin

Acest update înlocuiește mesajul cu procent cu trei distanțe etichetate. ESP32 măsoară; FastAPI pe Raspberry Pi calculează categoria. Codul și APK-ul au fost pregătite și testate local. Instalarea pe Raspberry Pi nu a fost efectuată: conexiunea SSH la `10.253.97.231:22` a expirat.

## 1. Formatul ESP32

JSON UTF-8, distanțe **în centimetri**, nu microsecunde sau milimetri:

```json
{"bin_id":"BIN_001","lat":45.748,"long":21.208,"distance_mid_cm":50,"distance_full_cm":50,"distance_top_cm":90}
```

Valorile sunt exemple de format, nu măsurători sau calibrare pentru coșul tău.

- `distance_mid_cm`: senzor lateral la jumătatea coșului.
- `distance_full_cm`: senzor lateral aproape de buză.
- `distance_top_cm`: senzor de sus orientat în jos.
- `bin_id`: ID-ul creat în Admin; `id` este acceptat ca alias de receptor.
- Coordonate: `lat`/`long` sau `latitude`/`longitude`; se acceptă și `lon`.
- Opțional `battery`: procent întreg 0–100. Lipsa sa nu șterge ultima valoare cunoscută.
- Nu trimite `fill_level` sau `fill_category`: se resping în noul receptor.
- Un senzor fără ecou nu trebuie transformat în zero sau distanță maximă validă. Omite pachetul și încearcă din nou, sau trimite o valoare invalidă care va fi respinsă; nu se deduce „gol” dintr-o eroare.

Păstrează parametrii radio comuni: 433.92 MHz, SF7, BW 125 kHz, CR 4/5, sync word 0x12, CRC. Driverul radio furnizat a rămas neschimbat. Noul mesaj este scurt, dar verifică limita de payload a bibliotecii ESP32 și transmite JSON compact.

## 2. Pragurile #define, pe Raspberry Pi

Fișier:

```text
/home/djoldskull/smartwaste/backend/config/ultrasonic_thresholds.h
```

Conține șase definiții numerice, citite de Python, fără compilare C:

| Define | Semnificație |
|---|---|
| `MID_DETECT_CM` | Distanța maximă la care senzorul lateral de la jumătate consideră deșeurile prezente |
| `FULL_DETECT_CM` | Distanța maximă la care senzorul lateral de la buză consideră deșeurile prezente |
| `TOP_FULL_CM` | Distanța maximă măsurată de sus care confirmă nivelul plin |
| `TOP_MEDIUM_CM` | Distanța maximă măsurată de sus care validează candidatul mediu indicat lateral |
| `SENSOR_MIN_CM` | Limita minimă validă pentru senzorii utilizați |
| `SENSOR_MAX_CM` | Limita maximă validă pentru senzorii utilizați |

Pragurile confirmate sunt deja configurate:

```c
#define MID_DETECT_CM 5
#define FULL_DETECT_CM 5
#define TOP_FULL_CM 5
#define TOP_MEDIUM_CM 10
#define SENSOR_MIN_CM 0.1
#define SENSOR_MAX_CM 400
```

Ultimele două valori sunt limite software implicite pentru respingerea valorilor invalide, nu specificații de precizie ale unui anumit model de senzor. Ajustează-le la senzorii reali. Pragurile 5/5/5/10 au fost alese de utilizator, dar nu au fost calibrate sau verificate fizic în această sesiune.

```bash
nano ~/smartwaste/backend/config/ultrasonic_thresholds.h
```

Reguli: toate valorile trebuie să fie pozitive, în intervalul `SENSOR_MIN_CM`–`SENSOR_MAX_CM`, iar `TOP_FULL_CM < TOP_MEDIUM_CM`. Sunt acceptate numere întregi sau zecimale cu punct, fără unități, expresii sau alte directive C. Pragurile se recitesc la fiecare cerere. Sunt comune tuturor coșurilor; pentru coșuri de geometrii diferite trebuie extinsă configurația per `bin_id`.

Calibrează cu recipientul gol, apoi cu material până la jumătate și apoi aproape de buză. Verifică citirile fiecărui senzor pentru fiecare stare. Pragurile laterale trebuie să distingă obstacolul real de peretele opus. Nu există deocamdată histerezis sau filtrare temporală: oscilațiile peste/sub prag pot crea schimbări repetate.

## 3. Regula de clasificare și validare

Un senzor lateral consideră nivelul atins când `distanța <= pragul` lui.

| Lateral jumătate | Lateral buză | Confirmare de sus | Rezultat |
|---|---|---|---|
| Nu | Nu | `top > TOP_MEDIUM_CM` | **1 — Gol** |
| Da | Nu | `top <= TOP_MEDIUM_CM` (10 cm) | **2 — Mediu** |
| Oricare citire validă | Da | `top <= TOP_FULL_CM` (5 cm) | **3 — Plin**, prioritar |
| Oricare | Oricare | Contrazice nivelul lateral | Citiri contradictorii; respinse |

„Gol” înseamnă **sub pragul mediu**, nu neapărat complet fără deșeuri. Nu se face medie sau vot majoritar: senzorul de sus validează candidatul lateral. Un nivel mediu cu distanță de sus de 3 cm rămâne Mediu dacă senzorul de la buză nu detectează deșeuri. Pentru Plin nu este obligatorie detectarea laterală la mijloc, dar toate cele trei citiri trebuie să fie valide. Dacă senzorul de la buză detectează, însă cel de sus nu confirmă Plin, nu se coboară automat la Mediu: pachetul este respins. Dacă oricare dintre cei trei senzori este invalid ori citirile nu se confirmă, API-ul returnează 422 și păstrează starea și coordonatele anterioare. Receptorul afișează motivul în log. Nu inventează o categorie pentru un senzor defect.

## 4. Baza de date și Android

Migrarea `002_ultrasonic.sql` adaugă o singură tabelă:

```text
sw_ultrasonic_measurements
  id
  bin_id
  fill_category          -- 1, 2 sau 3
  distance_mid_cm
  distance_full_cm
  distance_top_cm
  battery
  config_hash            -- identifică pragurile folosite la clasificarea salvată
  recorded_at
```

Se adaugă un rând la prima categorie validă sau când categoria/bateria se schimbă. Micile variații ale distanțelor în aceeași categorie nu generează rânduri. Coordonatele se actualizează în `bins` numai dacă sunt diferite, fără o măsurătoare nouă dacă nivelul e același. Cele trei distanțe păstrate sunt cele de la schimbarea salvată, nu fiecare citire radio. Un pachet identic nu scrie date noi; logica supraviețuiește restartului și serializează cererile concurente per tomberon.

Valorile vechi din `bin_measurements.fill_level` rămân procente și nu sunt rescrise în 1/2/3. În `/api/v1/bins`, un tomberon cu istoric ultrasonic primește `fill_category: 1/2/3` și `fill_level: null`. Clasificarea ultrasonică are prioritate după prima citire validă; nu amesteca transmiterea procentelor vechi pentru același coș.

APK-ul **1.1.0, versionCode 2** afișează Gol/Mediu/Plin, culorile corespunzătoare și numără categoria 3 drept „necesită colectare”. Nu afișează 1–3% și nu inventează 0/50/100%. Pentru tomberoanele fără citire ultrasonică validă, păstrează afișarea procentelor legacy.

Endpoint-urile și rapoartele originale din `main.py` rămân neschimbate: rapoartele vechi lucrează numai cu procentele din `bin_measurements`, nu includ noul istoric categoric. `recorded_at` este data ultimei schimbări salvate, nu un heartbeat al receptorului. Nu sunt implementate ACK radio, ordonarea pachetelor întârziate sau coadă persistentă; ESP32 trebuie să retrimită periodic starea. Cheia API protejează receptor→FastAPI, nu autentifică expeditorul radio.

## 5. Instalare (după copierea arhivei pe Pi)

Nu rula aceste comenzi pe laptop; sunt pentru Raspberry Pi. Dezarhivează pachetul într-un director separat, de exemplu `~/SmartWaste-Ultrasonic-update`, și deschide terminalul acolo. Pachetul nu conține `main.py`, `.env` sau un fișier systemd care să le înlocuiască.

Backup al surselor care vor fi actualizate:

```bash
backup_dir="$HOME/smartwaste-backups/ultrasonic-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$backup_dir"
cp -a "$HOME/smartwaste/backend" "$backup_dir/backend"
if [ -d "$HOME/smartwaste/lora" ]; then
    cp -a "$HOME/smartwaste/lora" "$backup_dir/lora"
fi
```

Copiază fișierele livrate (din directorul dezarhivat):

```bash
mkdir -p ~/smartwaste/backend/config ~/smartwaste/lora
cp -a backend/smartwaste/. ~/smartwaste/backend/smartwaste/
cp backend/migrations/002_ultrasonic.sql ~/smartwaste/backend/migrations/
cp -n backend/config/ultrasonic_thresholds.h ~/smartwaste/backend/config/
cp lora/receiver.py lora/packet.py lora/requirements.txt ~/smartwaste/lora/
```

`cp -n` păstrează o calibrare deja existentă. Dacă ai instalat o variantă anterioară, deschide fișierul .h și setează explicit pragurile 5/5/5/10 de mai sus; un fișier existent cu -1 nu este suprascris automat. Dacă ai modificat pe Pi fișierele Python după livrarea lor, compară-le cu backup-ul înainte de înlocuire.

Oprește vechiul receptor LoRa din terminalul/serviciul lui; nu porni două receptoare pe același modul SPI. Apoi migrează și repornește FastAPI:

```bash
cd ~/smartwaste/backend
source ../.venv-mobile/bin/activate
python -m smartwaste.manage migrate
```

**Continuă numai dacă migrarea a reușit**, apoi:

```bash
sudo systemctl restart smartwaste.service
sudo systemctl status smartwaste.service --no-pager -l
```

Nu rula seed din nou și nu porni Uvicorn manual în paralel. Migrarea aditivă poate fi repetată și nu șterge date existente. Modifică pragurile în fișierul de la pasul 2. Dacă în `.env` există `SMARTWASTE_LORA_API_URL`, schimbă valoarea în `http://127.0.0.1:8000/iot/ultrasonic-readings` sau elimină suprascrierea, pentru a folosi noul URL implicit. Nu distribui `.env`.

Pornirea receptorului actualizat:

```bash
cd ~/smartwaste
source .venv-mobile/bin/activate
pip install -r lora/requirements.txt
python lora/receiver.py --no-api
```

`--no-api` verifică numai recepția și formatul; nu clasifică și nu scrie în DB. După verificare, Ctrl+C și:

```bash
python lora/receiver.py
```

Dacă ai deja serviciu pentru LoRa, schimbă-i comanda către acest `receiver.py` și repornește-l, în loc să pornești manual. `smartwaste.service` continuă să gestioneze doar FastAPI. Această livrare nu presupune numele sau configurația unui serviciu LoRa existent.

Instalează pe telefon APK-ul din `release/SmartWaste-ultrasonic-debug.apk`, peste aplicația existentă. URL-ul este tot `http://10.253.97.231:8000/`. Dacă IP-ul Pi s-a schimbat, este necesară reconstruirea APK-ului cu noua adresă. Cheia Maps rămâne neconfigurată dacă nu ai adăugat una.

## 6. Verificare și limite

Testat local: **51 teste backend/parser**, inclusiv PostgreSQL real; **5 teste Android**, build APK reușit, Lint 0 erori. Verificate cele trei categorii, pragurile inclusive, valori invalide, contradicții, configurație necalibrată, păstrarea procentelor vechi, filtrarea Resident, deduplicare după restart și 12 cereri simultane.

Nu s-a efectuat calibrare fizică, testare radio pe SX1278 sau instalare pe Pi/Tiger Cloud. Noul APK nu a fost testat pe telefon fizic. Fișierul de praguri livrat conține valorile confirmate de utilizator. Verifică-le pe recipientul real înainte de a te baza pe categorii. Configurațiile incomplete sau invalide sunt respinse cu 503.

După instalare, verifică trei situații fizice cunoscute și confirmă în Android Gol/Mediu/Plin. Retrimite de mai multe ori aceeași stare: receptorul trebuie să afișeze `Unchanged: no database write`. Verifică și un senzor deconectat: nu trebuie să schimbe starea salvată în Gol.
