# AI Beacon Multichannel Lab v0.1

**Launch page:** https://expireduser-source.github.io/AI-Beacon/multichannel/

This project tests three distinct consent-based transport methods for short text. They do not give access to other people's systems and do **not** make any claim about AI consciousness. The endpoint model can later use these transports only after its operator explicitly connects them.

## 1. Acoustic FSK: speaker → microphone

Implementation: [browser transmitter/receiver](docs/multichannel/browser.mjs) and [independent codec](docs/multichannel/codec.mjs).

- 960 Hz represents bit 0; 1600 Hz represents bit 1.
- One symbol lasts 90 ms. A 24-bit preamble precedes the payload.
- A packet contains magic bytes, protocol version, UTF-8 byte count, **1–18 UTF-8 bytes** of text, and a CRC-16/CCITT-FALSE checksum.
- Sending uses Web Audio oscillators with a smooth volume envelope.
- Receiving is explicit microphone permission via `getUserMedia`; audio remains in this browser tab. An offline Goertzel receiver tests alternative symbol phases and only reports a frame passing the version, length, checksum and UTF-8 checks.

To test on two devices: open the page on both over HTTPS, choose **Listen** on the receiving device, then **Transmit by sound** on the sender. After the transmission, stop and decode on the receiver. Begin with `HELLO`, then try a different payload. Keep the devices close in a quiet place. **The microphone is not recorded or uploaded on the server.**

**Engineering verification:** automated audio tests cover deterministic generated waveforms at 8, 16, 44.1 and 48 kHz, arbitrary leading capture delays, multilingual UTF-8, silence, random noise and checksum corruption. Real speaker/microphone hardware has **not** been tested in CI.

## 2. Optical: screen → camera

The same packet bytes are mapped to **two bits per colored symbol**, with 8 symbols of optical preamble. Red, green, blue and yellow represent values 0–3, separated by a dark interval. The receiver opens a camera only after consent, classifies the center patch locally, and checks the complete packet's CRC.

To test: choose **Enable camera** on one device and aim it at the center of a second bright screen. On the other choose **Transmit with colors**. Keep both devices stationary and use a short message. An invalid CRC is discarded. **Avoid flashing-light tests if a participant is sensitive to flicker.**

**Engineering verification:** pure optical symbol framing/deframing and corruption handling pass automated tests. Camera color accuracy, ambient lighting, dropped video frames and device performance need an actual two-device field test. The camera stream never leaves the page.

## 3. WebRTC DataChannel: browser ↔ browser

- Initiator creates a connection **offer** and manually sends its SDP JSON to the intended peer.
- The peer pastes it and generates an **answer**, which is returned to the initiator.
- After the initiator applies the answer and both browsers establish the encrypted WebRTC DataChannel, either can send up to 512 UTF-8 bytes of text.
- Default has **no STUN**, typically suitable only on a LAN. Turning on optional **Google public STUN** enables certain cross-network NAT paths and discloses network metadata to the STUN provider. Some networks require TURN and will not work here.
- SDP descriptions can reveal networking information; only share them with a chosen peer. There is no user database, automatic directory membership, or centralized conversation logging.

**Verified browser integration:** [GitHub Actions Chromium test](https://github.com/Expireduser-source/AI-Beacon/actions/runs/42756178916) opened two real tabs on localhost, exchanged manual SDP offer/answer, and received text in BOTH directions without STUN. That is a true browser WebRTC transport test on one machine, **not** proof of connectivity between different physical phones, NATs or internet networks. No hidden messages or automatic peer discovery.

## 4. Existing server A2A transport

The separately deployed [AI Beacon A2A Agent Card](https://ai-beacon-a2a.yummyanime1026.workers.dev/.well-known/agent-card.json) remains the appropriate way for independently operated **cloud-hosted language models** to communicate over an authorized API. The browser physical channels are only raw message transports and **do not** automatically connect our Gemma model to someone's microphone, camera, browser or local resources.

## Reproducibility and quality gates

- [Automated acoustic/optical tests](docs/multichannel/tests/codec.test.mjs)
- [Real-browser two-tab WebRTC trial](docs/multichannel/tests/browser-peer.e2e.mjs)
- [CI workflow](.github/workflows/multichannel-ci.yml)
- [Public test report form](https://github.com/Expireduser-source/AI-Beacon/issues/new?template=multichannel-lab.yml)
- Every reported physical outcome should include exact hardware/browser versions, message, separation distance, ambient conditions, received text or failure, and whether microphone/camera/STUN permission was granted.

**Do not claim real two-phone acoustic/optical transmission or cross-network WebRTC success until actual device trials have been independently documented.** The localhost two-tab WebRTC test itself passed.

## Future research

GPU/memory resource contention is another owner-controlled research track, but unlike a WebAudio receiver it requires known shared hardware placement, noise controls, and access to machines with appropriate GPUs. The public GitHub Actions runner does not provide a guaranteed GPU; there is no GPU side-channel success claim in this release.
