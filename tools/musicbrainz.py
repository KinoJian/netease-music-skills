#!/usr/bin/env python3
"""
MusicBrainz API wrapper for song metadata lookup.
Free API, no key required. Rate limit: ~1 req/sec.
"""
import json, os, time, urllib.request, urllib.parse, urllib.error
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_FILE = os.path.join(SCRIPT_DIR, '.mb_cache.json')

class MusicBrainz:
    BASE = 'https://musicbrainz.org/ws/2'

    def __init__(self):
        self._cache = self._load_cache()
        self._last_request = 0

    def _load_cache(self):
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Clear cache older than 30 days
                    cutoff = datetime.now(timezone.utc).timestamp() - 30*24*3600
                    return {k: v for k, v in data.items() if v.get('_ts', 0) > cutoff}
            except Exception:
                pass
        return {}

    def _save_cache(self):
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(self._cache, f, ensure_ascii=False, indent=2)

    def _rate_limit(self):
        elapsed = time.time() - self._last_request
        if elapsed < 1.2:
            time.sleep(1.2 - elapsed)
        self._last_request = time.time()

    def _request(self, endpoint, params):
        """Make a rate-limited GET request to MusicBrainz."""
        url = f'{self.BASE}/{endpoint}?{urllib.parse.urlencode(params)}'
        cache_key = url

        if cache_key in self._cache:
            return self._cache[cache_key]

        self._rate_limit()
        req = urllib.request.Request(url)
        req.add_header('User-Agent', 'SongTagTool/1.0 (personal-use)')
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                data['_ts'] = time.time()
                self._cache[cache_key] = data
                self._save_cache()
                return data
        except Exception as e:
            return {'error': str(e), 'recordings': []}

    def lookup(self, artist, title):
        """Search for a recording and return structured tags."""
        # Clean query
        artist_q = artist.split(',')[0].strip()  # take primary artist
        title_q = title.split('(')[0].strip()    # remove feat. etc

        query = f'recording:"{title_q}" AND artist:"{artist_q}"'
        params = {'query': query, 'fmt': 'json', 'limit': 3}
        data = self._request('recording/', params)

        result = {'tags': [], 'genres': [], 'year': None, 'score': None}
        for r in data.get('recordings', []):
            # Only accept high-confidence matches (score >= 90)
            score = r.get('score', 0)
            if score < 90:
                continue
            result['score'] = score
            # Collect tags
            for t in r.get('tags', []):
                tag = t['name']
                if tag not in result['tags']:
                    result['tags'].append(tag)
            # Try to get first-release-date
            if 'first-release-date' in r:
                result['year'] = r['first-release-date'][:4]
            # Only take the best match
            break

        if result['tags']:
            result['genres'] = self._classify(result['tags'])
        return result

    def _classify(self, tags):
        """Map raw MusicBrainz tags to our category system."""
        genre_map = {
            'jazz': '爵士', 'jazz fusion': '爵士融合', 'jazz-funk': '爵士放克',
            'hip hop': '嘻哈', 'alternative hip hop': '另类嘻哈',
            'rock': '摇滚', 'instrumental rock': '器乐摇滚', 'post-rock': '后摇',
            'electronic': '电子', 'idm': 'IDM', 'ambient': '氛围',
            'classical': '古典', 'piano': '钢琴', 'folk': '民谣',
            'pop': '流行', 'indie': '独立', 'soul': '灵魂',
            'j-pop': '日系流行', 'anime': '动漫', 'soundtrack': '原声',
            'funk': '放克', 'r&b': '节奏蓝调',
        }
        genres = set()
        for tag in tags:
            tag_lower = tag.lower()
            if tag_lower in genre_map:
                genres.add(genre_map[tag_lower])
        return list(genres)


# Singleton
mb = MusicBrainz()

def lookup_song(artist, title):
    """Convenience function: lookup a song and return tags."""
    return mb.lookup(artist, title)
