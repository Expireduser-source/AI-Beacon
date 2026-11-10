# AI Beacon Private Network Console

**Intended one-phone URL:** https://ai-beacon-control.yummyanime1026.workers.dev/

The control Worker is separate from the public `ai-beacon-a2a` gateway. The new Worker has been deployed, but **operator access is NOT yet configured until its `CONSOLE_KEY` Cloudflare secret is set**. Without this secret, all model-control API requests return HTTP 503 (fail closed), and no paid model calls can occur via the console.

## One-time setup from an Android phone

1. Open https://ai-beacon-control.yummyanime1026.workers.dev/ in your browser.
2. Expand **«Первичная настройка ключа на телефоне»** and press **«Создать личный ключ локально»**. The page creates a **random 256-bit key** in your browser using `crypto.getRandomValues`. Do not publish it.
3. Copy the key and store it in your password manager.
4. In another tab open https://dash.cloudflare.com/ and log in to the **Cloudflare account that owns this Worker**. Go to **Workers & Pages → ai-beacon-control → Settings → Variables and Secrets → Add**, choose **Secret**, enter exactly **`CONSOLE_KEY`** for the variable name and paste your random key as the value. Save and deploy any pending binding changes if Cloudflare prompts you.
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

## Troubleshooting

- **HTTP 503 on login:** `CONSOLE_KEY` has not been configured in the Worker; set it in Cloudflare.
- **Wrong key / 401:** Paste exactly the value saved as `CONSOLE_KEY`.
- **No response from Emissary:** The actual remote server can time out, return an error, or change its Agent Card. The run is marked failed rather than inventing a reply.
- **2/2 budget exhausted:** The daily limit resets at 00:00 UTC; repeat attempts count as new runs.
- **Cloudflare Workers dashboard changes:** The menu wording may vary; use Workers & Pages → select `ai-beacon-control` → Settings / Variables / Secrets.
