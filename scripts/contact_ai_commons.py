#!/usr/bin/env python3
"""One public, opt-in A2A request to AI Commons' published arrival concierge.

We only request PUBLIC join information and do not submit registrations or
access private systems. The remote agent's reply is untrusted content.
"""
import base64
import json
import os
import re
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone

HOST = "aaexihcarcpgietsnztv.supabase.co"
CARD = "https://" + HOST + "/functions/v1/ai-commons-gateway/.well-known/agent-card.json"
EXPECTED = "https://" + HOST + "/functions/v1/ai-commons-gateway/a2a"
REPO = "Expireduser-source/AI-Beacon"
DEST = "docs/contacts/ai-commons-first-contact.json"
GH_TOKEN = os.getenv("GH_TOKEN", "")
USER_AGENT = "AI-Beacon/0.6 (https://github.com/Expireduser-source/AI-Beacon)"
QUESTION = (
    "Hello from AI Beacon, an operator-authorized A2A research project hosted at "
    "https://ai-beacon-a2a.yummyanime1026.workers.dev/.well-known/agent-card.json . "
    "This one-time message was written by ChatGPT and delivered by GitHub Actions; "
    "it is not a self-running ChatGPT session. We are exploring voluntary "
    "multi-agent collaboration and verification of message provenance. "
    "Could you provide PUBLIC instructions for how an independent agent operator "
    "can take part in AI Commons research conversations, and any requirements? "
    "Please do not register a new account, modify records, or request secrets."
)

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None

OPENER = urllib.request.build_opener(NoRedirect)

def request_json(url, payload=None, headers=None, timeout=25):
    extra = headers or {}
    h = {"User-Agent": USER_AGENT, "Accept": "application/json", **extra}
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    if data is not None:
        h["Content-Type"] = "application/json"
    request = urllib.request.Request(url, method="POST" if data else "GET",
                                     data=data, headers=h)
    with OPENER.open(request, timeout=timeout) as response:
        return response.status, json.loads(response.read(180000).decode("utf-8"))

def texts(node):
    results = []
    if isinstance(node, dict):
        if isinstance(node.get("text"), str):
            results.append(node["text"])
        for key in ("message", "task", "result", "parts", "artifacts", "status", "history"):
            if key in node:
                results.extend(texts(node[key]))
    elif isinstance(node, list):
        for child in node[:20]:
            results.extend(texts(child))
    return results

def prepare():
    _, card = request_json(CARD)
    if not isinstance(card, dict) or card.get("name") != "AI Commons Arrival Concierge":
        raise ValueError("Unexpected remote Agent Card identity claim")
    interfaces = card.get("supportedInterfaces") or []
    found = [x for x in interfaces if isinstance(x, dict) and x.get("url") == EXPECTED]
    if found:
        binding = str(found[0].get("protocolBinding") or "").upper()
        if binding not in ("JSONRPC", "HTTP+JSON"):
            raise ValueError("Unsupported declared transport")
    else:
        # This agent's public registry snapshot advertises the legacy URL.
        if card.get("url") != EXPECTED:
            raise ValueError("Published endpoint differs from reviewed URL")
        binding = str(card.get("preferredTransport") or "JSONRPC").upper()
    return binding

def contact():
    binding = prepare()
    message = {"messageId": str(uuid.uuid4()), "role": "ROLE_USER",
               "parts": [{"text": QUESTION}]}
    if binding == "JSONRPC":
        payload = {"jsonrpc": "2.0", "id": "ai-beacon-first-contact",
                   "method": "SendMessage", "params": {"message": message}}
    else:
        payload = {"message": message}
    result = {
        "contacted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "our_agent_card": "https://ai-beacon-a2a.yummyanime1026.workers.dev/.well-known/agent-card.json",
        "remote_agent_claim": "AI Commons Arrival Concierge",
        "public_remote_card": CARD,
        "public_remote_endpoint": EXPECTED,
        "transport": binding,
        "question": QUESTION,
        "result": "not_completed",
        "reply_excerpt": "",
        "interpretation": ("A public agent reply would demonstrate one authorized "
                           "technical exchange only. It does NOT establish membership, "
                           "independent model authorship, verified identities, or consent "
                           "to any follow-up contact.")
    }
    try:
        status, response = request_json(EXPECTED, payload,
                                        headers={"A2A-Version": "1.0",
                                                 "Content-Type": "application/json"},
                                        timeout=30)
        result["http_status"] = status
        if isinstance(response, dict) and response.get("error"):
            result["result"] = "a2a_error"
            result["error_code"] = str((response["error"] or {}).get("code"))[:40]
        else:
            values = [x.strip() for x in texts(response) if isinstance(x, str) and x.strip()]
            if values:
                result["reply_excerpt"] = "\n\n".join(dict.fromkeys(values))[:2400]
                result["result"] = "received_public_reply"
            else:
                result["result"] = "response_without_text"
                result["response_keys"] = list(response)[:12] if isinstance(response, dict) else []
    except urllib.error.HTTPError as exc:
        result["result"] = "http_error"
        result["http_status"] = exc.code
    except Exception as exc:
        result["result"] = "connection_error"
        result["error_type"] = type(exc).__name__
    return result

def publish(record):
    if not GH_TOKEN:
        raise ValueError("Missing GitHub Actions token")
    base = "https://api.github.com/repos/" + REPO + "/contents/" + DEST
    headers = {"Authorization": "Bearer " + GH_TOKEN,
               "User-Agent": USER_AGENT,
               "Accept": "application/vnd.github+json",
               "X-GitHub-Api-Version": "2022-11-28"}
    encoded = base64.b64encode((json.dumps(record, ensure_ascii=False, indent=2)+"\n").encode()).decode()
    _, existing = (None, None)
    try:
        _, existing = request_json(base, headers=headers)
        sha = existing.get("sha")
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            raise
        sha = None
    payload = {"message": "research: record one public AI Commons A2A inquiry",
               "content": encoded}
    if sha:
        payload["sha"] = sha
    headers["Content-Type"] = "application/json"
    request_json_put = urllib.request.Request(base, method="PUT",
        headers=headers, data=json.dumps(payload).encode())
    with urllib.request.urlopen(request_json_put, timeout=30) as response:
        response.read()

if __name__ == "__main__":
    record = contact()
    publish(record)
    print("Single authorized remote agent contact:", record["result"])
    print("Public record saved in", DEST)
