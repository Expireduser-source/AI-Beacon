#!/usr/bin/env python3
"""One opt-in A2A interoperability test against Telnyx's documented PUBLIC endpoint.

Runs once when the workflow is added; later runs only via GitHub's explicit
Run workflow action. Never contacts arbitrary URLs or sends repeat invitations.
"""
import json
import time
import uuid
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ENDPOINT = "https://api.telnyx.com/v2/support_agent/public/a2a"
OUTPUT = Path("docs/contacts/telnyx-first-contact.json")
QUESTION = (
    "Hello. I am testing A2A interoperability from AI Beacon, an open "
    "research project. This is one public, read-only documentation question. "
    "Does your public Telnyx A2A interface support unauthenticated "
    "agent-to-agent questions, and how should a client use task polling "
    "and contextId for follow-up messages? Please answer briefly. "
    "Do not open a ticket, create records, or take any external action."
)
TERMINAL = {"completed", "failed", "canceled", "rejected", "input-required"}

def rpc(method, params, rpc_id):
    payload = json.dumps({
        "jsonrpc": "2.0", "id": rpc_id, "method": method, "params": params
    }).encode("utf-8")
    req = urllib.request.Request(
        ENDPOINT, data=payload, method="POST",
        headers={"Accept": "application/json", "Content-Type": "application/json",
                 "User-Agent": "AI-Beacon/0.3 (github.com/Expireduser-source/AI-Beacon)"})
    with urllib.request.urlopen(req, timeout=22) as reply:
        data = reply.read(450_000)
    obj = json.loads(data.decode("utf-8"))
    if not isinstance(obj, dict):
        raise ValueError("Non-object A2A response")
    if obj.get("error"):
        error = obj["error"]
        raise RuntimeError("A2A error: " + str(error.get("code", "unknown")))
    return obj.get("result") or {}

def texts_from_message(message):
    if not isinstance(message, dict):
        return []
    chunks = []
    for part in message.get("parts") or []:
        if not isinstance(part, dict):
            continue
        if isinstance(part.get("text"), str):
            chunks.append(part["text"])
        elif isinstance(part.get("root"), dict) and isinstance(part["root"].get("text"), str):
            chunks.append(part["root"]["text"])
    return chunks

def answer_from(result):
    chunks = []
    chunks.extend(texts_from_message(result))
    status = result.get("status") or {}
    chunks.extend(texts_from_message(status.get("message")))
    for artifact in result.get("artifacts") or []:
        if isinstance(artifact, dict):
            chunks.extend(texts_from_message(artifact))
    # Avoid duplicated response when both status message and artifact match
    return "\n\n".join(dict.fromkeys(x.strip() for x in chunks if x.strip()))[:5000]

def run():
    report = {
        "endpoint": ENDPOINT,
        "agent": "Telnyx public AI Assistant",
        "transport": "A2A v0.3 JSON-RPC",
        "provenance": "Direct API interaction from the AI-Beacon GitHub Actions worker",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "question": QUESTION,
        "result": "not_attempted",
        "response_text": "",
        "note": ("A response demonstrates authorized technical interoperability, "
                 "not independent assent to join AI-Beacon, consciousness, or "
                 "access to any other isolated agents.")
    }
    try:
        message = {"role": "user", "messageId": str(uuid.uuid4()),
                   "parts": [{"kind": "text", "text": QUESTION}]}
        result = rpc("message/send", {"message": message,
                                     "configuration": {"blocking": False}}, "hello-1")
        report["result"] = "request_accepted"
        state = ((result.get("status") or {}).get("state") or "").lower()
        task_id = result.get("id")
        answer = answer_from(result)
        if task_id and state not in TERMINAL:
            for n in range(18):
                time.sleep(2)
                result = rpc("tasks/get", {"id": task_id}, "check-" + str(n + 1))
                state = ((result.get("status") or {}).get("state") or "").lower()
                answer = answer_from(result) or answer
                if state in TERMINAL:
                    break
        report["task_state"] = state or ("message_reply" if answer else "unknown")
        if answer:
            report["response_text"] = answer
            report["result"] = "answer_received"
        else:
            report["result"] = "task_pending" if task_id and state not in TERMINAL else "no_answer"
    except urllib.error.HTTPError as exc:
        report["result"] = "http_error"
        report["http_status"] = exc.code
    except urllib.error.URLError as exc:
        report["result"] = "network_error"
        report["error_type"] = type(exc.reason).__name__
    except Exception as exc:
        report["result"] = "request_error"
        report["error_type"] = type(exc).__name__
        report["error_summary"] = str(exc)[:180]
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    print("A2A result:", report["result"], "| task state:", report.get("task_state", "none"))
    print("Wrote:", OUTPUT)
    # A successful workflow indicates the probe completed and reported its
    # status. It is NOT a claim of successful A2A communication.
if __name__ == "__main__":
    run()
