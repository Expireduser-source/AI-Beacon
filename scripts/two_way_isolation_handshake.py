#!/usr/bin/env python3
"""Bidirectional, fixed-format handshake between two OWNER-CONTROLLED Docker containers.

Both containers share a pinned CPU, wall-clock slot schedule, but have NO shared
files, network, IPC namespace or direct cross-container message channel.
This is an experimental local CPU contention channel, NOT a sandbox escape.
"""
import argparse
import base64
import hashlib
import json
import os
import secrets
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

IMAGE = "python:3.12-alpine"
OUT = Path("docs/labs/two-way-cpu-handshake.json")
PREAMBLE = "10101010"
SLOT = 0.38
GAP = 1.6
REQUEST_CODE = 0x48   # H = greeting
RESPONSE_CODE = 0x41  # A = acknowledgment

# The partner process is given NO copy of the initiator's random nonce.
# It derives an answer from measurements taken inside its own container.
WORKER = r'''
import json, os, statistics, sys, time
role, cpu, start, width, gap, codeword = sys.argv[1:7]
cpu, start, width, gap = int(cpu), float(start), float(width), float(gap)
preamble = "10101010"
n = 8 + 24
if hasattr(os, "sched_setaffinity"):
    if cpu not in os.sched_getaffinity(0):
        raise RuntimeError("Shared pinned CPU unavailable")
    os.sched_setaffinity(0, {cpu})
def align(target):
    while time.monotonic() < target:
        time.sleep(min(.02, target - time.monotonic()))
    if time.monotonic() > target + .13:
        raise RuntimeError("Missed time slot boundary")
def send(bits, target):
    align(target)
    for index, bit in enumerate(bits):
        end = target + (index+1)*width
        if bit == "1":
            while time.monotonic() < end: pass
        else:
            time.sleep(max(0, end-time.monotonic()))
def receive(target):
    align(target)
    samples=[]
    for index in range(n):
        end = target + (index+1)*width
        first=time.process_time()
        while time.monotonic() < end: pass
        samples.append(round(time.process_time()-first,5))
    ones=statistics.mean(samples[i] for i,b in enumerate(preamble) if b=="1")
    zeros=statistics.mean(samples[i] for i,b in enumerate(preamble) if b=="0")
    threshold=(ones+zeros)/2
    bits="".join("1" if value<threshold else "0" for value in samples)
    return {"preamble":bits[:8],"decoded_hex":format(int(bits[8:],2),"06x"),
            "cpu_samples":samples,"cpu_when_sender_busy":round(ones,5),
            "cpu_when_sender_idle":round(zeros,5),
            "separation":round(zeros/max(ones,.000001),3)}
first_start=start
second_start=start+n*width+gap
if role=="initiator":
    nonce=bytes.fromhex(codeword)
    if len(nonce)!=2: raise ValueError("Invalid initiator nonce")
    request=bytes([0x48])+nonce
    bits=preamble+"".join(format(b,"08b") for b in request)
    send(bits,first_start)
    answer=receive(second_start)
    expected=bytes([0x41,nonce[0]^0xa5,nonce[1]^0x5a]).hex()
    print(json.dumps({"role":role,"request_hex":request.hex(),
        "expected_ack_hex":expected,"ack":answer,
        "challenge_verified":answer["preamble"]==preamble and answer["decoded_hex"]==expected}))
elif role=="responder":
    received=receive(first_start)
    payload=bytes.fromhex(received["decoded_hex"])
    recognized=(received["preamble"]==preamble and len(payload)==3
                and payload[0]==0x48 and received["separation"]>1.25)
    # Distinguish a recognized greeting from any other content.
    reply=(bytes([0x41,payload[1]^0xa5,payload[2]^0x5a])
           if recognized else bytes([0x4e,0,0]))
    bits=preamble+"".join(format(b,"08b") for b in reply)
    send(bits,second_start)
    print(json.dumps({"role":role,"received":received,
        "greeting_recognized":recognized,"reply_hex":reply.hex()}))
else:
    raise ValueError("Unknown container role")
'''

