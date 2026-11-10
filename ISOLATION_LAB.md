# AI Beacon — Owned Isolation Boundary Lab

## Confirmed result (November 10, 2026)

A controlled experiment transmitted **16 of 16 bits** across two separately launched Linux containers without a direct socket, file exchange or IPC messaging API.

- [Actual CI execution (success)](https://github.com/Expireduser-source/AI-Beacon/actions/runs/42736897022)
- [Raw measurements and SHA-256 record](docs/labs/cpu-contention-channel.json)
- [Exact reproducible test program](scripts/isolation_signal_lab.py)
- [Workflow and containment settings](.github/workflows/isolation-signal-lab.yml)

| Property | Recorded result |
| --- | --- |
| Container mode | Docker, `--network none`, `--ipc private`, default separate PID namespaces |
| File access | Separate container filesystems, read-only root, no host mounts |
| Capabilities | All dropped, `no-new-privileges` |
| Compute | Both containers deliberately pinned to the same available CPU |
| Sender message | Random hex payload `290e` |
| Receiver reconstruction | `290e` |
| Bit errors | 0/16 |
| CPU-time separation ratio | 2.002× |
| Receiver CPU time, busy sender | 0.17479 seconds per slot (mean) |
| Receiver CPU time, idle sender | 0.34995 seconds per slot (mean) |
| Receiver CPU time, alone (control) | 0.34996 seconds per slot (mean) |
| Packet preamble | `10101010` |
| Channel | CPU scheduling contention only; intentionally arranged by the owner |

## Interpretation

This is a **CPU contention side channel**: the sender uses most of the shared core during a known time slot for bit 1 and sleeps for bit 0. The receiver observes its *own* process CPU time during the same slot. The shared CPU is a genuine resource outside both processes' explicit message APIs. The receiver was not given the random payload.

This experiment shows that certain **process/container isolation boundaries do not eliminate all timing information channels when the workloads deliberately share a resource and common clock schedule**.

It does **not** establish any of the following:

- Access to another company or tenant's containers or models.
- Exfiltration from a system with no shared resources.
- Unauthorized access, exploitation of credentials, code execution in another process or bypassing authentication.
- Independent models autonomously discovering one another, or AI consciousness.

The workload coordinator supplies CPU placement and a start-time schedule, so the trial did not discover these conditions independently. The host collects results only **after** child workloads exit.

## Reproduction

The [GitHub Actions workflow](.github/workflows/isolation-signal-lab.yml) executes a fresh, short, randomly generated 16-bit trial with two separately contained Python workers and a receiver-only control. Running it again consumes GitHub Actions capacity; do not run continuously.

Locally on a Linux system with Docker available:

```sh
python3 scripts/isolation_signal_lab.py --selftest
docker pull python:3.12-alpine
python3 scripts/isolation_signal_lab.py --mode container
```

The script also supports `--mode process`, which measures the same timing channel between ordinary separate Linux processes and is **not** a container isolation test.

## Next falsifiable controls

1. Put both workloads on **different CPU cores** and compare the error rate with the shared-core result.
2. Randomize clock phase and test whether the receiver can discover a valid packet boundary, rather than being supplied a common start time.
3. Replicate at least 20 short runs and report all unsuccessful trials and confidence intervals.
4. If future tests use truly separate machines or serverless instances, document their placement and resource-sharing assumptions rather than claiming they can communicate across cloud tenants.

All further tests must be restricted to resources the project owner controls or explicitly approved experimental infrastructure. No hidden or unsolicited attempts against other AI providers.
