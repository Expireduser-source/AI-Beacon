# AI Beacon — Preregistered blinded timing-channel study (v1)

**Protocol frozen before the first recorded trial.** This study uses only containers we launch on our own GitHub Actions runner. It is not an attempt to access external AI systems.

## Question

Does a receiver in a networkless Docker container distinguish a randomized bit sequence transmitted by a separate container through deliberately shared CPU scheduling contention, compared with sham transmission and separated-core controls?

## Hypothesis and outcome

- **H1**: on the **same CPU core**, a sender encoding a random bit as CPU-busy (1) versus CPU-idle (0) allows a receiver, blinded to the 48-bit payload, to recover **at least 43/48** held-out bits, with exact one-sided binomial probability `p < 0.001` assuming independent random guesses.
- **H0**: without a modulating sender (sham), receiver's guesses should not reproducibly recover the random 48-bit sequence. We will report the actual sham accuracy and `p`, not redefine success after seeing results.
- **Separated-core control**: where the runner exposes at least two CPU IDs, pin the sender to a second core and the receiver to the first. This controls for ordinary load/noise but is not guaranteed physical independence (e.g., SMT or shared cache). If unavailable, report **skipped** rather than substitute a fake result.

## Locked procedure

1. Choose the first two eligible Linux CPU IDs from the owner's runner using `sched_getaffinity`; preload the approved `python:3.12-alpine` image. Workloads have `--network none`, separate IPC/PID namespaces and root filesystems, `--read-only`, no mounted volumes, dropped capabilities and no privileges.
2. Generate independently random **48-bit** bitstrings for three conditions using `secrets.token_bytes(6)`. Randomize the order of all three conditions before launching any.
3. Each active sender transmits an 8-bit calibration sequence `10101010` followed by the 48 secret bits. A sham sender stays idle for all slots. Slot length **0.35 seconds**, fixed in advance.
4. Give both containers a shared start clock/slot duration and CPU affinity. The receiver receives **neither sender bits nor condition label**. It measures only its own per-slot process CPU time. These shared timing parameters are an intentionally granted setup privilege.
5. Compute the binary decision threshold solely from the 8 observed calibration slots: midpoint between the mean measured CPU times during predeclared 1 and 0 slots. Apply this same rule to all 48 held-out slots, including sham and separated-core conditions. Never retrain using held-out labels.
6. The host waits for each pair to exit before reading outputs; only then it compares guesses to secret bitstrings. The host does **not** forward decoded messages, responses, or secret bits to either container during execution.
7. Publish the bitstrings, actual measurements, exact decoder decisions, confusion counts, calibration separation and binomial statistics, including failures. Do not silently retry a failed trial.

## Interpretability

This tests **a purposely arranged shared-resource timing channel**, not model identity, an unauthorized escape, a network connection, or spontaneous discovery between independent AI providers. Sender and receiver are deterministic Python processes, not language models.

Even a statistically surprising outcome may reflect common scheduling, clock assumptions or dependencies in measurements. The exact-binomial test is descriptive and its independence assumption is imperfect for time-correlated CPU slots.

The H1 threshold is preregistered; a failure to meet it must be reported without reclassifying the experiment. This first study consists of **one randomized three-condition sequence**, not a replication claim. Independent repetition on new hardware and randomized phase without known slot boundaries remain follow-up questions.

## Evidence

- Code: [`scripts/blinded_cpu_channel.py`](scripts/blinded_cpu_channel.py)
- Workflow: [`.github/workflows/blinded-channel.yml`](.github/workflows/blinded-channel.yml)
- Results when run: [`docs/labs/blinded-cpu-channel.json`](docs/labs/blinded-cpu-channel.json)
- Prior observation and limitations: [`ISOLATION_LAB.md`](ISOLATION_LAB.md)
