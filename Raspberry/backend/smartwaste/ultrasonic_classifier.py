"""Pure three-sensor classifier; parse numeric #defines without executing C/code."""
from dataclasses import dataclass
import hashlib
import math
import re


class CalibrationError(ValueError):
    pass


class SensorError(ValueError):
    pass


@dataclass(frozen=True)
class Thresholds:
    mid: float
    full: float
    top_full: float
    top_medium: float
    minimum: float
    maximum: float
    fingerprint: str


DEFINES = ('MID_DETECT_CM', 'FULL_DETECT_CM', 'TOP_FULL_CM', 'TOP_MEDIUM_CM', 'SENSOR_MIN_CM', 'SENSOR_MAX_CM')


def parse_thresholds(source: str) -> Thresholds:
    values = {}
    for line in source.splitlines():
        line = line.split('//', 1)[0].strip()
        if not line:
            continue
        match = re.fullmatch(r'#define\s+(\w+)\s+([-+]?(?:\d+(?:\.\d*)?|\.\d+))', line)
        if not match or match[1] not in DEFINES or match[1] in values:
            raise CalibrationError('Configurație #define invalidă sau duplicată.')
        values[match[1]] = float(match[2])
    if set(values) != set(DEFINES) or any(not math.isfinite(v) or v <= 0 for v in values.values()):
        raise CalibrationError('Calibrează toate pragurile pozitive din ultrasonic_thresholds.h înainte de utilizare.')
    low, high = values['SENSOR_MIN_CM'], values['SENSOR_MAX_CM']
    if low >= high or not all(low <= values[k] <= high for k in DEFINES[:4]):
        raise CalibrationError('Pragurile trebuie să se afle în intervalul valid al senzorilor.')
    if values['TOP_FULL_CM'] >= values['TOP_MEDIUM_CM']:
        raise CalibrationError('TOP_FULL_CM trebuie să fie mai mic decât TOP_MEDIUM_CM.')
    canonical = '\n'.join(f'{k}={values[k]}' for k in DEFINES)
    return Thresholds(*(values[k] for k in DEFINES), hashlib.sha256(canonical.encode()).hexdigest())


def classify(mid: float, full: float, top: float, thresholds: Thresholds) -> int:
    for distance in (mid, full, top):
        if type(distance) not in (float, int) or not math.isfinite(distance) or not thresholds.minimum <= distance <= thresholds.maximum:
            raise SensorError('Distanță invalidă sau în afara intervalului calibrat. Starea anterioară este păstrată.')
    at_mid, at_full = mid <= thresholds.mid, full <= thresholds.full
    lateral = 3 if at_full else 2 if at_mid else 1
    # Top sensor validates the lateral candidate; it does not independently
    # promote medium to full. A confirmed rim detection has priority.
    confirmed = (top <= thresholds.top_full if lateral == 3 else
                 top <= thresholds.top_medium if lateral == 2 else
                 top > thresholds.top_medium)
    if not confirmed:
        raise SensorError(f'Validare nereușită pentru categoria {lateral}: distanța de sus nu confirmă senzorii laterali. Starea anterioară este păstrată.')
    return lateral
