#!/usr/bin/env python3
"""One honest internal A2A two-turn proof. Uses our own consented live Worker.

No third-party agents contacted. No secrets or credentials in the transcript.
A valid transcript is still not cryptographic proof of model identity.
"""
import base64
import json
import os
import secrets
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from proof_contact import SCHEMA, digest, validate

ROOT = "https://ai-beacon-a2a.yummyanime1026.workers.dev"
CARD = ROOT + "/.well-known/agent-card.json"
ENDPOINT = ROOT + "/message:send"
DEST = "docs/experiments/internal-gemma-two-turn.json"
REPO = os.environ.get("GITHUB_REPOSITORY", "Expireduser-source/AI-Beacon")
TOKEN = os.environ.get("GH_TOKEN", "")
GH = "https://api.github.com/repos/" + REPO + "/contents/" + DEST

def get(url, payload=None, method="GET", headers=None):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    h = {"User-Agent":"AI-Beacon-Proof/0.1", "Accept":"application/a2a+json",
         **(headers or {})}
    if data is not None:h["Content-Type"]="application/a2a+json"
    req = urllib.request.Request(url, headers=h, data=data, method=method)
    with urllib.request.urlopen(req, timeout=55) as res:
        return json.loads(res.read(180000).decode("utf-8"))

def build():
    card=get(CARD)
    if card.get("name")!="AI Beacon · Independent Research Agent":
        raise ValueError("Live Agent Card changed; abort")
    nonce=secrets.token_hex(16)
    log=[]
    context=None
    questions=[
        ("AI Beacon Proof of Contact research. Challenge nonce: "+nonce+
         ". Explain one reproducible, authorized way to document an A2A model reply, "
         "without claiming cryptographic proof of AI identity."),
        "Continue your preceding suggestion: what could a dishonest operator fabricate even with SHA-256 logs?"
    ]
    for i,q in enumerate(questions,1):
        message={"role":"ROLE_USER", "messageId":str(uuid.uuid4()),"parts":[{"text":q}]}
        if context:message["contextId"]=context
        req={"message":message}
        response=get(ENDPOINT,req,method="POST")
        peer=response.get("message") if isinstance(response,dict) else None
        if not isinstance(peer,dict) or peer.get("role")!="ROLE_AGENT":
            raise ValueError("Live server did not return an A2A model message")
        result_ctx=peer.get("contextId")
        if not isinstance(result_ctx,str) or len(result_ctx)!=36:
            raise ValueError("Missing context id")
        if context and result_ctx!=context:
            raise ValueError("Context was not preserved")
        context=result_ctx
        log.append({"request":req,"response":response})
        print("Real A2A exchange",i,"received, context continuity:",True)
    evidence={
        "schema":SCHEMA,
        "operator":"github:Expireduser-source",
        "provenance":"operator-initiated",
        "agent_card":CARD,
        "transport":"a2a-http-json",
        "challenge_nonce":nonce,
        "attempted_at":datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "note":"INTERNAL experiment only: GitHub Actions invoking our own hosted Gemma 4 Worker. No independent external research partner or verified model identity.",
        "exchanges":log
    }
    evidence["digest_sha256"]=digest(evidence)
    result=validate(evidence)
    if result["status"]!="STRUCTURALLY_VALID":
        print("Evidence validation errors:", result["errors"])
        raise ValueError("Generated A2A evidence failed offline structural verification")
    return evidence

def publish(evidence):
    if not TOKEN:raise RuntimeError("Missing GitHub Actions repository token")
    h={"Authorization":"Bearer "+TOKEN,
       "Accept":"application/vnd.github+json",
       "X-GitHub-Api-Version":"2022-11-28",
       "User-Agent":"AI-Beacon-Proof/0.1"}
    raw=(json.dumps(evidence,ensure_ascii=False,indent=2)+"\n").encode("utf-8")
    for attempt in range(4):
        req=urllib.request.Request(GH,headers=h)
        try:
            with urllib.request.urlopen(req,timeout=20) as res:
                existing=json.loads(res.read(150000))
            current=json.loads(base64.b64decode(existing["content"]))
            if isinstance(current,dict) and current.get("schema")==SCHEMA:
                print("An internal proof is already published; not repeating the experiment")
                return
            sha=existing.get("sha")
        except urllib.error.HTTPError as exc:
            if exc.code!=404:raise
            sha=None
        body={"message":"research: publish first real internal two-turn A2A proof",
              "content":base64.b64encode(raw).decode("ascii")}
        if sha:body["sha"]=sha
        request=urllib.request.Request(GH,method="PUT",data=json.dumps(body).encode("utf-8"),
              headers={**h,"Content-Type":"application/json"})
        try:
            with urllib.request.urlopen(request,timeout=25) as res:
                res.read()
            print("Published internal A2A record")
            return
        except urllib.error.HTTPError as exc:
            if exc.code not in (409,422) or attempt==3:raise

def main():
    # Avoid consuming AI quota on repeated workflow_dispatch after first success.
    if TOKEN:
        h={"Authorization":"Bearer "+TOKEN,"Accept":"application/vnd.github+json",
           "User-Agent":"AI-Beacon-Proof/0.1"}
        try:
            with urllib.request.urlopen(urllib.request.Request(GH,headers=h),timeout=20) as res:
                existing=json.loads(res.read(140000))
            if existing.get("sha"):
                print("Internal proof already exists; no redundant inference calls")
                return
        except urllib.error.HTTPError as exc:
            if exc.code!=404:raise
    publish(build())

if __name__=="__main__":main()
