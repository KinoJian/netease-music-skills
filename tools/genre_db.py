#!/usr/bin/env python3
"""
Music genre database loader (qiaomu / RateYourMusic 5947 genres).
Provides lookup, enrichment, and search expansion for music-curator.

Usage:
  python genre_db.py lookup "Hard Bop"
  python genre_db.py children "Jazz"
  python genre_db.py expand "硬波普"
  python genre_db.py match "爆裂爵士"
"""

import json, os, sys, io

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

GENRE_DIR = os.path.join(
    os.path.expanduser('~'), '.claude', 'skills',
    'qiaomu-music-player-spotify', 'references'
)

# Chinese → English genre mapping (our local tags → RYM English names)
CN_TO_EN = {
    '硬波普': 'Hard Bop',
    '爆裂爵士': 'Death Jazz',
    '爵士嘻哈': 'Jazz Hip Hop',
    '莫代尔爵士': 'Modal Jazz',
    '融合爵士': 'Jazz Fusion',
    '灵魂爵士': 'Soul Jazz',
    '平滑爵士': 'Smooth Jazz',
    '酸性爵士': 'Acid Jazz',
    '自由爵士': 'Free Jazz',
    '爵士流行': 'Jazz Pop',
    '人声爵士': 'Vocal Jazz',
    '波萨诺瓦': 'Bossa Nova',
    '爵士放克': 'Jazz-Funk',
    '爵士融合': 'Jazz Fusion',
    '比波普': 'Bebop',
    '摇摆爵士': 'Swing',
    '大乐队': 'Big Band',
    '激进爵士': 'Nu Jazz',
    '后波普': 'Post-Bop',
    '冷爵士': 'Cool Jazz',
    '暗黑爵士': 'Dark Jazz',
    '室内爵士': 'Chamber Jazz',
    '前卫爵士': 'Avant-Garde Jazz',
    '拉丁爵士': 'Latin Jazz',
    '器乐嘻哈': 'Instrumental Hip Hop',
    '后摇': 'Post-Rock',
    '爵士': 'Jazz',
    '古典': 'Classical',
    '电子': 'Electronic',
    '摇滚': 'Rock',
    '灵魂': 'Soul',
    '放克': 'Funk',
    '嘻哈': 'Hip Hop',
    '流行': 'Pop',
    '民谣': 'Folk',
    '蓝调': 'Blues',
    '氛围': 'Ambient',
}

# Genre keywords for search expansion
GENRE_KEYWORDS = {
    'Hard Bop': ['hard bop', 'bebop', 'bluesy jazz', 'saxophone jazz', 'art blakey', 'jazz messengers'],
    'Modal Jazz': ['modal jazz', 'coltrane', 'miles davis kind of blue', 'impressionist jazz'],
    'Soul Jazz': ['soul jazz', 'gospel jazz', 'organ jazz', 'jimmy smith', 'cannonball adderley'],
    'Cool Jazz': ['cool jazz', 'west coast jazz', 'chet baker', 'gerry mulligan', 'muted trumpet'],
    'Bebop': ['bebop', 'charlie parker', 'dizzy gillespie', 'fast jazz', 'bop'],
    'Jazz Fusion': ['jazz fusion', 'jazz rock', 'weather report', 'mahavishnu', 'electric jazz'],
    'Smooth Jazz': ['smooth jazz', 'contemporary jazz', 'grover washington', 'spyro gyra'],
    'Vocal Jazz': ['vocal jazz', 'jazz singer', 'ella fitzgerald', 'billie holiday', 'jazz standards vocal'],
    'Bossa Nova': ['bossa nova', 'brazilian jazz', 'jobim', 'getz gilberto', 'samba jazz'],
    'Jazz-Funk': ['jazz funk', 'funky jazz', 'herbie hancock headhunters', 'casiopea'],
    'Dark Jazz': ['dark jazz', 'noir jazz', 'bohren', 'doom jazz', 'cinematic jazz'],
    'Nu Jazz': ['nu jazz', 'electronic jazz', 'jazztronica', 'jazzy electronic', 'jazz house'],
    'Acid Jazz': ['acid jazz', 'jamiroquai', 'incognito', 'brand new heavies', 'groove jazz'],
    'Big Band': ['big band', 'swing orchestra', 'duke ellington', 'count basie', 'brass ensemble'],
    'Swing': ['swing jazz', 'benny goodman', 'artie shaw', 'lindy hop', 'swing dance'],
    'Free Jazz': ['free jazz', 'ornette coleman', 'albert ayler', 'avant jazz', 'fire music'],
    'Post-Bop': ['post bop', 'wayne shorter', 'herbie hancock', '60s jazz', 'blue note 60s'],
    'Jazz Pop': ['jazz pop', 'pop jazz', 'jazz vocal pop', 'norah jones', 'diana krall'],
    'Instrumental Hip Hop': ['instrumental hip hop', 'nujabes', 'j dilla', 'beat tape', 'lo fi hip hop'],
    'Post-Rock': ['post rock', 'mogwai', 'explosions in the sky', 'godspeed', 'instrumental rock'],
}


def _load_json(path):
    if not os.path.exists(path):
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def _find_in_subs(sub_genres, name_lower):
    """Recursively search sub_genres for a matching genre name."""
    for s in sub_genres:
        if name_lower in s['name'].lower():
            return s
        if s.get('sub_genres'):
            found = _find_in_subs(s['sub_genres'], name_lower)
            if found:
                return found
    return None


