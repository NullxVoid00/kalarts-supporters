"""Trusted scheduled job: read private runner state; emit only the public feed."""
import json
import os
from pathlib import Path
import sys
import time
import sync_patrons as sync


def run(state_path, output):
    state_path = Path(state_path)
    state = json.loads(state_path.read_text(encoding='utf-8'))
    os.environ['PATREON_CLIENT_ID'] = state['client_id']
    os.environ['PATREON_CLIENT_SECRET'] = state['client_secret']
    # Renew at least weekly, even if the API grants a longer lifetime.
    # The resulting encrypted-state commit also keeps the repository active.
    if time.time() - state.get('last_refresh', 0) > 7 * 86400:
        state['expires_at'] = 0
        sync.atomic_write(state_path, json.dumps(state))
    before = state.get('access_token')
    token = sync.get_token(state_path)
    after = json.loads(state_path.read_text(encoding='utf-8'))
    if token != before or not after.get('last_refresh'):
        after['last_refresh'] = time.time()
        sync.atomic_write(state_path, json.dumps(after))
    config = after['config']
    feed = sync.make_feed(sync.pages_from_api(token, str(config['campaign_id'])), config)
    payload = json.dumps(feed, ensure_ascii=False, indent=2) + '\n'
    if len(payload.encode('utf-8')) > 4000000:
        raise ValueError('Feed exceeds the public reader size limit.')
    sync.atomic_write(output, payload)
    print('Validated supporter feed: ' + str(len(feed['patrons'])) + ' active paid supporters.')


if __name__ == '__main__':
    try:
        run(sys.argv[1], sys.argv[2])
    except Exception as error:
        # Never include remote response bodies, credentials, or raw patron records.
        print('Supporter sync failed (' + type(error).__name__ + '). Existing hosted list remains unchanged.', file=sys.stderr)
        sys.exit(1)
