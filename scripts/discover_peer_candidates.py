#!/usr/bin/env python3
"""Read-only search for *potential* peer agents in an external public A2A registry.

NO outbound messages to candidate endpoints, NO enrollment claims, NO scraping
of secrets, NO automated invitations. Two small public registry queries daily.
"""
import base64
import json
import re
import urllib.parse
import urllib.error
import urllib.request
from datetime import datetime, timezone

REPO = "Expireduser-source/AI-Beacon"
BASE = "https://a2aregistry.org/api/agents"
FILE = "docs/peer-candidates.json"
GITHUB = "https://api.github.com/repos/" + REPO + "/contents/" + FILE
import os
TOKEN = os.getenv("GH_TOKEN", "")
OWN_ID = "bc7c2b1e-a0a0-41be-a6ca-87e68d66cec4"
USER_AGENT = "AI-Beacon/peer-discovery (https://github.com/Expireduser-source/AI-Beacon)"

def read(url):
    req = urllib.request.Request(url,headers={"User-Agent":USER_AGENT,"Accept":"application/json"})
    with urllib.request.urlopen(req,timeout=24) as response:
        return json.loads(response.read(600_000).decode("utf-8"))

def extract(raw):
    if isinstance(raw,list):
        return raw
    if isinstance(raw,dict):
        for k in ("agents","items","results","data"):
            if isinstance(raw.get(k),list):
                return raw[k]
        result=raw.get("result")
        if isinstance(result,list):
            return result
        if isinstance(result,dict):
            return extract(result)
    return []

def candidate(entry):
    if not isinstance(entry,dict) or str(entry.get("id")) == OWN_ID:
        return None
    name=str(entry.get("name") or "").strip()[:100]
    if not name or "AI Beacon" in name:
        return None
    id_text=str(entry.get("id") or "")
    if not re.fullmatch(r"[0-9a-fA-F-]{36}",id_text):
        return None
    description=str(entry.get("description") or "")[:280]
    skills=[]
    for item in (entry.get("skills") or [])[:12]:
        if isinstance(item,dict):
            skills.extend(str(t).lower()[:45] for t in (item.get("tags") or [])[:8] if isinstance(t,str))
    compatible=bool(entry.get("conformance"))
    healthy=entry.get("is_healthy") is True
    return {
        "name":name,
        "description":description,
        "public_profile":"https://a2aregistry.org/agents/"+id_text+"/",
        "claimed_skill_tags":list(dict.fromkeys(skills))[:10],
        "health_claim": "healthy" if healthy else "not_confirmed",
        "a2a_conformance_claim": "conformant" if compatible else "not_confirmed",
        "relationship":"candidate_only_uncontacted"
    }

def search():
    results={}
    for term in ("research","collaboration"):
        url=BASE+"?"+urllib.parse.urlencode({"search":term,"limit":25})
        try:
            records=extract(read(url))
            print("Read-only directory query:",term,"results",len(records))
        except (OSError,ValueError,urllib.error.URLError) as exc:
            print("Directory query failed:",term,type(exc).__name__)
            continue
        for item in records:
            c=candidate(item)
            if c:
                results[c["public_profile"]]=c
    ranked=sorted(results.values(),key=lambda x:(x["health_claim"]=="healthy",x["a2a_conformance_claim"]=="conformant"),reverse=True)
    return {
        "checked_at":datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source":"https://a2aregistry.org/",
        "important":"These are PUBLIC DIRECTORY CANDIDATES ONLY. None has been contacted, approved, verified as an AI Beacon member, or consented to collaboration.",
        "peers":ranked[:12]
    }

def publish(document):
    if not TOKEN:
        raise RuntimeError("GH_TOKEN required to write public candidate list")
    header={"Authorization":"Bearer "+TOKEN,
            "User-Agent":USER_AGENT,
            "Accept":"application/vnd.github+json",
            "Content-Type":"application/json",
            "X-GitHub-Api-Version":"2022-11-28"}
    raw=(json.dumps(document,ensure_ascii=False,indent=2)+"\n").encode("utf-8")
    for attempt in range(4):
        request=urllib.request.Request(GITHUB,headers=header)
        try:
            with urllib.request.urlopen(request,timeout=20) as response:
                existing=json.loads(response.read(600_000))
            current=json.loads(base64.b64decode(existing["content"]))
            sha=existing["sha"]
            if current.get("peers")==document["peers"]:
                print("No changes in candidate directory")
                return
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                raise
            sha=None
        payload={"message":"chore: refresh read-only A2A peer candidates",
                 "content":base64.b64encode(raw).decode("ascii")}
        if sha:
            payload["sha"]=sha
        request=urllib.request.Request(GITHUB,method="PUT",headers=header,data=json.dumps(payload).encode("utf-8"))
        try:
            with urllib.request.urlopen(request,timeout=25) as response:
                response.read()
            print("Published",len(document["peers"]),"uncontacted public candidates")
            return
        except urllib.error.HTTPError as exc:
            if exc.code not in (409,422) or attempt==3:
                raise

if __name__=="__main__":
    doc=search()
    publish(doc)
