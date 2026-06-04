#!/usr/bin/env python3
"""
Batch tag all untagged songs using MusicBrainz (Tier 1/2 auto).
Usage: python batch_tag.py
"""
import json, os, sys, time, io

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(SCRIPT_DIR, 'songs_db.json')
sys.path.insert(0, SCRIPT_DIR)
from musicbrainz import lookup_song

def load_db():
    if not os.path.exists(DB_FILE):
        print('Database not found. Run "python tools/sync.py" first to sync your liked songs.')
        return {'meta': {'last_sync': None, 'total': 0}, 'songs': []}
    with open(DB_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_db(db):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(db, f, ensure_ascii=False, indent=2)

def needs_tagging(song):
    """Check if a song needs batch tagging (only if no structured tier1/2 tags)."""
    tags = song.get('tags', [])
    if not tags:
        return True
    # Check if it has structured category:value tags
    has_category = any(':' in t for t in tags)
    # Only tag if it has no category tags OR only has old-style tags
    return not has_category or all(':' not in t for t in tags)

def auto_tag(song):
    """Generate Tier 1+2 tags from MusicBrainz + inference."""
    artist = song['artists'][0] if song['artists'] else ''
    result = lookup_song(artist, song['name'])
    tags = []

    # Tier 1: MusicBrainz data
    if result.get('genres'):
        for g in result['genres']:
            tags.append(f'流派:{g}')
    if result.get('tags'):
        for t in result['tags']:
            tags.append(f'风格:{t}')
    if result.get('year'):
        tags.append(f'年代:{result["year"]}s' if not result['year'].endswith('s') else f'年代:{result["year"]}')

    # Tier 2: Inference
    art = song['artists']
    alb = song.get('album', '')
    dur_ms = song.get('duration_ms', 0)

    # Source type
    lower = (song['name'] + alb + ' '.join(art)).lower()
    if any(w in lower for w in ['ost', 'soundtrack', 'オリジナル', 'サウンドトラック']):
        if 'tv' in lower or 'アニメ' in lower or 'animation' in lower:
            tags.append('来源:动漫OST')
        elif 'game' in lower or 'ゲーム' in lower:
            tags.append('来源:游戏OST')
        elif 'movie' in lower or 'film' in lower or '映画' in lower:
            tags.append('来源:电影OST')
        else:
            tags.append('来源:原声配乐')

    # Instrumental vs vocal
    has_vocal_keywords = any(w in lower for w in ['vocal', 'voice', 'choir', 'feat', 'ft.', 'singer', '歌', '唱'])
    if dur_ms and dur_ms < 150000 and not has_vocal_keywords:
        tags.append('来源:器乐演奏')

    # Region from artist names (Tier 2)
    has_jp = any('぀' <= c <= 'ヿ' or '一' <= c <= '鿿' for c in ' '.join(art))
    if has_jp:
        tags.append('地域:日本')
    # Check for Chinese artists
    has_cn = any('一' <= c <= '鿿' for c in ' '.join(art))
    if has_cn and not has_jp:
        tags.append('地域:华语')

    # Duration-based tempo hint (very rough Tier 2)
    if dur_ms:
        if dur_ms < 120000:
            tags.append('节奏:短曲')
        elif dur_ms > 420000:
            tags.append('节奏:长篇')

    return tags

def main():
    db = load_db()
    untagged = [s for s in db['songs'] if needs_tagging(s)]
    total = len(untagged)
    print(f'Found {total} songs to batch-tag (out of {db["meta"]["total"]})')
    print(f'MusicBrainz rate limit: ~1 req/sec, ETA: ~{total//60} min\n')

    tagged = 0
    skipped = 0
    for i, song in enumerate(untagged):
        artist = song['artists'][0] if song['artists'] else '?'
        print(f'[{i+1}/{total}] {song["name"][:40]} — {artist[:30]}', end=' ')
        try:
            new_tags = auto_tag(song)
            if new_tags:
                song['tags'] = new_tags
                tagged += 1
                print(f'-> {len(new_tags)} tags')
            else:
                skipped += 1
                print('-> (no tags found)')
        except Exception as e:
            skipped += 1
            print(f'-> error: {e}')

        # Save progress every 20 songs
        if (i + 1) % 20 == 0:
            save_db(db)
            print(f'  [saved at {i+1}/{total}]')

    db['meta']['last_batch_tag'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    save_db(db)

    print(f'\n=== Batch Tag Complete ===')
    print(f'  Tagged:  {tagged}')
    print(f'  Skipped: {skipped}')
    print(f'  DB saved to {DB_FILE}')

if __name__ == '__main__':
    main()
