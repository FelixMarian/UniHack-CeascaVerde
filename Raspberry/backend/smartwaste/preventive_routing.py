"""Gemini chooses among road-costed options; the server owns route geometry and limits."""
import json
import os
import re
from itertools import combinations

import httpx
from fastapi import HTTPException

from .route_planner import draw_plan, optimal_order, road_matrix


def choose_option(key, model, profiles, options):
    prompt = (
        'Choose one preventive waste collection option. Use the observed average hours '
        'from empty to full, elapsed hours since collection, remaining hours, number of cycles, '
        'additional actual road distance and estimated additional fuel. Prefer urgent bins with '
        'well-supported history and a small detour. An extra collection now should plausibly avoid '
        'an early additional trip. Choose option 0 if the detour is not worthwhile. '
        'Return only the option number as JSON. Data: '
        + json.dumps({'bins': profiles, 'options': options}, separators=(',', ':'))
    )
    payload = {
        'contents': [{'parts': [{'text': prompt}]}],
        'generationConfig': {
            'responseMimeType': 'application/json',
            'responseJsonSchema': {'type': 'object',
                                   'properties': {'option': {'type': 'integer', 'enum': list(range(len(options)))}},
                                   'required': ['option']},
        },
    }
    with httpx.Client(timeout=12, follow_redirects=False) as client:
        response = client.post(
            f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent',
            json=payload, headers={'x-goog-api-key': key})
        response.raise_for_status()
    parts = response.json()['candidates'][0]['content']['parts']
    answer = json.loads(''.join(part['text'] for part in parts if not part.get('thought')))
    selected = answer['option']
    if type(selected) is not int or not 0 <= selected < len(options):
        raise ValueError('Invalid Gemini option')
    return selected


def route_solution(matrix, indices):
    reduced = [[matrix[a][b] for b in indices] for a in indices]
    order = [indices[i] for i in optimal_order(reduced)]
    cycle = [0, *order, 0]
    return order, sum(matrix[a][b] for a, b in zip(cycle, cycle[1:]))


def preventive_plan(hq, required, candidates, consumption):
    """Return a plan plus the confirmed preventive stops and an availability indicator."""
    key, model = os.getenv('GEMINI_API_KEY', ''), os.getenv('GEMINI_MODEL', '')
    if not key or not re.fullmatch(r'[A-Za-z0-9._-]+', model):
        return None, [], 'not_configured'
    bins = required + candidates
    try:
        ors, coords, matrix = road_matrix(hq, bins)
    except HTTPException:
        return None, [], 'unavailable'
    mandatory = list(range(len(required) + 1))
    baseline_order, baseline_distance = route_solution(matrix, mandatory)
    limit = min(1500, max(500, baseline_distance * .20))
    options = [{'option': 0, 'bins': [], 'extra_meters': 0, 'extra_fuel_liters': 0}]
    plans = [(baseline_order, ())]
    for count in range(1, len(candidates) + 1):
        for group in combinations(range(len(candidates)), count):
            order, distance = route_solution(matrix, mandatory + [len(mandatory) + i for i in group])
            extra = max(0, distance - baseline_distance)
            if extra <= limit:
                options.append({'option': len(plans), 'bins': list(group),
                                'extra_meters': round(extra),
                                'extra_fuel_liters': round(extra * consumption / 100000, 3)})
                plans.append((order, group))
    selected = 0
    status = 'detour_too_long'
    if len(plans) > 1:
        profiles = [{field: item[field] for field in
                     ('average_fill_hours', 'hours_since_empty', 'hours_to_full', 'cycles')}
                    for item in candidates]
        try:
            selected = choose_option(key, model, profiles, options)
            status = 'selected' if selected else 'none_selected'
        except (httpx.HTTPError, ValueError, KeyError, TypeError, IndexError):
            status = 'unavailable'
    order, group = plans[selected]
    chosen = [candidates[i] for i in group]
    return draw_plan(ors, coords, bins, order), chosen, status
