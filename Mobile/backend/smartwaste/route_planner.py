"""Exact stop ordering on the directed road distance matrix."""
import math
import os
import httpx
from fastapi import HTTPException


def post(url, key, payload):
    headers = {'Authorization': key}
    try:
        with httpx.Client(timeout=25, follow_redirects=False) as client:
            response = client.post(url, headers=headers, json=payload)
        if response.status_code == 429:
            raise HTTPException(429, 'Cota gratuită de rutare a fost atinsă. Reîncearcă mai târziu.')
        if response.status_code in (401, 403):
            raise HTTPException(503, 'Cheia openrouteservice nu este validă ori nu are acces.')
        response.raise_for_status()
        return response.json()
    except (httpx.HTTPError, ValueError):
        raise HTTPException(502, 'Serviciul de rutare nu a răspuns corect. Ruta nu a fost salvată.') from None


def optimal_order(matrix):
    """Held–Karp: state (visited mask, last stop) stores cost and predecessor."""
    stops = range(1, len(matrix))
    all_visited = (1 << len(stops)) - 1
    def bit(stop):
        return 1 << (stop - 1)
    best = {(bit(stop), stop): (matrix[0][stop], 0) for stop in stops}
    for mask in range(1, all_visited + 1):
        for last in stops:
            if (mask, last) not in best:
                continue
            cost, _ = best[mask, last]
            for next_stop in stops:
                if mask & bit(next_stop):
                    continue
                key = (mask | bit(next_stop), next_stop)
                candidate = cost + matrix[last][next_stop]
                if key not in best or candidate < best[key][0]:
                    best[key] = (candidate, last)
    last = min(stops, key=lambda stop: (best[all_visited, stop][0] + matrix[stop][0], stop))
    order = []
    mask = all_visited
    while mask:
        order.append(last)
        previous = best[mask, last][1]
        mask ^= bit(last)
        last = previous
    return order[::-1]


def road_matrix(hq, bins):
    ors = os.getenv('OPENROUTESERVICE_API_KEY')
    if not ors:
        raise HTTPException(503, 'Configurează OPENROUTESERVICE_API_KEY în .env pe Raspberry Pi.')
    if not 1 <= len(bins) <= 12:
        raise HTTPException(422, 'Această versiune planifică între 1 și 12 opriri într-o rută.')
    coords = [[hq[1], hq[0]]] + [[b['longitude'], b['latitude']] for b in bins]
    matrix = post('https://api.openrouteservice.org/v2/matrix/driving-car', ors,
                  {'locations': coords, 'metrics': ['distance']}).get('distances')
    n = len(coords)
    if not isinstance(matrix, list) or len(matrix) != n or any(not isinstance(row, list) or len(row) != n or
        any(not isinstance(v, (float, int)) or not math.isfinite(v) or v < 0 for v in row) for row in matrix):
        raise HTTPException(422, 'Cel puțin o oprire nu este accesibilă rutier. Verifică coordonatele tomberoanelor.')
    return ors, coords, matrix


def draw_plan(ors, coords, bins, order):
    geometry = post('https://api.openrouteservice.org/v2/directions/driving-car/geojson', ors,
        {'coordinates': [coords[0]] + [coords[i] for i in order] + [coords[0]], 'instructions': False})
    try:
        feature = geometry['features'][0]
        points = feature['geometry']['coordinates']
        summary = feature['properties']['summary']
        distance, duration = float(summary['distance']), float(summary['duration'])
        if not math.isfinite(distance) or not math.isfinite(duration) or distance < 0 or duration < 0 or len(points) < 2:
            raise ValueError()
        if any(len(p) < 2 or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in p[:2]) or not -180 <= p[0] <= 180 or not -90 <= p[1] <= 90 for p in points):
            raise ValueError()
    except (KeyError, IndexError, TypeError, ValueError):
        raise HTTPException(502, 'Geometria rutieră primită nu este validă.') from None
    return {'stops': [bins[i-1] for i in order], 'geometry': [[p[1], p[0]] for p in points],
            'distance_meters': distance, 'duration_seconds': duration, 'planner': 'Held–Karp + openrouteservice'}


def plan(hq, bins):
    ors, coords, matrix = road_matrix(hq, bins)
    return draw_plan(ors, coords, bins, optimal_order(matrix))
