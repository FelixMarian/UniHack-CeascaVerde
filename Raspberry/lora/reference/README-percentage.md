# LoRa → FastAPI → Tiger Cloud: scriere numai la schimbare

Acest update folosește tabelele existente `bins` și `bin_measurements`. Nu necesită tabele noi, migrare nouă, seed sau APK nou. Necesită instalarea extensiei mobile anterioare (`main_mobile:app`).

## Mesajul ESP32

Trimite JSON UTF-8, de exemplu:

```json
{"bin_id":"BIN_001","lat":45.748,"long":21.208,"fill_level":85}
```

- `bin_id` trebuie să fie exact ID-ul creat în Admin, nu numele afișat al tomberonului. Receptorul acceptă și `id`.
- Coordonatele pot fi `lat`/`long`, `latitude`/`longitude` sau `latitude`/`lon`. Dacă trimiți două variante pentru același câmp, valorile trebuie să coincidă.
- `fill_level`: număr întreg 0–100, fără `%` și fără ghilimele.
- Coordonate: numere JSON finite, cu punct zecimal; ambele sunt obligatorii. Nu folosi `0,0` ca substitut pentru un GPS fără fix; nu transmite măsurătoarea până ai coordonate valide sau folosește coordonatele fixe ale tomberonului.
- `battery` este opțional, întreg 0–100. Când lipsește sau este `null`, valoarea cunoscută anterior este păstrată.
- `sequence` poate exista în mesaj, dar nu este trimis la API și nu blochează actualizările după restartul ESP32. Backend-ul compară valorile persistate.
- Nu se acceptă automat un șir liber precum `BIN_001,21.208,45.748,85`: firmware-ul trebuie să trimită JSON-ul de mai sus.

ID-ul nu este autentificare radio. CRC detectează erorile de transmisie, nu expeditorii falși; autentificarea mesajelor radio nu este adăugată în acest update.

## Comportament

Noul endpoint este `POST /iot/readings`, protejat cu `X-API-Key`. Receptorul convertește mesajul în `bin_id`, `latitude`, `longitude`, `fill_level`, opțional `battery`.

| Ce se primește | Efect în DB |
|---|---|
| Prima măsurătoare pentru un tomberon înregistrat | Adaugă măsurătoarea și actualizează coordonatele dacă diferă |
| Același procent, aceleași coordonate, aceeași baterie | Nu scrie date noi |
| Procent diferit | Adaugă o măsurătoare nouă, păstrând istoricul |
| Doar coordonate diferite | Modifică `bins.latitude/longitude`, fără o măsurătoare duplicată |
| Doar bateria transmisă diferă | Adaugă o măsurătoare, pentru a păstra noua baterie |
| ID neînregistrat | 404; nu creează automat tomberoane |
| Date invalide | Respinse de receptor sau 422 de la API |

Compararea este exactă, pe fiecare `bin_id`. Coordonatele cu mici variații GPS sunt considerate diferite; nu se aplică o toleranță implicită. Exemplu: `85 → 85 → 60 → 60 → 85` produce **3 măsurători**, dacă nu exista anterior una. Nu se confundă tomberoanele cu același procent.

Compararea și actualizarea sunt într-o tranzacție, cu blocarea rândului tomberonului în PostgreSQL. Cererile simultane identice către `/iot/readings` nu produc măsurători duplicate. Acest lucru nu promite deduplicarea scrierilor simultane făcute prin ruta veche `/readings` sau direct în DB; folosește noua rută pentru receptor.

`recorded_at` rămâne timpul ultimei **schimbări salvate**, nu timpul ultimului pachet recepționat. Nu există încă un câmp `last_seen`. Graficele și media din rapoartele existente vor folosi eșantioane la schimbare, nu eșantioane periodice; media existentă nu este ponderată cu timpul.

Pachetele întârziate cu valori diferite sunt tratate drept schimbări la momentul recepției. Nu sunt implementate ordonare după timpul ESP32, ACK radio, coadă persistentă sau retransmitere garantată. Dacă HTTP eșuează, receptorul raportează eroarea și încearcă din nou la următorul pachet primit. ESP32 trebuie să transmită periodic starea; transmisia numai la schimbare necesită ulterior confirmare/retry. Apelul HTTP poate bloca bucla până la timeout-ul existent de 5 secunde; hardware-ul și pierderile radio nu au fost testate aici.

## Instalare pe Raspberry Pi

Dezarhivează `SmartWaste-LoRa-update.zip` pe laptop și copiază:

| Fișier din arhivă | Destinație pe Pi |
|---|---|
| `backend/smartwaste/iot.py` | `/home/djoldskull/smartwaste/backend/smartwaste/iot.py` |
| `backend/smartwaste/integration.py` | `/home/djoldskull/smartwaste/backend/smartwaste/integration.py` |
| `lora/receiver.py` | `/home/djoldskull/smartwaste/lora/receiver.py` |
| `lora/packet.py` | `/home/djoldskull/smartwaste/lora/packet.py` |
| `lora/requirements.txt` | `/home/djoldskull/smartwaste/lora/requirements.txt` |

Păstrează o copie a vechiului `integration.py` și a receptorului înainte de înlocuire. Nu înlocui `main.py`, `main_mobile.py` sau `.env`. Copiază ambele fișiere backend înainte de restart. Dacă ai modificat local `integration.py`, integrează cele trei adăugiri IoT în loc de suprascriere: importul routerului IoT, `app.state.sw_device_key = device_key`, `app.include_router(iot_router)`.

Pe Pi:

```bash
mkdir -p ~/smartwaste/lora
cd ~/smartwaste/backend
source ../.venv-mobile/bin/activate
pip install -r ../lora/requirements.txt
sudo systemctl restart smartwaste.service
sudo systemctl status smartwaste.service --no-pager -l
```

SPI trebuie să fie activat, iar utilizatorul receptorului trebuie să aibă acces la SPI și GPIO conform configurației hardware existente. Nu porni două receptoare simultan pe același modul.

Test doar recepție, **fără scrieri în DB**:

```bash
cd ~/smartwaste
source .venv-mobile/bin/activate
python lora/receiver.py --no-api
```

Oprește testul cu Ctrl+C, apoi pornește receptorul cu trimitere către API:

```bash
python lora/receiver.py
```

Adresa implicită este `http://127.0.0.1:8000/iot/readings`. Opțional, `SMARTWASTE_LORA_API_URL` o suprascrie în `.env`; dacă ai o valoare veche terminată în `/readings`, schimb-o în `/iot/readings`. Cheia este citită din `~/smartwaste/.env` și nu se transmite prin radio.

Pentru același pachet repetat trebuie să vezi:

```text
Database updated: measurement= True coordinates= True
Unchanged: no database write
```

Valorile booleene depind de starea deja existentă în DB. Apasă „Actualizează” în Android pentru a vedea ultima valoare și noua poziție. Acest update nu configurează automat un serviciu systemd separat pentru receptor; serviciul `smartwaste.service` pornește numai FastAPI.

## Verificări efectuate

22 teste backend/parser trecute, inclusiv PostgreSQL local: prima citire, pachet identic, coordonate schimbate, separarea tomberoanelor, revenirea la o valoare mai veche, restart, baterie opțională, autentificare și 12 cereri simultane identice (o singură măsurătoare nouă). Testele backend anterioare trec în continuare.

S-au păstrat registrele, frecvența și setările radio din codul furnizat. **Nu s-a efectuat un test fizic ESP32/SX1278, nici instalarea acestui update pe Pi/Tiger Cloud.** Raportul testelor este inclus în `validation/lora-tests.xml`.
