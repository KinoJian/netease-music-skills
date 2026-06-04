#!/usr/bin/env python3
"""
Song tag manager with MusicBrainz integration.
Usage:
  python tag.py add <keyword> --tags "tag1, tag2" [--all]
  python tag.py show <keyword> [--mb]
  python tag.py lookup <keyword>          # Show MusicBrainz info
  python tag.py search <keyword>
  python tag.py list [--tag <tag>]
  python tag.py tags
  python tag.py categorize               # Show tags grouped by category

Tag format: "category:value"  (e.g. "流派:爵士", "情绪:积极向上")
"""
import json, os, sys, argparse, io, re
from collections import defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(SCRIPT_DIR, 'songs_db.json')

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from musicbrainz import lookup_song

CATEGORIES = {
    '情绪': ['情绪', 'mood', 'vibe'],
    '流派': ['流派', 'genre'],
    '器乐': ['器乐', 'instrument', '乐器'],
    '氛围': ['氛围', 'atmosphere', '场景'],
    '节奏': ['节奏', 'tempo', 'bpm', '速度'],
    '年代': ['年代', '年代', 'era', 'decade'],
    '人声': ['人声', 'vocal', 'vocals'],
    '来源': ['来源', 'source', 'ost', 'anime', 'game'],
}

def load_db():
    if not os.path.exists(DB_FILE):
        print('Database not found. Run "python tools/sync.py" first to sync your liked songs.')
        return {'meta': {'last_sync': None, 'total': 0}, 'songs': []}
    with open(DB_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_db(db):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(db, f, ensure_ascii=False, indent=2)

def find_songs(db, query, search_tags=False):
    q = query.lower()
    matches = []
    for s in db['songs']:
        if q == s['id'].lower() or q == str(s['oid']):
            return [s]
        if len(q) >= 4 and s['id'].lower().startswith(q):
            return [s]
        fields = '|'.join([s['name'], ', '.join(s['artists']), s['album']]).lower()
        if search_tags:
            fields += '|' + ', '.join(s['tags']).lower()
        if q in fields:
            matches.append(s)
    return matches

def fmt(s):
    artists = ', '.join(s['artists'])
    dur = ''
    if s.get('duration_ms'):
        m, sec = divmod(s['duration_ms'] // 1000, 60)
        dur = f' [{m}:{sec:02d}]'
    tags = f'  [{", ".join(s["tags"])}]' if s['tags'] else ''
    return f'{s["name"]} -- {artists}{dur}{tags}'

def categorize_tags(tags):
    """Group tags by category."""
    groups = defaultdict(list)
    uncategorized = []
    for tag in tags:
        if ':' in tag:
            cat, val = tag.split(':', 1)
            groups[cat].append(val)
        else:
            uncategorized.append(tag)
    return dict(groups), uncategorized

def print_tags_detail(tags):
    """Print tags organized by category."""
    groups, other = categorize_tags(tags)
    if not groups and not other:
        print('  (no tags)')
        return
    category_order = ['情绪', '流派', '器乐', '氛围', '节奏', '年代', '人声', '来源']
    for cat in category_order:
        if cat in groups:
            print(f'  {cat}:  {", ".join(groups[cat])}')
            del groups[cat]
    for cat, vals in groups.items():
        print(f'  {cat}:  {", ".join(vals)}')
    if other:
        print(f'  其他:  {", ".join(other)}')

# ---- Commands ----

def cmd_add(db, song_id, tags_str, apply_all):
    songs = find_songs(db, song_id)
    if not songs:
        print(f'No song found for: {song_id}')
        sys.exit(1)
    if len(songs) > 1 and not apply_all:
        print(f'Multiple matches ({len(songs)}):')
        for s in songs[:10]:
            print(f'  [{s["id"][:8]}...] {fmt(s)}')
        print('\nUse --all to tag all matches.')
        sys.exit(1)

    targets = songs if apply_all else [songs[0]]
    new_tags = [t.strip() for t in tags_str.split(',') if t.strip()]

    # Deduplicate within same category (replace old value with new)
    new_by_cat = {}
    for t in new_tags:
        if ':' in t:
            cat, val = t.split(':', 1)
            new_by_cat[cat] = val
        else:
            new_by_cat[t] = t  # uncategorized

    for song in targets:
        # Remove existing tags in same categories, then add new ones
        remaining = []
        for t in song['tags']:
            if ':' in t:
                cat = t.split(':', 1)[0]
                if cat in new_by_cat:
                    continue  # replace with new value
            elif t in new_by_cat:
                continue
            remaining.append(t)
        song['tags'] = remaining + new_tags

    save_db(db)
    print(f'[OK] Tags added to {len(targets)} song(s):')
    for s in targets:
        print(f'     {fmt(s)}')

def cmd_rm(db, song_id, tags_str, apply_all):
    songs = find_songs(db, song_id)
    if not songs:
        print(f'No song found for: {song_id}')
        sys.exit(1)
    if len(songs) > 1 and not apply_all:
        print(f'Multiple matches ({len(songs)}). Use --all to remove from all.')
        for s in songs[:10]:
            print(f'  [{s["id"][:8]}...] {fmt(s)}')
        sys.exit(1)

    targets = songs if apply_all else [songs[0]]
    rm_tags = [t.strip() for t in tags_str.split(',') if t.strip()]
    for song in targets:
        song['tags'] = [t for t in song['tags'] if t not in rm_tags]
    save_db(db)
    print(f'[OK] Tags removed from {len(targets)} song(s):')
    for s in targets:
        print(f'     {fmt(s)}')

def cmd_show(db, song_id, show_mb=False):
    songs = find_songs(db, song_id)
    if not songs:
        print(f'No song found for: {song_id}')
        sys.exit(1)
    for s in songs[:5]:
        artists = ', '.join(s['artists'])
        print(f'\n  [{s["id"][:12]}...] {s["name"]}')
        print(f'  Artist:   {artists}')
        print(f'  Album:    {s["album"]}')
        if s.get('duration_ms'):
            m, sec = divmod(s['duration_ms'] // 1000, 60)
            print(f'  Duration: {m}:{sec:02d}')
        print(f'  URL:      https://music.163.com/#/song?id={s["oid"]}')
        print(f'  Tags:')
        print_tags_detail(s['tags'])

        if show_mb:
            print(f'\n  --- MusicBrainz ---')
            result = lookup_song(
                s['artists'][0] if s['artists'] else '',
                s['name']
            )
            if result.get('genres'):
                print(f'  MB Genres: {", ".join(result["genres"])}')
            if result.get('tags'):
                print(f'  MB Tags:   {", ".join(result["tags"])}')
            if result.get('year'):
                print(f'  MB Year:   {result["year"]}')
            if result.get('score'):
                print(f'  MB Score:  {result["score"]}')
            if not any([result.get('genres'), result.get('tags')]):
                print(f'  (no MusicBrainz data found)')

def cmd_lookup(db, song_id):
    """Show MusicBrainz info for a song."""
    songs = find_songs(db, song_id)
    if not songs:
        print(f'No song found for: {song_id}')
        sys.exit(1)
    s = songs[0]
    artist = s['artists'][0] if s['artists'] else ''
    name = s['name']
    print(f'\n  Looking up: {name} -- {artist}')
    result = lookup_song(artist, name)
    print(f'  Score:    {result.get("score", "?")}')
    print(f'  Year:     {result.get("year", "?")}')
    print(f'  Genres:   {", ".join(result["genres"]) if result.get("genres") else "(none)"}')
    print(f'  Raw Tags: {", ".join(result["tags"]) if result.get("tags") else "(none)"}')

def cmd_list(db, tag_filter=None):
    if tag_filter:
        songs = [s for s in db['songs'] if tag_filter in s['tags']]
        print(f'Songs matching "{tag_filter}": {len(songs)}')
    else:
        songs = [s for s in db['songs'] if s['tags']]
        print(f'Tagged songs: {len(songs)}/{db["meta"]["total"]}')
    for s in sorted(songs, key=lambda x: x['name']):
        print(f'  {fmt(s)}')

def cmd_tags(db):
    all_tags = {}
    for s in db['songs']:
        for t in s['tags']:
            all_tags[t] = all_tags.get(t, 0) + 1

    groups, uncat = defaultdict(list), []
    for t, count in sorted(all_tags.items(), key=lambda x: -x[1]):
        if ':' in t:
            cat, val = t.split(':', 1)
            groups[cat].append((val, count))
        else:
            uncat.append((t, count))

    print(f'Tags ({len(all_tags)} unique, {sum(all_tags.values())} total)\n')
    for cat in ['情绪', '流派', '器乐', '氛围', '节奏', '年代', '人声', '来源']:
        if cat in groups:
            print(f'  [{cat}]')
            for val, count in sorted(groups[cat], key=lambda x: -x[1]):
                print(f'    {val}  ({count})')
            del groups[cat]
    for cat, vals in groups.items():
        print(f'  [{cat}]')
        for val, count in sorted(vals, key=lambda x: -x[1]):
            print(f'    {val}  ({count})')
    if uncat:
        print(f'  [未分类]')
        for val, count in sorted(uncat, key=lambda x: -x[1]):
            print(f'    {val}  ({count})')

def cmd_search(db, keyword):
    q = keyword.lower()
    results = []
    for s in db['songs']:
        fields = '|'.join([
            s['name'], ', '.join(s['artists']), s['album'],
            ', '.join(s['tags'])
        ]).lower()
        score = sum(1 for w in q.split() if w in fields)
        if score > 0:
            results.append((score, s))
    results.sort(key=lambda x: -x[0])
    print(f'Search "{keyword}": {len(results)} results')
    for score, s in results[:30]:
        print(f'  {score}* {fmt(s)}')

def main():
    parser = argparse.ArgumentParser(description='Song tag manager with MusicBrainz')
    sub = parser.add_subparsers(dest='cmd')

    for name in ['add', 'rm']:
        p = sub.add_parser(name)
        p.add_argument('song', help='Song ID or keyword')
        p.add_argument('--tags', required=True, help='Comma-separated tags (use category:value)')
        p.add_argument('--all', action='store_true', help='Apply to all matches')

    p_show = sub.add_parser('show')
    p_show.add_argument('song', help='Song ID or keyword')
    p_show.add_argument('--mb', action='store_true', help='Also show MusicBrainz info')

    p_lookup = sub.add_parser('lookup')
    p_lookup.add_argument('song', help='Song ID or keyword')

    p_list = sub.add_parser('list')
    p_list.add_argument('--tag', help='Filter by tag value')

    sub.add_parser('tags', help='List all tags grouped by category')

    p_search = sub.add_parser('search')
    p_search.add_argument('keyword', help='Search keyword')

    args = parser.parse_args()
    if not args.cmd:
        parser.print_help()
        sys.exit(1)

    db = load_db()

    if args.cmd == 'add':
        cmd_add(db, args.song, args.tags, getattr(args, 'all', False))
    elif args.cmd == 'rm':
        cmd_rm(db, args.song, args.tags, getattr(args, 'all', False))
    elif args.cmd == 'show':
        cmd_show(db, args.song, getattr(args, 'mb', False))
    elif args.cmd == 'lookup':
        cmd_lookup(db, args.song)
    elif args.cmd == 'list':
        cmd_list(db, args.tag)
    elif args.cmd == 'tags':
        cmd_tags(db)
    elif args.cmd == 'search':
        cmd_search(db, args.keyword)

if __name__ == '__main__':
    main()