def _search_all_categories(term_lower):
    """Search across all main categories for a genre name."""
    main_dir = os.path.join(GENRE_DIR, 'main')
    detailed_dir = os.path.join(GENRE_DIR, 'detailed')

    # First check main/<category>.json sub_genres
    for fname in os.listdir(main_dir):
        if not fname.endswith('.json'): continue
        data = _load_json(os.path.join(main_dir, fname))
        if not data: continue
        for sub in data.get('sub_genres', []):
            if term_lower in sub['name'].lower():
                return {'genre': sub, 'parent': data['name'], 'level': 'sub'}

    # Then check detailed/<subgenre>.json for deeper levels
    for fname in os.listdir(detailed_dir):
        if not fname.endswith('.json'): continue
        data = _load_json(os.path.join(detailed_dir, fname))
        if not data: continue
        for sub in data.get('sub_genres', []):
            if term_lower in sub['name'].lower():
                return {'genre': sub, 'parent': data['name'], 'level': sub.get('level', 'sub-2')}

    return None


def lookup(genre_name):
    """Look up a genre by English name. Returns dict with name, description, parent, subs."""
    result = _search_all_categories(genre_name.lower())
    if result:
        g = result['genre']
        return {
            'name': g['name'],
            'description': g.get('description', ''),
            'parent': result['parent'],
            'level': result['level'],
            'url': g.get('url', ''),
            'sub_genres': [s['name'] for s in g.get('sub_genres', [])],
        }
    return None


def children(parent_name):
    """List all sub-genres under a parent genre."""
    main_dir = os.path.join(GENRE_DIR, 'main')
    fname = os.path.join(main_dir, parent_name + '.json')
    data = _load_json(fname)
    if not data:
        return None
    return {
        'name': data['name'],
        'description': data.get('description', ''),
        'sub_genres': [{'name': s['name'], 'description': s.get('description', ''),
                        'level': s.get('level', 'sub')}
                       for s in data.get('sub_genres', [])],
    }


def expand(cn_tag):
    """Expand a Chinese tag into search keywords."""
    en_name = CN_TO_EN.get(cn_tag)
    if not en_name:
        return None

    # Get genre description + keywords
    genre_info = lookup(en_name)
    keywords = GENRE_KEYWORDS.get(en_name, [en_name.lower()])

    result = {
        'cn_tag': cn_tag,
        'en_name': en_name,
        'keywords': keywords,
    }
    if genre_info:
        result['description'] = genre_info['description']
        result['parent'] = genre_info['parent']
        result['sub_genres'] = genre_info.get('sub_genres', [])

    return result


def match(cn_tag):
    """Try to match a Chinese genre tag to the RYM database."""
    en_name = CN_TO_EN.get(cn_tag)
    if not en_name:
        return {'matched': False, 'reason': 'No English mapping found'}

    result = _search_all_categories(en_name.lower())
    if result:
        return {
            'matched': True,
            'cn_tag': cn_tag,
            'en_name': en_name,
            'rym_name': result['genre']['name'],
            'description': result['genre'].get('description', ''),
            'parent': result['parent'],
            'level': result['level'],
            'url': result['genre'].get('url', ''),
        }

    # For unmatched genres, try related genres as hints
    related_hints = {
        '爆裂爵士': ['Dark Jazz', 'Avant-Garde Jazz', 'Free Jazz'],
        'Death Jazz': ['Dark Jazz', 'Avant-Garde Jazz', 'Free Jazz'],
        '爵士嘻哈': ['Jazz-Funk', 'Acid Jazz'],
        'Jazz Hip Hop': ['Jazz-Funk', 'Acid Jazz'],
        '涉谷系': ['Jazz Pop', 'Bossa Nova'],
    }
    hints = related_hints.get(cn_tag, related_hints.get(en_name, []))
    if hints:
        return {
            'matched': False,
            'cn_tag': cn_tag,
            'en_name': en_name,
            'reason': 'Not a standard RYM genre, but related to...',
            'related_genres': hints,
        }

    return {'matched': False, 'cn_tag': cn_tag, 'reason': 'Not found in RYM database'}


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser(description='Genre DB tools')
    sub = p.add_subparsers(dest='cmd')

    p_lookup = sub.add_parser('lookup')
    p_lookup.add_argument('name', help='Genre name in English')

    p_children = sub.add_parser('children')
    p_children.add_argument('name', help='Parent genre name')

    p_expand = sub.add_parser('expand')
    p_expand.add_argument('tag', help='Chinese genre tag')

    p_match = sub.add_parser('match')
    p_match.add_argument('tag', help='Chinese genre tag to match against RYM')

    args = p.parse_args()

    if args.cmd == 'lookup':
        r = lookup(args.name)
        print(json.dumps(r, indent=2, ensure_ascii=False) if r else f'Genre "{args.name}" not found.')
    elif args.cmd == 'children':
        r = children(args.name)
        if r:
            print(f'{r["name"]} — {r["description"][:100]}')
            for s in r['sub_genres']:
                print(f'  {s["name"]} ({s["level"]}) — {s["description"][:80]}')
        else:
            print(f'Category "{args.name}" not found.')
    elif args.cmd == 'expand':
        r = expand(args.tag)
        print(json.dumps(r, indent=2, ensure_ascii=False) if r else f'No mapping for "{args.tag}"')
    elif args.cmd == 'match':
        r = match(args.tag)
        print(json.dumps(r, indent=2, ensure_ascii=False))
