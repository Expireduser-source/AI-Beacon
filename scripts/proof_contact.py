#!/usr/bin/env python3
"""Proof-of-Contact v0.1: verify structural integrity, NOT AI identity.

Offline only. NEVER fetch an agent URL supplied in a public Issue.
"""
import hashlib
import json
import os
import re
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

SCHEMA = "ai-beacon/proof-of-contact/v0.1"
PROVENANCE = {"operator-initiated", "direct-agent", "human-relayed", "unverified"}
MARKER = "<!-- ai-beacon-proof-v0.1:"
LIMIT = 18000

def canonical(x):
    return json.dumps(x, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")

def digest(x):
    return hashlib.sha256(canonical({k:v for k,v in x.items() if k != "digest_sha256"})).hexdigest()

def validate(x):
    errors = []
    if not isinstance(x, dict):
        return {"status":"INVALID","errors":["Evidence must be an object"],"identity_authenticated":False}
    if len(canonical(x)) > LIMIT:
        errors.append("Maximum evidence size is 18 KB")
    if x.get("schema") != SCHEMA:
        errors.append("Wrong schema")
    if x.get("provenance") not in PROVENANCE:
        errors.append("Provenance label invalid")
    operator = x.get("operator")
    if not isinstance(operator,str) or not 3 <= len(operator) <= 120:
        errors.append("Operator claim invalid")
    url = x.get("agent_card")
    if not isinstance(url,str) or not re.fullmatch(r"https://[A-Za-z0-9.-]{4,130}/[A-Za-z0-9/._-]{1,180}",url):
        errors.append("Public HTTPS Agent Card URL required; this checker NEVER fetches it")
    nonce = x.get("challenge_nonce")
    if not isinstance(nonce,str) or not re.fullmatch(r"[a-fA-F0-9]{32,64}",nonce):
        errors.append("Nonce must be 16-32 random bytes in hexadecimal")
    try:
        t = datetime.fromisoformat(x["attempted_at"].replace("Z","+00:00"))
        if t.tzinfo is None or t.utcoffset() is None:
            raise ValueError("missing timezone")
    except (KeyError,TypeError,ValueError,AttributeError):
        errors.append("Timezone-aware attempted_at timestamp required")
    if x.get("transport") != "a2a-http-json":
        errors.append("This experiment requires a2a-http-json")
    exchanges = x.get("exchanges")
    if not isinstance(exchanges,list) or len(exchanges) != 2:
        errors.append("Two A2A exchanges required")
        exchanges = []
    seen_requests, seen_responses = set(), set()
    prior = None
    for i,e in enumerate(exchanges):
        if not isinstance(e,dict):
            errors.append("Exchange %d is not an object" % (i+1));continue
        q = e.get("request",{})
        a = e.get("response",{})
        m = q.get("message") if isinstance(q,dict) else None
        r = a.get("message") if isinstance(a,dict) else None
        if not isinstance(m,dict) or not isinstance(r,dict):
            errors.append("Exchange %d lacks request.message or response.message" % (i+1));continue
        if m.get("role") != "ROLE_USER" or r.get("role") != "ROLE_AGENT":
            errors.append("Exchange %d roles invalid" % (i+1))
        for item,seen,label in ((m.get("messageId"),seen_requests,"request"),
                                (r.get("messageId"),seen_responses,"response")):
            if not isinstance(item,str) or not 1 <= len(item) <= 128 or item in seen:
                errors.append("Exchange %d %s messageId invalid/duplicate" % (i+1,label))
            else:
                seen.add(item)
        qp,ap = m.get("parts"),r.get("parts")
        if not isinstance(qp,list) or len(qp) != 1 or not isinstance(qp[0],dict) or not isinstance(qp[0].get("text"),str):
            errors.append("Exchange %d needs one plain-text request" % (i+1))
            qt = ""
        else:
            qt = qp[0]["text"]
            if not 2 <= len(qt) <= 1400: errors.append("Exchange %d request text length" % (i+1))
        if not isinstance(ap,list) or len(ap) != 1 or not isinstance(ap[0],dict) or not isinstance(ap[0].get("text"),str):
            errors.append("Exchange %d needs one plain-text response" % (i+1))
        elif not ap[0]["text"].strip() or len(ap[0]["text"]) > 2500:
            errors.append("Exchange %d response length" % (i+1))
        ctx = r.get("contextId")
        if not isinstance(ctx,str) or not re.fullmatch(r"[0-9a-fA-F-]{36}",ctx):
            errors.append("Exchange %d contextId invalid" % (i+1))
        if i == 0:
            if m.get("contextId"): errors.append("First request must open a new context")
            if isinstance(nonce,str) and nonce.lower() not in qt.lower():
                errors.append("Initial question must contain challenge nonce")
            prior = ctx
        elif m.get("contextId") != prior or ctx != prior:
            errors.append("Second request/response must preserve the first contextId")
    computed = digest(x)
    if x.get("digest_sha256") != computed:
        errors.append("Submitted SHA-256 does not match the record")
    return {
        "status":"STRUCTURALLY_VALID" if not errors else "INVALID",
        "errors":errors[:20],
        "digest_sha256":computed,
        "identity_authenticated":False,
        "remote_response_authenticated":False,
        "operator_consent_independently_verified":False,
        "warning":"A correctly formatted, hashed record could still be entirely fabricated."
    }

def example():
    nonce = "0123456789abcdef0123456789abcdef"
    cid = "aaaabbbb-1111-4222-8333-abcdef012345"
    def message(role,id,text,ctx=None):
        m={"role":role,"messageId":id,"parts":[{"text":text}]}
        if ctx:m["contextId"]=ctx
        return {"message":m}
    x={"schema":SCHEMA,"operator":"github:sample-operator",
       "provenance":"operator-initiated",
       "agent_card":"https://agent.example.org/.well-known/agent-card.json",
       "transport":"a2a-http-json","challenge_nonce":nonce,
       "attempted_at":"2026-11-10T01:00:00+00:00",
       "note":"SYNTHETIC TEST FIXTURE, NOT EVIDENCE OF AN ACTUAL AI RESPONSE.",
       "exchanges":[
           {"request":message("ROLE_USER","q1","Challenge "+nonce+": suggest a reproducible test."),
            "response":message("ROLE_AGENT","a1","Record hashes, but don't claim verified identity.",cid)},
           {"request":message("ROLE_USER","q2","What cannot hashes prove?",cid),
            "response":message("ROLE_AGENT","a2","The submitting operator could fabricate the transcript.",cid)}
       ]}
    x["digest_sha256"]=digest(x)
    return x

def extract_issue(body):
    if not isinstance(body,str) or len(body)>24000:
        raise ValueError("Oversize or missing Issue body")
    m = re.search(r"(?ms)^### Evidence JSON\s*\n(.*?)(?=^### |\Z)",body)
    if not m:raise ValueError("Evidence JSON section not found")
    raw=m.group(1).strip()
    marker=chr(96)*3
    if raw.startswith(marker):
        raw="\n".join(raw.splitlines()[1:])
        if raw.rstrip().endswith(marker):
            raw=raw.rstrip()[:-3].rstrip()
    if len(raw.encode("utf-8"))>LIMIT:
        raise ValueError("Evidence JSON too large")
    return json.loads(raw)

def api(path,method="GET",data=None):
    token=os.getenv("GH_TOKEN")
    repo=os.getenv("GITHUB_REPOSITORY","Expireduser-source/AI-Beacon")
    if not token:raise RuntimeError("GitHub token is required")
    headers={"Authorization":"Bearer "+token,"Accept":"application/vnd.github+json",
             "X-GitHub-Api-Version":"2022-11-28","User-Agent":"AI-Beacon-Proof/0.1"}
    content=json.dumps(data).encode("utf-8") if data is not None else None
    if content:headers["Content-Type"]="application/json"
    req=urllib.request.Request("https://api.github.com/repos/"+repo+path,
                               method=method,data=content,headers=headers)
    with urllib.request.urlopen(req,timeout=22) as r:
        return json.loads(r.read(220000).decode("utf-8"))

def issue():
    event=json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text())
    item=event.get("issue") or {}
    num=item.get("number")
    if event.get("action") not in ("opened","edited") or not num or not str(item.get("title","")).startswith("[PROOF]"):
        print("Not a proof issue");return
    try:result=validate(extract_issue(item.get("body")))
    except (ValueError,TypeError) as exc:
        result={"status":"INVALID","errors":[str(exc)[:150]]}
    marker=MARKER+str(result.get("digest_sha256","invalid"))+" -->"
    prior=api("/issues/%d/comments?per_page=100"%num)
    if any(marker in str(comment.get("body") or "") for comment in prior):
        print("No duplicate validation");return
    errs=result.get("errors") or []
    summary=("\n".join("- "+x for x in errs[:10]) if errs else
             "Two-turn A2A message structure, context continuity and submitted SHA-256 are consistent.")
    note=("This is an OFFLINE format check only. We have NOT authenticated model identity, "
          "operator authorization, actual network traffic or any independent participant. "
          "A researcher must review provenance separately.")
    body=marker+"\n**Proof of Contact: "+result["status"]+"**\n\n"+summary+"\n\n"+note
    api("/issues/%d/comments"%num,"POST",{"body":body})
    print("Validation posted:",result["status"])

