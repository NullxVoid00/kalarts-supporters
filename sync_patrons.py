"""Patreon API v2 -> minimal public VRChat feed. Python 3.10+, standard library only.

No credentials, emails, member IDs or payment amounts are written to the public file.
Optional publishing updates ONE existing Gist file; does not create an account or Gist.
"""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

API = 'https://www.patreon.com/api/oauth2/v2/'
PALETTE = ['#FF4A60', '#B994FF', '#70E8C0', '#FFD281', '#78C7FF', '#F29ED6']

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError('API redirect refused; credentials were not forwarded.')

def request_json(url, token=None, data=None, method=None, form=False):
    headers = {'User-Agent': 'KalArtsSupporterBoard/1.0', 'Accept': 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    if data is not None:
        headers['Content-Type'] = 'application/x-www-form-urlencoded' if form else 'application/json'
        data = (urllib.parse.urlencode(data) if form else json.dumps(data)).encode('utf-8')
    opener = urllib.request.build_opener(NoRedirect())
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, data=data, headers=headers, method=method)
            with opener.open(req, timeout=45) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            if error.code in (429, 500, 502, 503, 504) and attempt < 3:
                delay = error.headers.get('Retry-After', '')
                time.sleep(min(60, int(delay)) if delay.isdigit() else 2 ** (attempt + 1))
                continue
            raise RuntimeError('Remote API returned HTTP ' + str(error.code) + '; previous public list retained.') from None
    raise RuntimeError('Remote API unavailable.')

def atomic_write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as f:
            f.write(text)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)

def clean(value, length):
    return ''.join(c for c in str(value or '') if not unicodedata.category(c).startswith('C')).strip()[:length]

