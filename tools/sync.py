#!/usr/bin/env python3
"""
Sync liked songs from ncm-cli to local database.
Auto-looks up new songs via MusicBrainz for tag suggestions.
Usage: python sync.py
"""
import json, os, subprocess, sys, re, io
from datetime import datetime, timezone

# Force UTF-8 on Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(SCRIPT_DIR, 'songs_db.json')
PLAYLIST_ID = os.environ.get('NCM_LIKED_PLAYLIST_ID', '')

from musicbrainz import lookup_song

def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'meta': {'last_sync': None, 'total': 0}, 'songs': []}

def save_db(db):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(db, f, ensure_ascii=False, indent=2)

def fetch_all_songs():
    """Fetch all liked songs via ncm-cli, return parsed list."""
    ncm_cli = os.path.join(os.environ.get('APPDATA', ''), 'npm', 'ncm-cli.cmd')
    if not os.path.exists(ncm_cli):
        ncm_cli = 'ncm-cli'

    songs = []
    for offset in range(0, 500, 100):
        result = subprocess.run(
            [ncm_cli, 'playlist', 'tracks',
             '--playlistId', PLAYLIST_ID,
             '--limit', '100',
             '--offset', str(offset),
             '--output', 'json'],
            capture_output=True, encoding='utf-8', timeout=30
        )
        if result.returncode != 0:
            err = result.stderr[:200] if result.stderr else 'unknown'
            print(f'  Warning: offset={offset} failed: {err}')
            break
        try:
            data = json.loads(result.stdout)
            batch = data.get('data', [])
            if not batch:
                break
            for s in batch:
                songs.append({
                    'id': s['id'],
                    'oid': s['originalId'],
                    'name': s['name'],
                    'artists': [a['name'] for a in s.get('artists', [])],
                    'album': s.get('album', {}).get('name', ''),
                    'duration_ms': s.get('duration'),
                    'liked_at': s.get('extMap', {}).get('addTime'),
                })
        except Exception:
            break
    return songs

def auto_tag(song):
    """Query MusicBrainz for tag suggestions. Returns categorized tags."""
    artist = song['artists'][0] if song['artists'] else ''
    result = lookup_song(artist, song['name'])
    tags = []
    if result.get('genres'):
        for g in result['genres']:
            tags.append(f'流派:{g}')
    if result.get('tags'):
        for t in result['tags']:
            # Skip if already covered by genre mapping
            tags.append(f'风格:{t}')
    if result.get('year'):
        tags.append(f'年代:{result["year"]}')
    return tags

def sync():
    if not PLAYLIST_ID:
        print('ERROR: NCM_LIKED_PLAYLIST_ID environment variable is not set.')
        print('Set it to your liked songs playlist ID (32-char hex from playlist URL).')
        print('Example: export NCM_LIKED_PLAYLIST_ID="YOUR_PLAYLIST_ID"')
        sys.exit(1)

    db = load_db()
    existing_ids = {s['id'] for s in db['songs']}
    now = datetime.now(timezone.utc).isoformat()

    print('Fetching liked songs from ncm-cli...')
    latest = fetch_all_songs()
    if not latest:
        print('ERROR: Failed to fetch songs. Is ncm-cli logged in?')
        sys.exit(1)

    new_songs = []
    new_ids = set()
    for s in latest:
        sid = s['id']
        new_ids.add(sid)
        if sid not in existing_ids:
            s['tags'] = []
            s['synced_at'] = now
            new_songs.append(s)

    removed_ids = existing_ids - new_ids
    removed = [s for s in db['songs'] if s['id'] in removed_ids]

    # Update existing songs
    for s in db['songs']:
        for fresh in latest:
            if s['id'] == fresh['id']:
                s['name'] = fresh['name']
                s['artists'] = fresh['artists']
                s['album'] = fresh['album']
                s['duration_ms'] = fresh['duration_ms']
                s['synced_at'] = now
                break

    # Auto-tag new songs with MusicBrainz
    for s in new_songs:
        print(f'  Looking up: {s["name"]} — {s["artists"][0] if s["artists"] else "?"}')
        mb_tags = auto_tag(s)
        s['tags'] = mb_tags
        print(f'    -> {", ".join(mb_tags) if mb_tags else "(no tags found)"}')

    # Add new
    db['songs'].extend(new_songs)
    db['meta'] = {'last_sync': now, 'total': len(db['songs'])}
    save_db(db)

    # Report
    print(f'\n=== Sync Report ===')
    print(f'  Total:  {len(db["songs"])} songs')
    print(f'  New:    {len(new_songs)}')
    for s in new_songs:
        artists = ', '.join(s['artists'])
        print(f'          + {s["name"]} — {artists}')
        if s['tags']:
            print(f'            Tags: {", ".join(s["tags"])}')
    print(f'  Removed:{len(removed)}')
    for s in removed:
        artists = ', '.join(s['artists'])
        print(f'          - {s["name"]} — {artists}')
    print(f'  Unchanged: {len(db["songs"]) - len(new_songs)}')

if __name__ == '__main__':
    sync()
