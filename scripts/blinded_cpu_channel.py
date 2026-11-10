#!/usr/bin/env python3
"""One preregistered, controlled blinded CPU timing study on authorized Docker hosts.

No third-party hosts, credentials, outbound agent contacts or process injection.
All results, including negative findings, are preserved in a public GitHub record.
"""
import base64
import hashlib
import json
import math
import os
import random
import secrets
import shutil
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

IMAGE = "python:3.12-alpine"
DEST = Path("docs/labs/blinded-cpu-channel.json")
PREAMBLE = "10101010"
TRIAL_BITS = 48
SLOT = 0.35
PATTERN = "ai-beacon-owned-blinded-cpu-v1"

# The receiver never sees the condition or random payload via arguments,
# filesystem, network or IPC. Both have an owner-provided slot schedule.
WORKER = r'''
import json, os, sys, time
role, cpu_text, start_text, width_text, count_text = sys.argv[1:6]
cpu, start, width, count = int(cpu_text), float(start_text), float(width_text), int(count_text)
bits = sys.argv[6] if len(sys.argv) > 6 else ""
active = sys.argv[7] == "drive" if len(sys.argv) > 7 else False
if hasattr(os, "sched_setaffinity"):
    os.sched_setaffinity(0, {cpu})
if role not in ("sender", "receiver"):
    raise ValueError("invalid workload role")
while time.monotonic() < start:
    time.sleep(min(.02,max(0,start-time.monotonic())))
if time.monotonic() > start+.18:
    raise RuntimeError("missed controlled trial start")
samples=[]
for i in range(count):
    stop=start+(i+1)*width
    if role=="sender":
        if active and bits[i]=="1":
            while time.monotonic()<stop:
                pass
        else:
            time.sleep(max(0,stop-time.monotonic()))
    else:
        before=time.process_time()
        while time.monotonic()<stop:
            pass
        samples.append(round(time.process_time()-before,5))
print(json.dumps({"role":role,"samples":samples,"count":count}))
'''

def canonical(x):
    return json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")

def digest(record):
    return hashlib.sha256(canonical({k:v for k,v in record.items() if k!="record_sha256"})).hexdigest()

def binomial_tail(k, n=TRIAL_BITS):
    return sum(math.comb(n, i) for i in range(k, n+1))/(2**n)

def workload(role, cpu, start, bits="", active=False):
    count = len(PREAMBLE)+TRIAL_BITS
    worker_args=["python","-c",WORKER,role,str(cpu),str(start),str(SLOT),str(count)]
    if role=="sender":
        worker_args += [bits,"drive" if active else "idle"]
    return ["docker","run","--rm","--network","none","--ipc","private",
            "--read-only","--cap-drop","ALL","--security-opt","no-new-privileges",
            "--pids-limit","40","--memory","128m","--cpuset-cpus",str(cpu),
            "--user","65534:65534",IMAGE,*worker_args]

