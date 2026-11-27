"""Build Club Abyssal's opt-in entitlement feed from current campaign membership."""
import urllib.error
import json
import re
import time
import urllib.request
from html.parser import HTMLParser

PROFILE = re.compile(r"usr_[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$")

class ProfileTitle(HTMLParser):
    title = None
    description = None
    def handle_starttag(self, tag, attrs):
        fields = dict(attrs)
        if tag == "meta" and (fields.get("name") or fields.get("property")) == "og:title":
            self.title = fields.get("content")
        if tag == "meta" and (fields.get("name") or fields.get("property")) == "og:description":
            self.description = fields.get("content")

def profile_name(identifier):
    if not PROFILE.fullmatch(identifier):
        raise ValueError("Invalid VRChat profile ID")
    url = "https://vrchat.com/home/user/" + identifier
    req = urllib.request.Request(url, headers={"User-Agent": "KalArts-VerifiedHosts/1.0 (github.com/NullxVoid00/kalarts-supporters)"})
    with urllib.request.urlopen(req, timeout=8) as response:
        if response.geturl().split("?")[0].rstrip("/") != url:
            return None
        parser = ProfileTitle()
        parser.feed(response.read(180000).decode("utf-8"))
    name = parser.title
    return name if name and name.lower() not in ("vrchat", "vrchat home", "user") and len(name) <= 64 and parser.description == "VRChat user " + name else None

def make_hosts(pages, raw_links, now=None, lookup=profile_name):
    now = int(time.time()) if now is None else now
    links = json.loads(raw_links or "[]")
    if not isinstance(links, list) or len(links) > 1000:
        raise ValueError("Invalid private mapping")
    paid = {row["id"] for page in pages for row in page.get("data", [])
            if row.get("type") == "member"
            and row.get("attributes", {}).get("patron_status") == "active_patron"
            and (row.get("attributes", {}).get("currently_entitled_amount_cents") or 0) > 0}
    seen_members, seen_accounts, names = set(), set(), set()
    stop = time.monotonic() + 50
    for row in links:
        mid, uid = row["member"], row["account"]
        if not PROFILE.fullmatch(uid) or not isinstance(mid, str) or not mid.isdigit() or mid in seen_members or uid in seen_accounts:
            raise ValueError("Duplicate or invalid private mapping")
        seen_members.add(mid)
        seen_accounts.add(uid)
        if mid in paid and time.monotonic() < stop:
            try:
                name = lookup(uid)
            except (OSError, TimeoutError, UnicodeError):
                continue
            if name:
                names.add(name)
    return {"version": 1, "issued": now, "expires": now + 6 * 3600, "hosts": sorted(names)}
