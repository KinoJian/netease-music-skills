#!/usr/bin/env python3
"""
Convert raw ncm-cli API output to songs_db.json format.
Run once to initialize the database from the liked songs dump.
"""
import json, re, sys, os
from datetime import datetime, timezone

RAW_FILE = os.path.join(os.environ.get('TEMP', '/tmp'), 'all_liked_songs.json')
DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'songs_db.json')

def load_existing_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'meta': {'last_sync': None, 'total': 0}, 'songs': []}

def parse_raw(raw_path):
    with open(raw_path, 'r', encoding='utf-8') as f:
        text = f.read()
    blocks = re.split(r'=== offset=\d+ ===\n', text)
    songs = []
    for block in blocks:
        if not block.strip():
            continue
        try:
            data = json.loads(block)
            for s in data.get('data', []):
                song = {
                    'id': s['id'],
                    'oid': s['originalId'],
                    'name': s['name'],
                    'artists': [a['name'] for a in s.get('artists', [])],
                    'album': s.get('album', {}).get('name', ''),
                    'duration_ms': s.get('duration'),
                    'tags': [],
                    'liked_at': s.get('extMap', {}).get('addTime'),
                    'synced_at': datetime.now(timezone.utc).isoformat()
                }
                songs.append(song)
        except Exception:
            pass
    return songs

def merge_songs(existing, new_songs):
    """Merge new songs into existing DB. Keep existing tags, add new songs."""
    existing_by_id = {s['id']: s for s in existing['songs']}
    merged = []
    new_count = 0
    for song in new_songs:
        if song['id'] in existing_by_id:
            # Keep existing song but update basic info
            old = existing_by_id[song['id']]
            old['name'] = song['name']
            old['artists'] = song['artists']
            old['album'] = song['album']
            old['duration_ms'] = song['duration_ms']
            old['synced_at'] = song['synced_at']
            merged.append(old)
        else:
            merged.append(song)
            new_count += 1
    removed = [s for s in existing['songs'] if s['id'] not in {n['id'] for n in new_songs}]
    return merged, new_count, len(removed)

def main():
    if not os.path.exists(RAW_FILE):
        print(f'ERROR: Raw data not found at {RAW_FILE}')
        print('Run sync.py first to fetch liked songs.')
        sys.exit(1)

    existing = load_existing_db()
    new_songs = parse_raw(RAW_FILE)
    merged, added, removed = merge_songs(existing, new_songs)

    db = {
        'meta': {
            'last_sync': datetime.now(timezone.utc).isoformat(),
            'total': len(merged)
        },
        'songs': merged
    }

    os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(db, f, ensure_ascii=False, indent=2)

    print(f'Database saved: {DB_FILE}')
    print(f'  Total: {len(merged)} songs')
    print(f'  Added: {added}')
    print(f'  Removed: {removed}')
    print(f'  Unchanged: {len(merged) - added}')

if __name__ == '__main__':
    main()
