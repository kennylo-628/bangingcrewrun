"""
Fetches latest Banging Crew activities from Strava API
and rewrites `running banging crew/data.js`.

Club activities endpoint returns limited fields (privacy):
  athlete.firstname, athlete.lastname, name, distance,
  moving_time, elapsed_time, total_elevation_gain, sport_type, type

Run automatically by GitHub Actions every 6 hours.
"""

import requests
import json
import os
import re

CLIENT_ID     = os.environ['STRAVA_CLIENT_ID']
CLIENT_SECRET = os.environ['STRAVA_CLIENT_SECRET']
REFRESH_TOKEN = os.environ['STRAVA_REFRESH_TOKEN']
CLUB_ID       = '2006097'
DATA_FILE     = 'running banging crew/data.js'


def get_access_token():
    r = requests.post('https://www.strava.com/oauth/token', data={
        'client_id':     CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'refresh_token': REFRESH_TOKEN,
        'grant_type':    'refresh_token',
    })
    r.raise_for_status()
    return r.json()['access_token']


def get_club_activities(token):
    headers = {'Authorization': f'Bearer {token}'}
    r = requests.get(
        f'https://www.strava.com/api/v3/clubs/{CLUB_ID}/activities',
        headers=headers,
        params={'per_page': 30}
    )
    r.raise_for_status()
    return r.json()


def fmt_time(seconds):
    h, rem = divmod(int(seconds), 3600)
    m, s   = divmod(rem, 60)
    return f'{h}:{m:02d}:{s:02d}' if h else f'{m}:{s:02d}'


def is_run(a):
    return a.get('sport_type') == 'Run' or a.get('type') == 'Run'


def build_activities(raw):
    runs = [a for a in raw if is_run(a)]
    result = []
    for i, a in enumerate(runs[:8]):
        athlete = a.get('athlete', {})
        result.append({
            'athlete': f"{athlete.get('firstname', '')} {athlete.get('lastname', '')}".strip(),
            'name':    a.get('name', 'Run'),
            'dist':    round(a.get('distance', 0) / 1000, 1),
            'time':    fmt_time(a.get('moving_time', 0)),
            'elev':    int(a.get('total_elevation_gain', 0)),
        })
    return result


def build_weekly_stats(raw):
    """
    Club endpoint has no date field (privacy), so we aggregate
    the most recent activities returned (up to 30).
    Label shows count context instead of date range.
    """
    runs = [a for a in raw if is_run(a)]
    total_dist = sum(a.get('distance', 0) for a in runs) / 1000
    total_secs = sum(a.get('moving_time', 0) for a in runs)
    total_elev = sum(a.get('total_elevation_gain', 0) for a in runs)
    h, rem     = divmod(int(total_secs), 3600)
    m          = rem // 60

    return {
        'week':      f'Latest {len(runs)} Runs',
        'runs':      len(runs),
        'distance':  f'{total_dist:.1f}',
        'time':      f'{h}h {m:02d}m',
        'elevation': str(int(total_elev)),
    }


def read_next_event(path):
    """Preserve the existing nextEvent block — never overwrite it."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        match = re.search(r'(const nextEvent\s*=\s*\{.*?\};)', content, re.DOTALL)
        if match:
            return match.group(1)
    except FileNotFoundError:
        pass
    return """const nextEvent = {
  date: 'TBC',
  time: 'TBC',
  location: 'TBC',
  recurring: 'Weekly · Every Saturday',
  lat: 22.3308,
  lng: 114.1628
};"""


def write_data_js(path, stats, activities, next_event_block):
    acts_json  = json.dumps(activities, ensure_ascii=False, indent=2)
    stats_json = json.dumps(stats,      ensure_ascii=False, indent=2)
    content = f"""// AUTO-UPDATED by GitHub Actions — do not edit weeklyStats or activities manually

const weeklyStats = {stats_json};

const activities = {acts_json};

// MANUAL — update nextEvent for each upcoming run
{next_event_block}
"""
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"✓ data.js updated — {len(activities)} activities")


if __name__ == '__main__':
    token      = get_access_token()
    raw        = get_club_activities(token)
    stats      = build_weekly_stats(raw)
    acts       = build_activities(raw)
    next_event = read_next_event(DATA_FILE)
    write_data_js(DATA_FILE, stats, acts, next_event)