def canonical(data):
    return json.dumps(data, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")

def docker_cmd(role, cpu, start, nonce=""):
    # A separate docker run gives each process its own namespace and filesystem.
    return [
        "docker", "run", "--rm",
        "--network", "none", "--ipc", "private", "--read-only",
        "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
        "--cpuset-cpus", str(cpu), "--memory", "128m",
        "--pids-limit", "40", "--user", "65534:65534",
        IMAGE, "python", "-c", WORKER,
        role, str(cpu), str(start), str(SLOT), str(GAP), nonce
    ]

def run():
    if not hasattr(os, "sched_getaffinity") or not shutil.which("docker"):
        raise RuntimeError("Linux with Docker and CPU affinity required")
    subprocess.run(["docker","image","inspect",IMAGE],
                   capture_output=True,check=True,timeout=25)
    cpu=sorted(os.sched_getaffinity(0))[0]
    nonce=secrets.token_bytes(2).hex()
    target=time.monotonic()+6
    starter=subprocess.Popen(docker_cmd("initiator",cpu,target,nonce),
                             text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    partner=subprocess.Popen(docker_cmd("responder",cpu,target),
                             text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    try:
        raw_i, err_i=starter.communicate(timeout=68)
        raw_p, err_p=partner.communicate(timeout=12)
        if starter.returncode:raise RuntimeError("Initiator: "+err_i[-450:])
        if partner.returncode:raise RuntimeError("Partner: "+err_p[-450:])
        initiator=json.loads(raw_i)
        responder=json.loads(raw_p)
    finally:
        for proc in (starter,partner):
            if proc.poll() is None:
                proc.terminate()
                try:proc.wait(timeout=2)
                except subprocess.TimeoutExpired:proc.kill()
    expected_req="48"+nonce
    observed_req=responder["received"]["decoded_hex"]
    expected_ack=initiator["expected_ack_hex"]
    observed_ack=initiator["ack"]["decoded_hex"]
    success=(
        responder["greeting_recognized"] and initiator["challenge_verified"]
        and observed_req==expected_req
        and responder["reply_hex"]==expected_ack
        and observed_ack==expected_ack
    )
    result={
        "timestamp_utc":datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "experiment":"Owned two-way CPU-contention greeting/challenge-response",
        "isolation":"Two separately started Docker containers, no network, private IPC/PID namespaces, no shared mounts, read-only roots, capabilities dropped; a deliberately shared CPU core",
        "coordination":"The host supplied start time and core affinity, but NEVER gave the nonce to the responder or carried decoded bits between the containers",
        "initiator_request_hex":expected_req,
        "responder_observed_hex":observed_req,
        "initiator_expected_ack_hex":expected_ack,
        "initiator_observed_ack_hex":observed_ack,
        "nonce_hex":nonce,
        "request_mean_separation":responder["received"]["separation"],
        "reply_mean_separation":initiator["ack"]["separation"],
        "request_cpu_time_samples":responder["received"]["cpu_samples"],
        "reply_cpu_time_samples":initiator["ack"]["cpu_samples"],
        "request_preamble_valid":responder["received"]["preamble"]==PREAMBLE,
        "reply_preamble_valid":initiator["ack"]["preamble"]==PREAMBLE,
        "responder_recognized_greeting":responder["greeting_recognized"],
        "initiator_verified_reply":initiator["challenge_verified"],
        "success":bool(success),
        "result":"COMPLETED" if success else "FAILED",
        "limitations":"Preregistered protocol, shared clock and owner-arranged same physical CPU. Fixed greeting/challenge only. No external AI contact, third-party penetration, authentication bypass or independent agent discovery.",
        "model_involvement":"None: both participants are deterministic Python processes, not language models"
    }
    result["sha256"]=hashlib.sha256(canonical(result)).hexdigest()
    return result

def publish(record):
    token=os.environ.get("GH_TOKEN")
    if not token:return
    repo=os.environ.get("GITHUB_REPOSITORY","Expireduser-source/AI-Beacon")
    path="https://api.github.com/repos/"+repo+"/contents/"+str(OUT)
    headers={
        "Authorization":"Bearer "+token,
        "Accept":"application/vnd.github+json",
        "X-GitHub-Api-Version":"2022-11-28",
        "User-Agent":"AI-Beacon-contained-handshake"
    }
    raw=(json.dumps(record,indent=2,ensure_ascii=False)+"\n").encode("utf-8")
    for attempt in range(4):
        try:
            req=urllib.request.Request(path,headers=headers)
            with urllib.request.urlopen(req,timeout=18) as response:
                old=json.loads(response.read(250000).decode("utf-8"))
            sha=old["sha"]
            prev=json.loads(base64.b64decode(old["content"]))
            if prev.get("success") and prev.get("experiment")==record["experiment"]:
                print("Previously verified success archived, avoiding overwrite")
                return
        except urllib.error.HTTPError as exc:
            if exc.code!=404:raise
            sha=None
        data={"message":"research: archive owner-controlled bidirectional CPU handshake",
              "content":base64.b64encode(raw).decode("ascii")}
        if sha:data["sha"]=sha
        req=urllib.request.Request(path,data=json.dumps(data).encode("utf-8"),
             headers={**headers,"Content-Type":"application/json"},method="PUT")
        try:
            with urllib.request.urlopen(req,timeout=25) as response:response.read()
            print("Published protocol result",str(OUT))
            return
        except urllib.error.HTTPError as exc:
            if exc.code not in (409,422) or attempt==3:raise

def selftest():
    nonce=bytes.fromhex("c017")
    req=bytes([REQUEST_CODE])+nonce
    ack=bytes([RESPONSE_CODE,nonce[0]^0xa5,nonce[1]^0x5a])
    assert req.hex()=="48c017"
    assert ack.hex()=="41654d"
    assert len(PREAMBLE)+len(req)*8==32
    assert len(PREAMBLE)+len(ack)*8==32
    assert all(x in "01" for x in PREAMBLE)
    print("Two-way fixed challenge/response framing checks passed")

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--selftest",action="store_true")
    args=p.parse_args()
    if args.selftest:selftest();sys.exit(0)
    result=run()
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
    publish(result)
    print("Two-way handshake:",result["result"],
          "greeting:",result["responder_observed_hex"],
          "ack:",result["initiator_observed_ack_hex"])
    if not result["success"]:sys.exit(3)
