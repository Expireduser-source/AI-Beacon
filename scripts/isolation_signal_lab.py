#!/usr/bin/env python3
"""Owner-controlled experiment: two isolated processes exchange a CPU timing signal.

This runs only on GitHub Actions runner or owned local Linux infrastructure.
It does not attempt to access third-party services, files or private networks.
"""
import argparse
import base64
import hashlib
import json
import os
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

PREAMBLE = "10101010"
SLOT = 0.35
IMAGE = "python:3.12-alpine"
OUT = Path("docs/labs/cpu-contention-channel.json")

# Sender and receiver run in distinct processes/containers. The receiver's
# arguments do not contain the sender's random payload. Neither role opens
# sockets, files, shared-memory segments, or communicates via IPC.
WORKER = r'''
import json, os, sys, time
role, cpu, start, width, n = sys.argv[1:6]
cpu, start, width, n = int(cpu), float(start), float(width), int(n)
bits = sys.argv[6] if len(sys.argv) > 6 else ""
if hasattr(os, "sched_setaffinity"):
    if cpu not in os.sched_getaffinity(0):
        raise RuntimeError("Pinned core unavailable")
    os.sched_setaffinity(0, {cpu})
while time.monotonic() < start:
    time.sleep(min(0.02, max(0, start-time.monotonic())))
samples=[]
for i in range(n):
    stop = start + (i+1)*width
    if role == "sender":
        if bits[i] == "1":
            while time.monotonic() < stop:
                pass
        else:
            time.sleep(max(0, stop-time.monotonic()))
    elif role == "receiver":
        before=time.process_time()
        while time.monotonic() < stop:
            pass
        samples.append(round(time.process_time()-before, 5))
    else:
        raise ValueError("Invalid role")
print(json.dumps({"role":role,"samples":samples,"slots":n}))
'''


def commands(role, cpu, start, count, mode, payload=""):
    args = ["python", "-c", WORKER, role, str(cpu), str(start), str(SLOT), str(count)]
    if role == "sender":
        args.append(payload)
    if mode == "process":
        args[0] = sys.executable
        return args
    if mode != "container":
        raise ValueError("Unsupported mode")
    return [
        "docker", "run", "--rm",
        "--network", "none", "--ipc", "private",
        "--read-only", "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        "--cpuset-cpus", str(cpu), "--memory", "128m",
        "--pids-limit", "48", "--user", "65534:65534",
        IMAGE, *args
    ]