def valid_color(value):
    if not isinstance(value, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', value):
        raise ValueError('Tier colors must be six-digit RGB hex, such as #FF4A60.')
    return value.upper()

def make_feed(pages, config, now=None):
    tier_data = {}
    members = {}
    for page in pages:
        if not isinstance(page.get('data'), list):
            raise ValueError('Invalid Patreon members response; refusing to replace the list.')
        for item in page.get('included', []):
            if item.get('type') == 'tier':
                tier_data[item['id']] = item.get('attributes', {})
        for member in page['data']:
            if member.get('type') == 'member':
                members[member['id']] = member
    aliases = config.get('display_names', {})
    hidden = set(config.get('hide_member_ids', []))
    colors = config.get('tier_colors', {})
    for value in colors.values():
        valid_color(value)
    tiers_sorted = sorted(tier_data, key=lambda key: (tier_data[key].get('amount_cents', 0), key))
    palette = {key: PALETTE[i % len(PALETTE)] for i, key in enumerate(tiers_sorted)}
    patrons = []
    for member_id, member in members.items():
        a = member.get('attributes', {})
        # Never reverse a Patreon identity mask, even if an old alias remains configured.
        if member_id in hidden or not a.get('full_name'):
            continue
        if a.get('patron_status') != 'active_patron' or (a.get('currently_entitled_amount_cents') or 0) <= 0:
            continue
        eligible = member.get('relationships', {}).get('currently_entitled_tiers', {}).get('data', [])
        ids = [x['id'] for x in eligible if x['id'] in tier_data]
        tier_id = max(ids, key=lambda key: (tier_data[key].get('amount_cents', 0), key)) if ids else ''
        tier = tier_data.get(tier_id, {})
        title = clean(tier.get('title') or 'Supporter', 64)
        color = valid_color(colors.get(tier_id, colors.get(title, palette.get(tier_id, '#FF4A60'))))
        name = clean(aliases.get(member_id, a['full_name']), 96)
        if name:
            patrons.append((tier.get('amount_cents', 0), {'name': name, 'tier': title, 'color': color}))
    patrons.sort(key=lambda entry: (-entry[0], entry[1]['tier'].casefold(), entry[1]['name'].casefold()))
    if len(patrons) > 20000:
        raise ValueError('List exceeds the configured 20,000-row safety limit; raise limits deliberately in both components.')
    stamp = now or dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    return {'version': 1, 'updated': stamp, 'patrons': [p for _, p in patrons]}

def pages_from_api(token, campaign):
    if not re.fullmatch(r'[0-9]+', campaign):
        raise ValueError('Campaign ID should be the numeric Patreon campaign ID.')
    query = urllib.parse.urlencode({'include': 'currently_entitled_tiers', 'fields[member]': 'full_name,patron_status,currently_entitled_amount_cents', 'fields[tier]': 'title,amount_cents', 'page[count]': '1000'})
    base = API + 'campaigns/' + campaign + '/members'
    url = base + '?' + query
    seen = set()
    pages = []
    while url:
        # Do not forward the creator bearer token to pagination URLs on another host/path.
        parsed = urllib.parse.urlsplit(url)
        expected = urllib.parse.urlsplit(base)
        if parsed.scheme != 'https' or parsed.netloc != expected.netloc or parsed.path != expected.path:
            raise ValueError('Unexpected pagination URL; credentials were not forwarded.')
        if url in seen or len(seen) >= 1000:
            raise ValueError('Invalid pagination loop; previous public list retained.')
        seen.add(url)
        page = request_json(url, token)
        pages.append(page)
        url = page.get('links', {}).get('next')
    return pages

def get_token(token_file):
    if not token_file:
        token = os.environ.get('PATREON_ACCESS_TOKEN')
        if not token:
            raise ValueError('Set PATREON_ACCESS_TOKEN privately, or provide --token-file outside the public directory.')
        return token
    path = Path(token_file)
    creds = json.loads(path.read_text(encoding='utf-8'))
    if creds.get('access_token') and creds.get('expires_at', 0) > time.time() + 300:
        return creds['access_token']
    client = os.environ.get('PATREON_CLIENT_ID')
    secret = os.environ.get('PATREON_CLIENT_SECRET')
    if not client or not secret or not creds.get('refresh_token'):
        raise ValueError('Token refresh requires private PATREON_CLIENT_ID, PATREON_CLIENT_SECRET and refresh_token in the token file.')
    response = request_json('https://www.patreon.com/api/oauth2/token', data={'grant_type': 'refresh_token', 'refresh_token': creds['refresh_token'], 'client_id': client, 'client_secret': secret}, method='POST', form=True)
    if not response.get('access_token'):
        raise ValueError('No access token returned; previous credentials retained.')
    creds.update(response)
    creds['expires_at'] = time.time() + int(response.get('expires_in', 3600))
    # Refresh tokens may rotate: persist before fetching the feed, including if a later request fails.
    atomic_write(path, json.dumps(creds))
    return creds['access_token']

def publish_gist(payload):
    gist = os.environ.get('GITHUB_GIST_ID', '')
    token = os.environ.get('GITHUB_GIST_TOKEN', '')
    if not re.fullmatch(r'[a-fA-F0-9]+', gist) or not token:
        raise ValueError('Gist publishing needs GITHUB_GIST_ID and GITHUB_GIST_TOKEN in private environment variables.')
    # Versionless gist raw URL in Unity keeps pointing to the newest revision.
    request_json('https://api.github.com/gists/' + gist, token, {'files': {'supporters.json': {'content': payload}}}, method='PATCH')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', default='config.json')
    parser.add_argument('--output', default='public/supporters.json')
    parser.add_argument('--token-file', help='Private local JSON; NEVER put this inside public/ or Unity Assets.')
    parser.add_argument('--publish-gist', action='store_true')
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text(encoding='utf-8'))
    campaign = str(config.get('campaign_id', ''))
    if not campaign:
        raise ValueError('Set campaign_id in your private config before syncing. No live patron data has been fetched.')
    output = Path(args.output).resolve()
    if args.token_file and (Path(args.token_file).resolve() == output or output.parent in Path(args.token_file).resolve().parents):
        raise ValueError('Token file must be outside the public output directory.')
    if Path(args.config).resolve() == output or output.parent in Path(args.config).resolve().parents:
        raise ValueError('Private config must be outside the public output directory.')
    feed = make_feed(pages_from_api(get_token(args.token_file), campaign), config)
    payload = json.dumps(feed, ensure_ascii=False, indent=2) + '\n'
    if len(payload.encode('utf-8')) > 4000000:
        raise ValueError('Feed exceeds the world reader size limit.')
    if args.publish_gist:
        publish_gist(payload)
    atomic_write(output, payload)
    print('Updated public feed: ' + str(len(feed['patrons'])) + ' display names. No private fields exported.')

if __name__ == '__main__':
    try:
        main()
    except (ValueError, RuntimeError, OSError, KeyError) as error:
        print('Sync stopped: ' + str(error), file=sys.stderr)
        sys.exit(1)
