# SmartWaste — receptor LoRa cu trei ultrasonici

Versiunea curentă primește `distance_mid_cm`, `distance_full_cm` și `distance_top_cm`.
FastAPI calculează categoria **1 = Gol, 2 = Mediu, 3 = Plin**, cu validare de sus.

**Instrucțiuni complete:** [ULTRASONIC_SETUP.md](ULTRASONIC_SETUP.md).

Sunt necesare calibrarea fișierului `backend/config/ultrasonic_thresholds.h`, migrarea
`002_ultrasonic.sql`, receptorul nou și APK-ul 1.1.0. Pragurile laterale sunt 5 cm; confirmarea de sus este 10 cm pentru Mediu și 5 cm
pentru Plin. Sunt valorile confirmate de utilizator, încă neverificate fizic.

Protocolul vechi cu procent este documentat în `reference/README-percentage.md`.
Endpoint-ul vechi `/iot/readings` rămâne compatibil, dar receptorul curent folosește
`/iot/ultrasonic-readings` și nu mai așteaptă procente de la ESP32.