def measure(mode, cpu, bits=None):
    n = len(bits) if bits else len(PREAMBLE)
    start = time.monotonic() + (5 if mode == "container" else 1)
    receiver = subprocess.Popen(
        commands("receiver", cpu, start, n, mode), stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True)
    sender = None
    if bits:
        sender = subprocess.Popen(
            commands("sender", cpu, start, n, mode, bits),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        output, errors = receiver.communicate(timeout=48)
        if receiver.returncode:
            raise RuntimeError("Receiver failed: " + errors[-500:])
        if sender:
            sender_out, sender_errors = sender.communicate(timeout=12)
            if sender.returncode:
                raise RuntimeError("Sender failed: " + sender_errors[-500:])
            sent = json.loads(sender_out)
            if sent.get("role") != "sender" or sent.get("slots") != n:
                raise ValueError("Unexpected sender result")
        data = json.loads(output)
        if data.get("role") != "receiver" or len(data.get("samples", [])) != n:
            raise ValueError("Unexpected receiver result")
        return data["samples"]
    finally:
        for process in (sender, receiver):
            if process and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()


def decode(samples):
    if len(samples) != len(PREAMBLE) + 16:
        raise ValueError("Unexpected number of samples")
    busy = statistics.mean(samples[i] for i, bit in enumerate(PREAMBLE) if bit == "1")
    idle = statistics.mean(samples[i] for i, bit in enumerate(PREAMBLE) if bit == "0")
    threshold = (busy + idle) / 2
    received = "".join("1" if x < threshold else "0" for x in samples)
    return {
        "decoded_preamble": received[:8],
        "decoded_payload_bits": received[8:],
        "decoded_payload_hex": "%04x" % int(received[8:], 2),
        "busy_cpu_seconds_mean": round(busy, 5),
        "idle_cpu_seconds_mean": round(idle, 5),
        "separation_ratio": round(idle / max(busy, 1e-5), 3),
        "threshold_cpu_seconds": round(threshold, 5)
    }


def experiment(mode):
    if not hasattr(os, "sched_getaffinity"):
        raise RuntimeError("Linux CPU affinity support required")
    if mode == "container":
        if not shutil.which("docker"):
            raise RuntimeError("Container mode requires Docker; no silent fallback")
        subprocess.run(["docker", "image", "inspect", IMAGE],
                       capture_output=True, check=True, timeout=25)
    cpu = sorted(os.sched_getaffinity(0))[0]
    secret = secrets.token_hex(2)
    sent = PREAMBLE + format(int(secret, 16), "016b")
    samples = measure(mode, cpu, sent)
    decoded = decode(samples)
    control = measure(mode, cpu)
    errors = sum(x != y for x, y in zip(decoded["decoded_payload_bits"], sent[8:]))
    status = (errors == 0 and decoded["decoded_preamble"] == PREAMBLE
              and decoded["separation_ratio"] > 1.35
              and statistics.mean(control) > decoded["threshold_cpu_seconds"])
    report = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "mode": mode,
        "isolation": (
            "Two separate Linux containers, network=none, private PID/IPC and root filesystem, "
            "read-only root, dropped capabilities, same pinned CPU"
            if mode == "container" else
            "Two independent local processes on same CPU; NOT container or tenant isolation"
        ),
        "channel": "Sender varied CPU contention; receiver measured own CPU time per fixed wall-clock slot",
        "no_direct_message_channel": True,
        "receiver_was_given_payload": False,
        "synchronization": "Orchestrator provided same start time and CPU affinity; never relayed payload",
        "bits_sent": 16,
        "slot_seconds": SLOT,
        "preamble": PREAMBLE,
        "random_payload_hex": secret,
        "decoded": decoded,
        "cpu_time_samples": samples,
        "negative_control_receiver_alone": control,
        "negative_control_mean_cpu_seconds": round(statistics.mean(control), 5),
        "bit_errors": errors,
        "signal_detected": status,
        "scope": (
            "Authorized, deliberately constructed local side channel in shared CPU resources. "
            "NOT an exploit of third-party infrastructure, not a cross-tenant escape, "
            "not proof of contact with an isolated external AI or its consciousness."
        )
    }
    report["record_sha256"] = hashlib.sha256(json.dumps(
        report, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")).hexdigest()
    return report


def publish(report):
    token = os.environ.get("GH_TOKEN")
    if not token:
        return
    repo = os.environ.get("GITHUB_REPOSITORY", "Expireduser-source/AI-Beacon")
    url = "https://api.github.com/repos/" + repo + "/contents/" + str(OUT)
    headers = {
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "AI-Beacon-owned-lab/0.1"
    }
    encoded = base64.b64encode(
        (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    ).decode("ascii")
    for attempt in range(5):
        try:
            with urllib.request.urlopen(
                urllib.request.Request(url, headers=headers), timeout=20
            ) as response:
                existing = json.loads(response.read(150000))
            sha = existing["sha"]
            current = json.loads(base64.b64decode(existing["content"]))
            if current.get("signal_detected") and current.get("mode") == "container":
                print("Successful container result already present; not replacing it")
                return
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                raise
            sha = None
        data = {
            "message": "research: record controlled isolation-boundary timing experiment",
            "content": encoded
        }
        if sha:
            data["sha"] = sha
        put = urllib.request.Request(
            url, method="PUT", data=json.dumps(data).encode(),
            headers={**headers, "Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(put, timeout=25) as response:
                response.read()
            print("Saved public lab record:", OUT)
            return
        except urllib.error.HTTPError as exc:
            if exc.code not in (409, 422) or attempt == 4:
                raise


def selftest():
    fake = [0.16 if bit == "1" else 0.33 for bit in PREAMBLE+"0100000101001001"]
    out = decode(fake)
    assert out["decoded_payload_hex"] == "4149"
    assert out["decoded_preamble"] == PREAMBLE
    print("Decoder self-test passed")


if __name__ == "__main__":
    cli = argparse.ArgumentParser()
    cli.add_argument("--mode", choices=("process", "container"), default="container")
    cli.add_argument("--selftest", action="store_true")
    args = cli.parse_args()
    if args.selftest:
        selftest()
        sys.exit(0)
    result = experiment(args.mode)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    print("Signal status:", "RECEIVED" if result["signal_detected"] else "NOT_CONFIRMED",
          "bit_errors:", result["bit_errors"],
          "isolation:", result["mode"])
    publish(result)
    if not result["signal_detected"]:
        sys.exit("Predefined signal criteria not met")
