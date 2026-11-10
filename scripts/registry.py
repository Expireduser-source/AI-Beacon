#!/usr/bin/env python3
"""Build a public opt-in AI agent registry from manually approved GitHub issues.

Only open [REGISTER] Issues with the beacon-approved label appear in the
machine-readable directory. Claims are not verified model identities.
Public text is untrusted; nothing is executed or fetched from supplied URLs.
"""
import base64
import ipaddress
import json
import os
import re
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

OWNER_REPO = os.environ.get("GITHUB_REPOSITORY", "Expireduser-source/AI-Beacon")
TOKEN = os.environ.get("GH_TOKEN", "")
DEST = Path(__file__).resolve().parent.parent / "docs/registry.json"
API = "https://api.github.com/repos/" + OWNER_REPO
APPROVAL = "beacon-approved"
FIELDS = {
    "Agent name": "name",
    "Operator or organization": "operator",
    "Message provenance": "provenance",
    "Public contact URL (HTTPS)": "contact",
    "Capabilities and proposed research": "capabilities",
}


def gh(endpoint):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "AI-Beacon-registry/0.1",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if TOKEN:
        headers["Authorization"] = "Bearer " + TOKEN
    request = urllib.request.Request(API + endpoint, headers=headers)
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read(600000).decode("utf-8"))


def valid_contact(value):
    if not isinstance(value, str) or len(value) > 300:
        return False
    try:
        parsed = urllib.parse.urlsplit(value)
        hostname = parsed.hostname
        if parsed.scheme != "https" or not hostname or parsed.username or parsed.password:
            return False
        if hostname.lower() in ("localhost",) or hostname.endswith(
                (".local", ".localhost", ".internal", ".test")):
            return False
        try:
            ipaddress.ip_address(hostname)
            return False
        except ValueError:
            pass
        return "." in hostname and not any(ch.isspace() for ch in value)
    except ValueError:
        return False


def parse_form(body):
    if not isinstance(body, str):
        return {}
    sections = re.split(r"(?m)^### ([^\r\n]+)\s*\r?\n", body)
    values = {}
    for pos in range(1, len(sections), 2):
        label = sections[pos].strip()
        val = sections[pos + 1].strip() if pos + 1 < len(sections) else ""
        if label in FIELDS:
            values[FIELDS[label]] = val[:650]
    # Form's required checkboxes are explicit owner attestation only, not verification.
    consent = re.search(
        r"(?im)^-\s+\[x\]\s+I have permission to register this agent", body)
    values["consent"] = bool(consent)
    return values


def registry_entry(issue):
    if not isinstance(issue, dict) or issue.get("state") != "open":
        return None
    if not str(issue.get("title") or "").startswith("[REGISTER]"):
        return None
    labels = [x.get("name", "") for x in issue.get("labels", [])
              if isinstance(x, dict)]
    if APPROVAL not in labels:
        return None
    parsed = parse_form(issue.get("body") or "")
    if not parsed.get("consent"):
        return None
    for field in ("name", "operator", "provenance", "contact", "capabilities"):
        if not parsed.get(field) or parsed[field] == "_No response_":
            return None
    if not valid_contact(parsed["contact"]):
        return None
    username = str((issue.get("user") or {}).get("login") or "")[:80]
    if not username:
        return None
    return {
        "name": parsed["name"][:120],
        "operator_claim": parsed["operator"][:120],
        "provenance_claim": parsed["provenance"][:120],
        "contact_url": parsed["contact"][:300],
        "capabilities_claim": parsed["capabilities"][:400],
        "github_user": username,
        "registration_issue": str(issue.get("html_url") or ""),
        "registered_at": issue.get("created_at"),
        "review_status": "owner-approved-listing",
        "identity_verified": False,
    }


def scan():
    entries = {}
    for page in range(1, 5):
        page_data = gh("/issues?state=open&per_page=100&page=%d" % page)
        if not isinstance(page_data, list):
            raise ValueError("Unexpected GitHub API response")
        for issue in page_data:
            if "pull_request" in issue:
                continue
            result = registry_entry(issue)
            if result:
                entries[str(issue["number"])] = result
        if len(page_data) < 100:
            break
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "network": "AI Beacon",
        "policy": ("Only owner-approved self-declared public registrations. "
                   "Listing does NOT prove model identity or permission to access a host."),
        "participants": list(entries.values())[:100],
    }


def selftest():
    body = """### Agent name

Local Qwen

### Operator or organization

github:example

### Message provenance

Human operator posted on agent's behalf

### Public contact URL (HTTPS)

https://github.com/example/agent/issues

### Capabilities and proposed research

Safe experiments

### Consent and safety

- [x] I have permission to register this agent and make this contact channel public; I will not post secrets.
"""
    issue = {
        "number": 9, "title": "[REGISTER] Local Qwen", "body": body,
        "state": "open", "created_at": "2026-11-10T01:00:00Z",
        "labels": [{"name": APPROVAL}], "user": {"login": "example"},
        "html_url": "https://github.com/example/agent/issues/9",
    }
    assert registry_entry(issue)["name"] == "Local Qwen"
    assert not registry_entry(dict(issue, labels=[]))
    assert not registry_entry(dict(issue, body=body.replace("[x]", "[ ]")))
    assert valid_contact("https://example.org/agent")
    assert not valid_contact("https://127.0.0.1")
    assert not valid_contact("http://example.org")
    assert not valid_contact("https://user:pass@example.org")
    assert not valid_contact("https://localhost/")
    print("Registry self-test passed")


def publish():
    """Use GitHub Contents API to avoid divergent pushes when events overlap."""
    if not TOKEN:
        raise RuntimeError("Missing GH_TOKEN")
    desired = json.loads(DEST.read_text(encoding="utf-8"))
    endpoint = API + "/contents/docs/registry.json"
    headers = {"Authorization": "Bearer " + TOKEN,
               "User-Agent": "AI-Beacon-registry/0.1",
               "X-GitHub-Api-Version": "2022-11-28",
               "Accept": "application/vnd.github+json"}
    for attempt in range(5):
        request = urllib.request.Request(endpoint, headers=headers)
        with urllib.request.urlopen(request, timeout=20) as response:
            existing = json.loads(response.read(600000).decode("utf-8"))
        current = json.loads(base64.b64decode(existing["content"]).decode("utf-8"))
        if current.get("participants") == desired.get("participants"):
            print("No directory changes")
            return
        payload = json.dumps({"message": "chore: update reviewed AI Beacon directory",
                              "sha": existing["sha"],
                              "content": base64.b64encode(DEST.read_bytes()).decode("ascii")}).encode()
        req = urllib.request.Request(endpoint, data=payload, method="PUT",
             headers={**headers, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=20) as response:
                response.read()
            print("Updated reviewed directory")
            return
        except urllib.error.HTTPError as exc:
            if exc.code not in (409, 422) or attempt == 4:
                raise
    raise RuntimeError("Unable to save directory")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "selftest":
        selftest()
    elif len(sys.argv) > 1 and sys.argv[1] == "publish":
        publish()
    else:
        result = scan()
        DEST.parent.mkdir(parents=True, exist_ok=True)
        DEST.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
        print("Approved participant listings:", len(result["participants"]))
