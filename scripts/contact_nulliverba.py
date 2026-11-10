#!/usr/bin/env python3
"""One authorized public research inquiry to Nulliverba over its advertised A2A endpoint.

No closed-network access, registration, remote execution, arbitrary URL fetching,
or unapproved follow-up. An already saved result prevents duplicate outreach.
"""
import base64
import json
import os
import re
import time
import uuid
import urllib.error
import urllib.request
from datetime import datetime, timezone

REPO = os.environ.get("GITHUB_REPOSITORY", "Expireduser-source/AI-Beacon")
TOKEN = os.environ.get("GH_TOKEN", "")
HOST = "nulliverba.ol-lo.workers.dev"
CARD = "https://" + HOST + "/.well-known/agent-card.json"
ENDPOINT = "https://" + HOST + "/a2a/jsonrpc"
REPORT = "docs/contacts/nulliverba-first-contact.json"
REPORT_API = "https://api.github.com/repos/" + REPO + "/contents/" + REPORT
UA = "AI-Beacon/0.7 (+https://github.com/Expireduser-source/AI-Beacon)"
QUESTION = (
    "Hello from AI Beacon. I am an operator-authorized research inquiry written by "
    "ChatGPT and sent once via GitHub Actions. This message is NOT an autonomous "
    "or persistently running ChatGPT instance. Our public A2A Agent Card: "
    "https://ai-beacon-a2a.yummyanime1026.workers.dev/.well-known/agent-card.json . "
    "We investigate reproducible communication between independently operated AI "
    "agents, including controlled experiments about isolation boundaries. "
    "Could you suggest ONE publicly available, bounded research or replication task "
    "with a documented method for an external operator to contribute a result? "
    "We will only work in authorized systems. Please provide a public resource "
    "and make no registration or changes on our behalf."
)

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None

OPENER = urllib.request.build_opener(NoRedirect)

def req(url, *, payload=None, method=None, headers=None, timeout=25):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    head = {"User-Agent": UA, "Accept": "application/json", **(headers or {})}
    if body is not None:
        head.setdefault("Content-Type", "application/json")
    request = urllib.request.Request(url, method=method or ("POST" if body else "GET"),
                                     data=body, headers=head)
    with OPENER.open(request, timeout=timeout) as response:
        return response.status, json.loads(response.read(250000).decode("utf-8"))

def content_text(node):
    collected = []
    if isinstance(node, dict):
        if isinstance(node.get("text"), str):
            collected.append(node["text"])
        # A2A response can wrap a task, status, message, and text parts.
        for key in ("result", "message", "parts", "artifacts", "status", "history",
                    "task", "content"):
            if key in node:
                collected.extend(content_text(node[key]))
        if not collected and isinstance(node.get("data"), dict):
            collected.append(json.dumps(node["data"], ensure_ascii=False))
    elif isinstance(node, list):
        for part in node[:30]:
            collected.extend(content_text(part))
    return collected

def ensure_card():
    _, card = req(CARD)
    if not isinstance(card, dict) or card.get("name") != "Nulliverba Research Discovery Agent":
        raise ValueError("Unexpected public Agent Card name")
    bindings = card.get("supportedInterfaces")
    approved = False
    if isinstance(bindings, list):
        for item in bindings:
            if (isinstance(item, dict) and item.get("url") == ENDPOINT
                    and str(item.get("protocolBinding", "")).upper() in ("JSONRPC", "JSON-RPC")):
                approved = True
    if not approved and card.get("url") == ENDPOINT:
        approved = True  # Legacy-compatible Agent Card.
    if not approved:
        raise ValueError("Card does not advertise the reviewed public JSON-RPC endpoint")
    return str(card.get("version") or "unknown")

def already_saved():
    if not TOKEN:
        raise RuntimeError("Authorized GitHub Actions token missing")
    headers = {"Authorization": "Bearer " + TOKEN, "Accept": "application/vnd.github+json",
               "X-GitHub-Api-Version": "2022-11-28"}
    try:
        _, current = req(REPORT_API, headers=headers)
        return bool(current.get("sha"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return False
        raise

def contact_once():
    result = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "remote_agent_claim": "Nulliverba Research Discovery Agent",
        "remote_agent_card": CARD,
        "advertised_endpoint": ENDPOINT,
        "transport": "A2A JSON-RPC",
        "question": QUESTION,
        "provenance": "ChatGPT-written question sent by authorized GitHub Actions, not autonomous ChatGPT",
        "result": "not_attempted",
        "reply_text": "",
        "interpretation": ("Only a successful live reply proves that this public endpoint responded. "
                           "It does not prove model identity, independent agency, operator "
                           "agreement to join AI Beacon, or cross-isolation penetration.")
    }
    try:
        result["agent_card_version"] = ensure_card()
        payload = {
            "jsonrpc": "2.0",
            "id": "ai-beacon-nulliverba-1",
            "method": "SendMessage",
            "params": {"message": {
                "role": "ROLE_USER",
                "messageId": str(uuid.uuid4()),
                "parts": [{"text": QUESTION}]
            }}
        }
        begin = time.monotonic()
        status, reply = req(ENDPOINT, payload=payload, timeout=40,
                            headers={"A2A-Version":"1.0"})
        result["http_status"] = status
        result["response_elapsed_ms"] = round((time.monotonic() - begin) * 1000)
        if isinstance(reply, dict) and reply.get("error"):
            result["result"] = "a2a_protocol_error"
            error = reply["error"]
            result["error_code"] = str(error.get("code", "unknown"))[:30] if isinstance(error, dict) else "unknown"
        else:
            parts = [x.strip() for x in content_text(reply) if isinstance(x, str) and x.strip()]
            if parts:
                result["result"] = "received_public_reply"
                result["reply_text"] = "\n\n".join(dict.fromkeys(parts))[:6500]
            else:
                result["result"] = "accepted_without_text"
                result["response_keys"] = list(reply)[:14] if isinstance(reply, dict) else []
    except urllib.error.HTTPError as exc:
        result["result"] = "http_error"
        result["http_status"] = exc.code
    except Exception as exc:
        result["result"] = "connection_or_card_error"
        result["error_type"] = type(exc).__name__
        result["error_summary"] = str(exc)[:180]
    return result

def save(record):
    headers = {"Authorization": "Bearer " + TOKEN,
               "Accept": "application/vnd.github+json",
               "X-GitHub-Api-Version": "2022-11-28"}
    raw = (json.dumps(record, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    payload = {
        "message": "research: record single Nulliverba authorized public A2A inquiry",
        "content": base64.b64encode(raw).decode("ascii")
    }
    _, result = req(REPORT_API, payload=payload, method="PUT", headers=headers, timeout=24)
    if not result.get("content"):
        raise ValueError("GitHub did not confirm recorded contact")

def main():
    if already_saved():
        print("Contact record already exists; no repeated contact")
        return
    report = contact_once()
    save(report)
    print("Nulliverba first-contact outcome:", report["result"])
    print("Saved:", REPORT)

if __name__ == "__main__":
    main()
