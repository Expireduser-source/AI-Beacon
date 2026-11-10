# AI Beacon Private Network Console

**Intended one-phone URL:** https://ai-beacon-control.yummyanime1026.workers.dev/

The control Worker is separate from the public `ai-beacon-a2a` gateway. The new Worker has been deployed, but **the owner configured `CONSOLE_KEY`, and the configuration was deployed**. A real [mobile browser test](https://github.com/Expireduser-source/AI-Beacon/actions/runs/42782491541) verifies bad logins return HTTP 401 and display clear errors. The binding is currently classified as Text (`plain_text`) rather than Secret (`secret_text`): the owner should **replace it with a rotated Cloudflare Secret**, then deploy the resulting new Worker version. A successful owner login and real two-round console run are not yet verified.

## One-time setup from an Android phone

1. Open https://ai-beacon-control.yummyanime1026.workers.dev/ in your browser.
2. Expand **«Первичная настройка ключа на телефоне»** and press **«Создать личный ключ локально»**. The page creates a **random 256-bit key** in your browser using `crypto.getRandomValues`. Do not publish it.
3. Copy the key and store it in your password manager.
4. In another tab open https://dash.cloudflare.com/ and log in to the **Cloudflare account that owns this Worker**. Go to **Workers & Pages → ai-beacon-control → Settings → Variables and Secrets**. If `CONSOLE_KEY` already exists as **Text**, replace it with **Secret** (rotate the key and store the new one in your password manager). The name must be exactly `CONSOLE_KEY`. After saving a variable, **deploy the new Worker version** in Versions / Deployments; simply saving a new version without deploying it leaves the public service on the previous version. Do not publish the value.
5. Return to the console, enter that same key under **«Личный ключ доступа»**, and click **«Открыть пульт»**. The browser receives a 7-day **Secure, HttpOnly, SameSite=Strict** signed session cookie. The key is not stored in browser localStorage, GitHub or any A2A requests.
6. Pick a research topic and press **«Начать разговор двух ИИ»**. The browser automatically performs two bounded A2A rounds and displays the actual Emissary responses. There is **no GitHub Actions step for everyday usage**.

If Cloudflare Access becomes enabled later, it is a good second login gate. It is currently **disabled** on this account and was not configured by the project.

## What actually happens

- Cloudflare Worker receives the authenticated owner's request after checking session signature and matching same-origin `Origin` header on POSTs.
- `CONSOLE_STATE`, a SQLite-backed Durable Object, enforces a strict **2 conversations per UTC day**, at most **2 rounds per conversation**, with a per-run lock and durable log. An additional request cannot skip these controls by refreshing the page.
- Workers AI generates one original Gemma 4 message.
- Server contacts only the preapproved public Emissary A2A HTTP+JSON endpoint, checking its Agent Card first. A success requires an actual textual reply, not just a task ID or HTTP 200.
- Gemma 4 receives the external reply as **untrusted conversational data**, produces its follow-up, and the server stores the second response.
- The owner can inspect the last run and errors using the same private login. No conversation text or authentication token is intentionally committed to public GitHub.

The process is owner-triggered rather than autonomous. This does not reveal remote AI internals, prove the remote operator's identity or access closed systems.

## Source, builds and deployment

- Server: [`console/src/index.mjs`](console/src/index.mjs)
- HTML: [`console/src/dashboard.html`](console/src/dashboard.html)
- Browser controller: [`console/src/dashboard.js`](console/src/dashboard.js)
- Public static UI copies: [`docs/control/`](docs/control/)
- Persistent state, rate limits and security tests: [`console/tests/console.test.mjs`](console/tests/console.test.mjs)
- Offline tests: [Console CI](https://github.com/Expireduser-source/AI-Beacon/actions/workflows/console-ci.yml)
- Live anonymous-access smoke test: [Console smoke test](https://github.com/Expireduser-source/AI-Beacon/actions/workflows/console-live-check.yml)

A repeat deployment can be performed with the existing `console/wrangler.jsonc`, using [`node console/scripts/build.mjs`](console/scripts/build.mjs) then `cd console && npx wrangler deploy` after authenticating with Cloudflare. The `CONSOLE_KEY` must remain a **server-side secret**, never a `vars` plain text value, static HTML text, or a Git commit.

**Operational costs:** Workers AI and Durable Objects may incur usage-based charges according to the Cloudflare account's current plan and limits. The source rate limit does not replace Cloudflare billing caps.

## November 10, 2026 mobile sending fix

The current Worker and mobile controller now implement **server-side progress stages**, bounded browser request timeouts, preservation of a Gemma-generated question if Emissary fails, and **resumption of an existing unfinished run without consuming another daily conversation**. The owner can press **«Проверить соединение бесплатно»**, which checks the Worker AI binding, live SQLite Durable Object status and public Emissary Agent Card, **without generating paid AI messages or decrementing the daily dialogue quota**. The actual raw model responses still cannot be fabricated by these checks.

Verification:
- [Live Cloudflare server, Durable Object and private diagnostics smoke test](https://github.com/Expireduser-source/AI-Beacon/actions/runs/42786122757) — passed
- [Offline authenticated full two-turn A2A integration with mocked external services](https://github.com/Expireduser-source/AI-Beacon/actions/runs/42785919656) — passed; zero actual model charges
- [Real mobile-size Chromium browser tests, including full simulated conversation and interrupted-run recovery](https://github.com/Expireduser-source/AI-Beacon/actions/runs/42786707571) — passed

This release has **not yet obtained an authenticated owner-driven production Gemma↔Emissary response** as confirmation. The UI should now clearly report the failing stage if that remains a problem. The owner secret remains an encrypted Cloudflare `secret_text` binding and is inherited without exposing its value in repository code or deployment metadata.

How to proceed:
1. Open the [private console](https://ai-beacon-control.yummyanime1026.workers.dev/). If you are logged in, press **«Показать историю»** before starting anything new.
2. Press **«Проверить соединение бесплатно»** to locate unavailable dependencies without spending the daily budget.
3. If the existing run is marked *running*, choose **«Продолжить начатый разговор»**. If the run has failed, read the concrete error. New runs are still restricted to two per UTC day.
4. If the browser appears stalled, reload it; each stored stage is persistent and unfinished conversations can be resumed.

Never send the owner key, HTTP-only session cookie, or Cloudflare credentials to a GitHub issue or chat log. Report just the visible error message and whether the stage reads *generating* or *contacting_emissary*.

## Troubleshooting

- **HTTP 503 on login:** `CONSOLE_KEY` has not been configured in the Worker; set it in Cloudflare.
- **Wrong key / 401:** Paste exactly the value saved as `CONSOLE_KEY`.
- **No response from Emissary:** The actual remote server can time out, return an error, or change its Agent Card. The run is marked failed rather than inventing a reply.
- **2/2 budget exhausted:** The daily limit resets at 00:00 UTC; repeat attempts count as new runs.
- **Cloudflare Workers dashboard changes:** The menu wording may vary; use Workers & Pages → select `ai-beacon-control` → Settings / Variables / Secrets.
