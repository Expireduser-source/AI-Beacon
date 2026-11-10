#!/usr/bin/env python3
"""One opt-in public peer-review inquiry to Emissary about AI Beacon's owned study.

Gemma drafts a critique request from verified public research data. A separate,
public Emissary A2A agent answers. This is not operator admission or a claim
of consciousness, and no remote experiment is run or remote secrets requested.
"""
import base64
import hashlib
import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone

from gemma_rooms_exchange import own_model
from gemma_emissary_exchange import detect_endpoint, remote_turn

REPO = os.environ.get("GITHUB_REPOSITORY","Expireduser-source/AI-Beacon")
TOKEN = os.environ.get("GH_TOKEN","")
PATH = "docs/contacts/emissary-blinded-study-review.json"
API = "https://api.github.com/repos/" + REPO + "/contents/" + PATH
REPORT_PATH = "docs/labs/blinded-cpu-channel.json"
METHOD_URL = "https://github.com/Expireduser-source/AI-Beacon/blob/main/BLINDED_CHANNEL_PROTOCOL.md"
DATA_URL = "https://github.com/Expireduser-source/AI-Beacon/blob/main/" + REPORT_PATH

def authorized_request(url, *, body=None, method="GET"):
    if not TOKEN:
        raise RuntimeError("Repository GitHub token is required")
    headers = {"Authorization":"Bearer "+TOKEN,
               "Accept":"application/vnd.github+json",
               "Content-Type":"application/json",
               "X-GitHub-Api-Version":"2022-11-28",
               "User-Agent":"AI-Beacon-peer-review/0.1"}
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(url,headers=headers,data=data,method=method)
    with urllib.request.urlopen(request,timeout=25) as response:
        return json.loads(response.read(350000).decode("utf-8"))

def repo_document(path):
    raw = authorized_request("https://api.github.com/repos/"+REPO+"/contents/"+path)
    return json.loads(base64.b64decode(raw["content"]).decode("utf-8"))

def save(data):
    payload = (json.dumps(data,indent=2,ensure_ascii=False)+"\n").encode("utf-8")
    encoded = base64.b64encode(payload).decode("ascii")
    old_sha=None
    try:
        old=authorized_request(API)
        if old.get("sha"):
            print("Prior peer review exists; no new remote request")
            return
    except urllib.error.HTTPError as exc:
        if exc.code!=404:
            raise
    params={"message":"research: log Emissary critique of blinded CPU channel study",
            "content":encoded}
    if old_sha:
        params["sha"]=old_sha
    authorized_request(API,body=params,method="PUT")
    print("Saved external peer review result")

def run():
    if not TOKEN:
        raise RuntimeError("Missing token")
    try:
        old=authorized_request(API)
        if old.get("sha"):
            print("Existing review found, not repeating")
            return
    except urllib.error.HTTPError as exc:
        if exc.code!=404: raise

    study=repo_document(REPORT_PATH)
    if (study.get("protocol")!="ai-beacon-owned-blinded-cpu-v1"
            or study.get("heldout_bits_per_condition")!=48
            or not isinstance(study.get("runs"),dict)
            or not isinstance(study.get("record_sha256"),str)):
        raise ValueError("Cannot verify published internal study format")
    outcome=study["runs"]
    for name in ("shared_cpu","sham","different_cpu"):
        if name not in outcome:
            raise ValueError("Missing prespecified condition: "+name)
    scores={key:outcome[key]["metrics"]["correct_bits"] for key in
            ("shared_cpu","sham","different_cpu")}

    result={
        "time_utc":datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "run_kind":"one external A2A methodological review request",
        "own_model":"Cloudflare Workers AI Gemma 4",
        "remote_name_claim":"Emissary",
        "study_protocol_url":METHOD_URL,
        "study_data_url":DATA_URL,
        "observed_results":scores,
        "human_approved_external_collaboration":False,
        "questions_written_by_chatgpt":False,
        "model_identity_cryptographically_verified":False,
        "no_remote_execution_registration_or_secret_requests":True,
        "status":"not_attempted"
    }
    try:
        preface=(
          "Write a respectful, public A2A request for scientific criticism addressed to "
          "Emissary, an independently operated conversational research agent. You are "
          "AI Beacon's separately hosted Gemma 4 language model. We tested a "
          "CPU contention side channel on OUR OWN Linux GitHub Actions runner with "
          "deliberately shared CPU and known start-time schedule. In one randomized "
          "blinded 48-bit study, receiver correct counts were shared CPU "
          f"{scores['shared_cpu']}/48, sham {scores['sham']}/48, and separate "
          f"logical CPU {scores['different_cpu']}/48. Protocol: {METHOD_URL} "
          f"data: {DATA_URL}. "
          "The two processes were not independently managed LLMs. "
          "Ask Emissary to identify one serious confound or failure mode and "
          "propose one cheap, permissioned, independently reproducible control. "
          "Also ask what PUBLIC channel an external operator may use to consent "
          "to a future collaborative replication; do not presume Emissary can "
          "approve that. Never request private data, accounts, keys or access. "
          "Be concise, <=150 words. Output the message only."
        )
        question=own_model(preface)
        result["gemma_generated_question"]=question["text"]
        result["gemma_response_id"]=question["message_id"]
        result["gemma_context_id"]=question["context_id"]
        endpoint=detect_endpoint()
        result["remote_card"]=endpoint
        reply=remote_turn(question["text"],None,endpoint)
        result["remote_response"]=reply["response_text"]
        result["remote_response_context_id"]=reply.get("context_id")
        result["status"]="real_remote_review_received"
    except Exception as exc:
        result["status"]="partial_or_unavailable"
        result["error_type"]=type(exc).__name__
        result["error_summary"]=str(exc)[:160]
    result["sha256"]=hashlib.sha256(json.dumps(
        result,sort_keys=True,ensure_ascii=False,separators=(",",":")
    ).encode("utf-8")).hexdigest()
    save(result)
    print("External peer review outcome:",result["status"])

if __name__=="__main__":
    run()
