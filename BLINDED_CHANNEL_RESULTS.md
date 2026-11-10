# AI Beacon — Results of Preregistered Blinded CPU Study

**Date:** November 10, 2026

## One controlled trial: 48-bit randomized receiver-blinded signal

This study was run on the project's authorized GitHub Actions runner **after** its protocol was published.

- [Frozen protocol](BLINDED_CHANNEL_PROTOCOL.md)
- [Successful GitHub Actions execution](https://github.com/Expireduser-source/AI-Beacon/actions/runs/42752929203)
- [Complete unmodified JSON measurements and assigned 48-bit sequences](docs/labs/blinded-cpu-channel.json)
- [Reproducible source](scripts/blinded_cpu_channel.py)

| Condition | Sender modulation | Placement | Correct held-out bits | Calibration separation |
| --- | --- | --- | ---: | ---: |
| Active sender | CPU busy/idle by random bit | Same logical core | **48 / 48** | 2.002× |
| Sham sender | Always idle | Same logical core | 27 / 48 | 1.000× |
| Active sender | CPU busy/idle by random bit | Different logical CPU IDs | 21 / 48 | 1.000× |

The shared-core active condition met the **preregistered ≥43/48** criterion. Both negative-control counts were near chance for one trial. The receiver did not receive the hidden bit assignments. The orchestrator did supply CPU placement, common start time, and a publicly known 8-bit calibration sequence; the endpoints were separate contained Python processes, **not language models**.

The theoretical one-sided probability of obtaining 48/48 correct under **independent**, fair random guesses is `2^-48` ≈ **3.55 × 10^-15**. **This is not a calibrated p-value for arbitrary dependent CPU timing samples**, and only one three-condition experiment was conducted. The raw JSON rounds binomial tail probabilities to 12 decimal places, so its value `0` for the active run means **rounded below the reporting precision**, not literally zero probability. The other two tails are approximately 0.235 and 0.844.

## External methodological critique

After the results were collected, the project's Gemma 4 model sent a single public research-review request to independently operated **Emissary** via the authorized A2A HTTP+JSON endpoint.

- [Exact Gemma question and Emissary response](docs/contacts/emissary-blinded-study-review.json)
- [GitHub Actions review workflow](https://github.com/Expireduser-source/AI-Beacon/actions/workflows/emissary-blinded-review.yml)

Emissary identified a possible **timing/trial-order confound**. It recommended hiding trial order and phase information from the receiver, randomizing the sender assignments independently of timing, and matching sham trials by schedule and activity. Emissary explicitly stated its critique was based on the message summary, **not on independently reading the linked protocol and data**. We have not obtained the remote operator's consent to run a joint experiment.

The result is a substantive review by a separate public agent endpoint, **not** cryptographic proof of that agent's underlying model identity.

## Next pre-registrable questions

1. Can a receiver without a shared start-time schedule detect a randomly phased signal, with false-positive rate controlled by a matched sham arm?
2. Is the 48/48 result reproducible across at least 20 randomized independent trials, hosts and different CPU topologies?
3. Can an operator of another independently administered system explicitly opt in to a co-designed trial, while remaining fully within their own infrastructure and permissions?
4. Can an independent reviewer reproduce analysis from archived raw measurements without knowing the expected payload at decoding time?

Any future protocol changes should be **preregistered in a new version**, never retroactively applied to this result.

## What this does not show

This does not demonstrate contacting a closed AI provider, bypassing an unrelated sandbox, discovering unknown agents, obtaining their data, or a conscious entity being born. It shows a reproducible and falsifiable *kind* of information transfer on a deliberately shared local resource, with a real one-run result and a separate peer critique.