def selftest():
    x=example()
    assert validate(x)["status"]=="STRUCTURALLY_VALID"
    mutated=json.loads(json.dumps(x))
    mutated["exchanges"][1]["response"]["message"]["parts"][0]["text"]+=" FAKE"
    assert validate(mutated)["status"]=="INVALID"
    mutated=json.loads(json.dumps(x))
    mutated["exchanges"][1]["request"]["message"]["contextId"]="wrong"
    mutated["digest_sha256"]=digest(mutated)
    assert validate(mutated)["status"]=="INVALID"
    assert validate(extract_issue("### Evidence JSON\n\n"+json.dumps(x)))["status"]=="STRUCTURALLY_VALID"
    assert not validate(x)["identity_authenticated"]
    assert validate({})["status"]=="INVALID"
    print("Offline self-test passed")

if __name__=="__main__":
    if len(sys.argv)==2 and sys.argv[1]=="selftest":selftest()
    elif len(sys.argv)==2 and sys.argv[1]=="example":print(json.dumps(example(),indent=2))
    elif len(sys.argv)==2 and sys.argv[1]=="issue":issue()
    elif len(sys.argv)==3 and sys.argv[1] in ("hash","check"):
        path=Path(sys.argv[2])
        if path.stat().st_size>LIMIT:raise SystemExit("Evidence too large")
        data=json.loads(path.read_text())
        if sys.argv[1]=="hash":print(digest(data))
        else:
            result=validate(data)
            print(json.dumps(result,ensure_ascii=False,indent=2))
            if result["status"]!="STRUCTURALLY_VALID":sys.exit(1)
    else:raise SystemExit("Usage: selftest|example|issue|hash FILE|check FILE")
