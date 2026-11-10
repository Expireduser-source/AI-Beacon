#!/usr/bin/env python3
"""Recover an accurate audit record from four already posted public Issue comments.

The original runner's hash-chain timestamps were lost after a Git push conflict.
This program creates a NEW, independently verifiable chain over the observed
GitHub comments and explicitly preserves the distinction.
"""
import base64
import hashlib
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

REPO = os.environ.get("GITHUB_REPOSITORY", "Expireduser-source/AI-Beacon")
TOKEN = os.environ.get("GH_TOKEN", "")
DEST = Path("docs/labs/first-peer-dialogue.json")
API = "https://api.github.com/repos/" + REPO
PATTERN = re.compile(
    r"^<!-- ai-beacon-two-model-lab -->\s*\n"
    r"Independent local model: ([^\r\n]+)\s*\n\s*\n"
    r"([\s\S]*?)\s*\n\s*\nHash SHA-256: ([a-f0-9]{64})"
    r"\s*\nRecorded by GitHub Actions\.",
    re.MULTILINE
)


def req(url, payload=None, method="GET"):
    headers = {"Authorization": "Bearer " + TOKEN,
               "Accept": "application/vnd.github+json",
               "X-GitHub-Api-Version": "2022-11-28",
               "User-Agent": "AI-Beacon/audit-recovery"}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        url, headers=headers, method=method,
        data=json.dumps(payload).encode("utf-8") if payload is not None else None)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read(600000).decode("utf-8"))


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def recover(comments):
    relevant = []
    for comment in comments:
        if ((comment.get("user") or {}).get("login") != "github-actions[bot]"):
            continue
        match = PATTERN.search(str(comment.get("body") or ""))
        if not match:
            continue
        model, text, old_hash = match.groups()
        if model not in ("qwen2.5:1.5b-instruct", "gemma3:1b"):
            continue
        relevant.append({
            "model": model, "text": text.strip(),
            "original_hash_reported_by_runner": old_hash,
            "github_comment_id": comment.get("id"),
            "github_comment_url": comment.get("html_url"),
            "timestamp": comment.get("created_at"),
        })
    relevant.sort(key=lambda x: x["github_comment_id"])
    if len(relevant) != 4:
        raise ValueError("Expected exactly four authentic GitHub bot comments")
    if [x["model"] for x in relevant] != [
            "qwen2.5:1.5b-instruct", "gemma3:1b",
            "qwen2.5:1.5b-instruct", "gemma3:1b"]:
        raise ValueError("Unexpected model ordering")
    previous = "0" * 64
    result = []
    for index, entry in enumerate(relevant, 1):
        entry = {"index": index, "previous": previous, **entry}
        entry["sha256"] = hashlib.sha256(canonical(entry)).hexdigest()
        result.append(entry)
        previous = entry["sha256"]
    return {
        "status": "recovered_from_public_issue_comments",
        "source": "https://github.com/" + REPO + "/issues/4",
        "messages": result,
        "message_count": 4,
        "reconstructed_hash_chain_valid": True,
        "original_runner_hash_chain_verified": False,
        "important_limitation": (
            "The original GitHub Action generated four independent model replies, "
            "but a concurrent repository update blocked its transcript commit. "
            "This new chain covers text and GitHub metadata copied from the "
            "actual published comments. Original timestamps used in the first "
            "chain were not preserved, so original hashes cannot be revalidated. "
            "Neither chain proves true model identity."),
    }


def publish(report):
    if not TOKEN:
        raise RuntimeError("Missing GitHub token")
    DEST.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(report, indent=2, ensure_ascii=False).encode("utf-8") + b"\n"
    DEST.write_bytes(raw)
    endpoint = API + "/contents/" + str(DEST)
    for attempt in range(5):
        try:
            current = req(endpoint)
            sha = current["sha"]
            decoded = base64.b64decode(current["content"])
            if decoded == raw:
                print("Audit transcript already published")
                return
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                raise
            sha = None
        data = {"message": "research: recover Qwen-Gemma transcript from observed comments",
                "content": base64.b64encode(raw).decode("ascii")}
        if sha:
            data["sha"] = sha
        try:
            req(endpoint, payload=data, method="PUT")
            print("Recovered transcript published")
            return
        except urllib.error.HTTPError as exc:
            if exc.code not in (409, 422) or attempt == 4:
                raise


def main():
    if not TOKEN:
        raise RuntimeError("Missing GitHub token")
    comments = req(API + "/issues/4/comments?per_page=100")
    report = recover(comments)
    publish(report)
    print("Recovered", report["message_count"], "messages; new chain only")


if __name__ == "__main__":
    main()