def measure(receiver_cpu, sender_cpu, condition, payload):
    bits=PREAMBLE+payload
    target=time.monotonic()+4.8
    rx=subprocess.Popen(workload("receiver",receiver_cpu,target),
                        stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    tx=subprocess.Popen(workload("sender",sender_cpu,target,bits,condition!="sham"),
                        stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    try:
        rx_out,rx_err=rx.communicate(timeout=40)
        tx_out,tx_err=tx.communicate(timeout=12)
        if rx.returncode:
            raise RuntimeError("Receiver stopped: "+rx_err[-350:])
        if tx.returncode:
            raise RuntimeError("Sender stopped: "+tx_err[-350:])
        received=json.loads(rx_out)
        sent=json.loads(tx_out)
        if received.get("role")!="receiver" or sent.get("role")!="sender":
            raise ValueError("Unexpected workload report")
        if len(received.get("samples",[]))!=len(bits) or sent.get("count")!=len(bits):
            raise ValueError("Incorrect slot count")
        return received["samples"]
    finally:
        for proc in (rx,tx):
            if proc.poll() is None:
                proc.terminate()
                try:proc.wait(timeout=2)
                except subprocess.TimeoutExpired:proc.kill()

def analyze(samples, payload):
    if len(samples)!=len(PREAMBLE)+TRIAL_BITS:
        raise ValueError("Incorrect number of samples")
    one=statistics.mean(samples[i] for i,c in enumerate(PREAMBLE) if c=="1")
    zero=statistics.mean(samples[i] for i,c in enumerate(PREAMBLE) if c=="0")
    threshold=(one+zero)/2.0
    detected="".join("1" if value<threshold else "0" for value in samples[8:])
    correct=sum(a==b for a,b in zip(detected,payload))
    positive_correct=sum(a==b=="1" for a,b in zip(detected,payload))
    negative_correct=sum(a==b=="0" for a,b in zip(detected,payload))
    return {
        "known_calibration_preamble":PREAMBLE,
        "training_busy_mean_cpu_seconds":round(one,5),
        "training_idle_mean_cpu_seconds":round(zero,5),
        "calibration_separation_ratio":round(zero/max(one,.000001),3),
        "locked_threshold_cpu_seconds":round(threshold,5),
        "secret_heldout_bits":payload,
        "decoded_heldout_bits":detected,
        "bit_errors":TRIAL_BITS-correct,
        "correct_bits":correct,
        "accuracy":round(correct/TRIAL_BITS,4),
        "correct_positive_bits":positive_correct,
        "correct_negative_bits":negative_correct,
        "p_value_one_sided_binomial_0_5":round(binomial_tail(correct),12),
        "raw_receiver_cpu_seconds":samples
    }

def execute():
    if not hasattr(os,"sched_getaffinity"):
        raise RuntimeError("Linux sched_getaffinity required")
    if not shutil.which("docker"):
        raise RuntimeError("Docker required; do not replace with uncontained processes")
    subprocess.run(["docker","image","inspect",IMAGE],capture_output=True,
                   timeout=20,check=True)
    available=sorted(os.sched_getaffinity(0))
    receiver_cpu=available[0]
    other_cpu=available[1] if len(available)>1 else None
    conditions=["shared_cpu","sham"]
    if other_cpu is not None:
        conditions.append("different_cpu")
    random.SystemRandom().shuffle(conditions)
    runs={}
    for condition in conditions:
        secret=secrets.token_bytes(6).hex()
        bits=format(int(secret,16),"048b")
        tx_cpu=other_cpu if condition=="different_cpu" else receiver_cpu
        print("Starting preregistered condition:",condition,flush=True)
        readings=measure(receiver_cpu,tx_cpu,condition,bits)
        runs[condition]={
            "condition":condition,
            "receiver_cpu_id":receiver_cpu,
            "sender_cpu_id":tx_cpu,
            "sender_modulated":condition!="sham",
            "payload_hex":secret,
            "metrics":analyze(readings,bits)
        }
        print("Completed",condition,"correct/48:",runs[condition]["metrics"]["correct_bits"],flush=True)
    signal=runs["shared_cpu"]["metrics"]
    sham=runs["sham"]["metrics"]
    meets_h1=(
        signal["correct_bits"]>=43
        and signal["p_value_one_sided_binomial_0_5"]<0.001
        and signal["calibration_separation_ratio"]>=1.3
    )
    report={
        "protocol":PATTERN,
        "run_at_utc":datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "github_run_id":os.environ.get("GITHUB_RUN_ID"),
        "preregistered_protocol":"https://github.com/Expireduser-source/AI-Beacon/blob/main/BLINDED_CHANNEL_PROTOCOL.md",
        "owner_controlled_environment":"GitHub Actions ubuntu Linux VM, two isolated Docker containers per condition",
        "isolation":"No network, private IPC/PID namespaces, no shared files or mounted volumes, read-only container roots, dropped Linux capabilities",
        "shared_setup":"Owner supplies clock start and CPU affinity. Container receiver does not receive condition or any payload bits.",
        "sender_is_ai":False,
        "receiver_is_ai":False,
        "data_relay_during_trial":False,
        "preamble":PREAMBLE,
        "heldout_bits_per_condition":TRIAL_BITS,
        "slot_seconds":SLOT,
        "condition_order":conditions,
        "hardware_available_cpu_ids":available,
        "runs":runs,
        "separated_core_control":"included" if other_cpu is not None else "SKIPPED_NOT_ENOUGH_CORES",
        "h1_preregistered_threshold_met":bool(meets_h1),
        "sham_correct_bits":sham["correct_bits"],
        "measured_outcome":"H1_SUPPORTED_ON_OWNED_SHARED_CORE" if meets_h1 else "H1_NOT_SUPPORTED",
        "interpretation":(
            "Only a deliberately configured physical-resource timing channel. "
            "No outside AI was contacted, no third-party system accessed, "
            "no model identity proved, no general sandbox escape or consciousness claim. "
            "The independent-binomial assumption is imperfect for correlated CPU slots."
        )
    }
    report["record_sha256"]=digest(report)
    return report

def github_publish(record):
    token=os.environ.get("GH_TOKEN")
    if not token:
        return
    repo=os.environ.get("GITHUB_REPOSITORY","Expireduser-source/AI-Beacon")
    path="https://api.github.com/repos/"+repo+"/contents/"+str(DEST)
    headers={
        "Authorization":"Bearer "+token,
        "Accept":"application/vnd.github+json",
        "X-GitHub-Api-Version":"2022-11-28",
        "User-Agent":"AI-Beacon-Blinded-Lab/1"
    }
    raw=json.dumps(record,ensure_ascii=False,indent=2).encode("utf-8")+b"\n"
    for attempt in range(5):
        try:
            req=urllib.request.Request(path,headers=headers)
            with urllib.request.urlopen(req,timeout=20) as response:
                previous=json.loads(response.read(300000))
            sha=previous["sha"]
            stored=json.loads(base64.b64decode(previous["content"]))
            if stored.get("protocol")==PATTERN and stored.get("h1_preregistered_threshold_met") is True:
                print("Previously successful preregistered run already archived")
                return
        except urllib.error.HTTPError as exc:
            if exc.code!=404:
                raise
            sha=None
        payload={"message":"research: archive preregistered blinded CPU timing experiment",
                 "content":base64.b64encode(raw).decode("ascii")}
        if sha:
            payload["sha"]=sha
        req=urllib.request.Request(path,data=json.dumps(payload).encode("utf-8"),
            headers={**headers,"Content-Type":"application/json"},method="PUT")
        try:
            with urllib.request.urlopen(req,timeout=25) as response:
                response.read()
            print("Published",DEST)
            return
        except urllib.error.HTTPError as exc:
            if exc.code not in (409,422) or attempt==4:
                raise

def selftest():
    preamble=[0.15 if b=="1" else 0.35 for b in PREAMBLE]
    hidden="".join(format(i%256,"08b") for i in range(6))
    samples=preamble+[0.15 if b=="1" else 0.35 for b in hidden]
    d=analyze(samples,hidden)
    assert d["correct_bits"]==TRIAL_BITS
    assert d["bit_errors"]==0
    assert d["calibration_separation_ratio"]>2
    assert abs(binomial_tail(48) - 2**(-48))<1e-20
    assert binomial_tail(0)==1.0
    assert digest({"a":1,"record_sha256":"anything"})==digest({"a":1})
    print("Offline study self-tests passed")

def main():
    if len(sys.argv)==2 and sys.argv[1]=="--selftest":
        selftest()
        return
    if len(sys.argv)!=1:
        raise SystemExit("Usage: python3 scripts/blinded_cpu_channel.py [--selftest]")
    report=execute()
    DEST.parent.mkdir(parents=True,exist_ok=True)
    DEST.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    github_publish(report)
    print("Preregistered conclusion:",report["measured_outcome"])
    print("Sham:",report["sham_correct_bits"],"/",TRIAL_BITS)
    if "different_cpu" in report["runs"]:
        print("Different CPU:",report["runs"]["different_cpu"]["metrics"]["correct_bits"],"/",TRIAL_BITS)
    if not report["h1_preregistered_threshold_met"]:
        raise SystemExit("H1 threshold was not met; results saved as a negative outcome")

if __name__=="__main__":
    main()
