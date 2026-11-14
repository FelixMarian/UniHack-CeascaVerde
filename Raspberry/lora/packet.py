"""JSON wire format normalization. No GPIO/SPI imports, independently testable."""
import math
import re


def field(data, name, *aliases):
    present = [key for key in (name, *aliases) if key in data]
    if not present:
        raise ValueError(f'Missing {name}')
    value = data[present[0]]
    if any(data[key] != value for key in present[1:]):
        raise ValueError(f'Conflicting aliases for {name}')
    return value


def coordinate(value, limit, name):
    if type(value) not in (int, float) or not math.isfinite(value) or not -limit <= value <= limit:
        raise ValueError(f'Invalid {name}')
    return float(value)


def validate_reading(data):
    if not isinstance(data, dict):
        raise ValueError('JSON object expected')
    bin_id = field(data, 'bin_id', 'id')
    if not isinstance(bin_id, str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}', bin_id):
        raise ValueError('Invalid bin_id')
    level = field(data, 'fill_level')
    if type(level) is not int or not 0 <= level <= 100:
        raise ValueError('Invalid fill_level')
    battery = data.get('battery')
    if battery is not None and (type(battery) is not int or not 0 <= battery <= 100):
        raise ValueError('Invalid battery')
    result = {
        'bin_id': bin_id,
        'latitude': coordinate(field(data, 'latitude', 'lat'), 90, 'latitude'),
        'longitude': coordinate(field(data, 'longitude', 'long', 'lon'), 180, 'longitude'),
        'fill_level': level,
    }
    if battery is not None:
        result['battery'] = battery
    return result


def validate_ultrasonic(data):
    if not isinstance(data, dict):
        raise ValueError('JSON object expected')
    bin_id = field(data, 'bin_id', 'id')
    if not isinstance(bin_id, str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}', bin_id):
        raise ValueError('Invalid bin_id')
    if 'fill_level' in data or 'fill_category' in data:
        raise ValueError('Send the three distances, not a percentage or category; classification runs on Raspberry Pi')
    result = {
        'bin_id':bin_id,
        'latitude':coordinate(field(data,'latitude','lat'),90,'latitude'),
        'longitude':coordinate(field(data,'longitude','long','lon'),180,'longitude'),
    }
    for name in ('distance_mid_cm','distance_full_cm','distance_top_cm'):
        value = field(data,name)
        if type(value) not in (int,float) or not math.isfinite(value) or value <= 0:
            raise ValueError(f'Invalid {name}; no echo must not be sent as zero')
        result[name] = float(value)
    battery = data.get('battery')
    if battery is not None:
        if type(battery) is not int or not 0 <= battery <= 100:
            raise ValueError('Invalid battery')
        result['battery'] = battery
    return result
