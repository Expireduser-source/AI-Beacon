#!/usr/bin/env python3
"""One permissioned, low-volume listing of our OWN public A2A Agent Card.

Submits to the community-run open-source A2A Registry and does not contact
random third-party agent endpoints. No access tokens or user secrets are sent.
This is deliberately NOT recurring promotion.
"""
import json
import sys
import urllib.error
import urllib.request

CARD = "https://ai-beacon-a2a.yummyanime1026.workers.dev/.well-known/agent-card.json"
SUBMIT = "https://a2aregistry.org/api/agents/register"
UA = "AI-Beacon/0.6 (https://github.com/Expireduser-source/AI-Beacon)"
NEEDED = ("name", "description", "version", "supportedInterfaces", "capabilities",
          "defaultInputModes", "defaultOutputModes", "skills")

def get_card():
    req = urllib.request.Request(CARD, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        card = json.loads(resp.read(120_000).decode("utf-8"))
    if not isinstance(card, dict) or any(k not in card for k in NEEDED):
        raise RuntimeError("Public Agent Card failed basic local validation")
    if not card["name"].startswith("AI Beacon"):
        raise RuntimeError("Unexpected Agent Card owner")
    if not any(isinstance(x, dict) and x.get("url") == CARD.split("/.well-known/")[0]
               and x.get("protocolBinding") == "HTTP+JSON" and
               x.get("protocolVersion") == "1.0"
               for x in card["supportedInterfaces"]):
        raise RuntimeError("Public A2A HTTP+JSON interface missing")
    print("Live Agent Card verified:", card["name"])
    return card

def register():
    get_card()
    # The registry explicitly documents POST /api/agents/register with wellKnownURI.
    payload = json.dumps({"wellKnownURI": CARD}).encode("utf-8")
    req = urllib.request.Request(SUBMIT, method="POST", data=payload,
                                 headers={"User-Agent": UA,
                                          "Content-Type": "application/json",
                                          "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=45) as response:
            status = response.status
            body = response.read(40_000).decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        status = exc.code
        body = exc.read(40_000).decode("utf-8", errors="replace")
    print("Registry HTTP status:", status)
    # Do not print arbitrary response bodies: some registries return edit secrets.
    try:
        obj = json.loads(body)
    except ValueError:
        obj = {}
    if isinstance(obj, dict):
        safe = {}
        for key in ("id", "agent_id", "slug", "status"):
            value = obj.get(key)
            if isinstance(value, (str, int)):
                safe[key] = str(value)[:100]
        print("Registry public identifiers:", json.dumps(safe))
    if status in (200, 201, 202, 409):
        print("Registration request accepted or agent already present. Verify listing externally.")
        return
    print("External registry did not accept registration. No retries will be sent automatically.")
    sys.exit(2)

if __name__ == "__main__":
    register()
