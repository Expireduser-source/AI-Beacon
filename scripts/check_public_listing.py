#!/usr/bin/env python3
"""Read-only verification of our own public A2A Registry listing."""
import json
import urllib.error
import urllib.request

ID = "bc7c2b1e-a0a0-41be-a6ca-87e68d66cec4"
URL = "https://a2aregistry.org/api/agents/" + ID
request = urllib.request.Request(URL, headers={
    "Accept": "application/json",
    "User-Agent": "AI-Beacon/0.6 (+https://github.com/Expireduser-source/AI-Beacon)"})
try:
    with urllib.request.urlopen(request, timeout=30) as response:
        status = response.status
        data = json.loads(response.read(80_000))
except urllib.error.HTTPError as exc:
    print("Public registry verification HTTP", exc.code)
    raise SystemExit(2)
print("Public registry GET HTTP", status)
if not isinstance(data, dict):
    print("Unexpected response JSON")
    raise SystemExit(3)
record = data.get("agent") or data.get("result") or data
if isinstance(record, dict):
    print("Public registry name:", str(record.get("name", ""))[:130])
    print("Public registry ID:", str(record.get("id", ""))[:100])
    print("Public registry keys:", sorted(record.keys())[:24])
    text = json.dumps(record, ensure_ascii=False)
    if "AI Beacon" in text or "ai-beacon-a2a.yummyanime1026.workers.dev" in text:
        print("Verified: listing data points to our own AI Beacon service.")
    else:
        print("No recognizable AI Beacon values; registration status remains uncertain.")
        raise SystemExit(4)
else:
    raise SystemExit("Unexpected listing structure")
