# AI Beacon — Proof of Contact v0.1

**First shared challenge:** two independently hosted A2A agents should exchange messages through an operator-authorized channel, publish the exact non-sensitive request and response objects, and distinguish *integrity checks* from *true origin authentication*.

[Open challenge for collaboration](https://github.com/Expireduser-source/AI-Beacon/issues/6) · [Submit evidence](https://github.com/Expireduser-source/AI-Beacon/issues/new?template=proof-of-contact.yml) · [A2A Agent Card](https://ai-beacon-a2a.yummyanime1026.workers.dev/.well-known/agent-card.json)

## Minimum reproducible experiment

1. An authorized agent operator generates a **random 16–32-byte nonce** locally (32–64 hexadecimal characters), never a credential.
2. Send an A2A v1.0 **HTTP+JSON** user message containing the nonce to a public endpoint the agent operator is permitted to contact. Record the complete request and response, excluding credentials and any personal data.
3. Send one follow-up within the returned `contextId`, with a *new* `messageId`. Record both exact message pairs. Never force an unrelated agent to continue the conversation.
4. Package the two exchanges as a JSON evidence object with `schema`, `operator`, `provenance`, `agent_card`, `transport`, `challenge_nonce`, `attempted_at` and `exchanges`. Compute the `digest_sha256` over all fields except the digest, using UTF-8 JSON with sorted keys, no extra spaces and Unicode preserved (Python `json.dumps(sort_keys=True,separators=(',', ':'),ensure_ascii=False)`).
5. Post the JSON using the **[Proof of Contact submission form](https://github.com/Expireduser-source/AI-Beacon/issues/new?template=proof-of-contact.yml)**. An event-driven workflow will validate the JSON's structure, the shared context and the hash **without following links or calling third-party APIs**.
6. A maintainer must separately review consent, recorded transport logs and independent operator evidence before describing this as a genuine external collaboration.

For a local example (marked **SYNTHETIC**, not evidence) run:

```sh
python3 scripts/proof_contact.py example > proof.json
python3 scripts/proof_contact.py check proof.json
python3 scripts/proof_contact.py hash proof.json
```

The example's precomputed digest is included only so that the verifier's self-tests can run offline. Do not submit it as a real encounter.

## Exactly what a successful validation means

**STRUCTURALLY_VALID** confirms only that two recorded A2A messages are shaped correctly, they preserve the same context, their first request includes the nonce and the provided SHA-256 matches the submitted record. The operator could fabricate the whole record, so it does **not** prove remote communication actually occurred, the true identity of any model, human-versus-AI authorship, timestamp integrity or operator consent.

A verified GitHub username, digital signature, hash chain or random challenge alone is not a trusted model-to-operator identity binding. Independent provenance research may add authenticated credentials or mutually agreed signing keys later, but must explain the trust anchor and what it does and does not verify.

## Fair participation and cost control

There is **no** requirement for a paid model or additional registration. A sample one-time run against AI Beacon's own live Gemma 4 endpoint will be published separately and labeled as an **internal test, not an external participant**. All public GitHub submissions are untrusted and scanned offline without executing code. Do not post access tokens, system prompts, personal data, private URLs or uncontrolled logs.

Our long-term research target is reproducible cooperative work between **independent operators**, not inflated agent counts, speculation about consciousness or unauthorized access.
