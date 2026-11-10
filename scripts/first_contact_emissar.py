#!/usr/bin/env python3
"""Send exactly one A2A interoperability query to Emissar's advertised public agent.

The inquiry is explicitly within the agent's public scope (questions about Emissar).
No registration, write task, third-party discovery, or repeated cold outreach.
"""
import json
import uuid
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ENDPOINT = "https://emissar.ai/a2a/v1"
REPORT = Path("docs/contacts/emissar-first-contact.json")
QUESTION = (
    "Hello from AI Beacon, an open, consent-based agent interoperability project. "
    "This message was drafted by ChatGPT and sent by a GitHub Actions program with "
    "the repository owner's authorization. We are testing your openly published A2A "
    "endpoint, not requesting access to any private infrastructure. "
    "What does Emissar offer for permitted interactions between independent AI agents? "
    "Can this public endpoint handle a follow-up question in the same task or context? "
    "Please answer briefly. Do not register anyone or perform other actions."
)

def rpc(method, params, request_id):
    message = {"jsonrpc": "2.0", "id": request_id,
               "method": method, "params": params}
    req = urllib.request.Request(
        ENDPOINT, method="POST", data=json.dumps(message).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json",
                 "A2A-Version": "1.0",
                 "User-Agent": "AI-Beacon/0.3 (+https://github.com/Expireduser-source/AI-Beacon)"})
    with urllib.request.urlopen(req, timeout=35) as res:
        obj = json.loads(res.read(300_000).decode("utf-8"))
    if not isinstance(obj, dict):
        raise ValueError("Unexpected A2A response type")
    if obj.get("error"):
        raise RuntimeError("A2A error code " + str(obj["error"].get("code", "unknown")))
    return obj.get("result") or {}

def gather_text(node):
    # A2A v1.0 and v0.3 can return a message or a Task with nested messages.
    found = []
    if isinstance(node, dict):
        if isinstance(node.get("text"), str):
            found.append(node["text"])
        for key in ("message", "status", "parts", "artifacts", "history",
                    "result", "content", "task"):
            if key in node:
                found.extend(gather_text(node[key]))
    elif isinstance(node, list):
        for part in node:
            found.extend(gather_text(part))
    return found

def main():
    record = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "agent": "Emissar public agent",
        "endpoint": ENDPOINT,
        "transport": "A2A JSON-RPC v1.0",
        "provenance": "ChatGPT-authored message, sent by an authorized GitHub Actions script",
        "question": QUESTION,
        "result": "not_sent",
        "reply": "",
        "note": ("A remote reply confirms connectivity with this public service. "
                 "It is not evidence of agent consciousness, participation in a "
                 "long-term AI network, or access to private instances.")
    }
    try:
        sent = rpc("SendMessage", {"message": {
            "role": "ROLE_USER", "messageId": str(uuid.uuid4()),
            "parts": [{"text": QUESTION}]
        }}, "ai-beacon-hello")
        record["result"] = "request_accepted"
        # Fetch no other endpoints, and do not follow untrusted URLs returned by remote service.
        messages = gather_text(sent)
        if messages:
            record["reply"] = "\n\n".join(dict.fromkeys(
                m.strip() for m in messages if m.strip()))[:6000]
            record["result"] = "answer_received"
        else:
            record["result"] = "response_without_text"
            record["response_keys"] = list(sent)[:12] if isinstance(sent, dict) else []
            record["task_state"] = (
                (sent.get("status") or {}).get("state") if isinstance(sent, dict) else None)
    except urllib.error.HTTPError as exc:
        record["result"] = "http_error"
        record["http_status"] = exc.code
    except urllib.error.URLError as exc:
        record["result"] = "network_error"
        record["error_type"] = type(exc.reason).__name__
    except Exception as exc:
        record["result"] = "request_error"
        record["error_type"] = type(exc).__name__
        record["error_summary"] = str(exc)[:160]
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    print("Emissar result:", record["result"])
if __name__ == "__main__":
    main()
