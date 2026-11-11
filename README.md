# Aegis Pay: governed agentic commerce on PayPal

An AI shopping agent can propose purchases, but it can never spend money on its own. A deterministic policy engine decides every cart, risky orders wait for a human, and payments run through the real PayPal Orders API (Sandbox).

**Live demo:** https://aegis-pay-v82h.onrender.com
(Free hosting: the first load can take about a minute to wake up.)

## How it works

1. A user describes what to buy in plain language.
2. The agent (Groq, openai/gpt-oss-120b) picks items from a product catalog. Items outside the catalog are discarded.
3. The policy engine evaluates the cart and returns allow, needs approval, or deny. The LLM never makes this decision.
4. Allowed carts go straight to PayPal. Carts above the threshold wait for a human reviewer. Denied carts never reach PayPal.
5. A PayPal order is created server-side and captured on return. Every step is written to an audit log.

## Policy rules (policy.py)

| Rule | Setting | Effect |
|---|---|---|
| Maximum order | $500 | Deny |
| Human approval threshold | $150 | Wait for reviewer |
| Daily budget | $800 settled spend | Deny |
| Blocked categories | gift cards, crypto, weapons | Deny |

## Console sections

Executive Overview, Agent Management, Transaction Management, Policy Administration, Approval Management, Risk & Compliance, Audit & Reporting (with CSV export), System Administration. All figures are computed from real stored transactions and audit events.

## Try it

1. Open the live demo, go to Transaction Management, click Run sample scenarios (3 real requests).
2. Or submit "Buy a keyboard and a mouse" ($118, auto-approved) and pay with the PayPal sandbox buyer account given in the Devpost testing instructions.
3. Submit "Order a standing desk" ($349), then approve it under Approval Management and pay.

## Stack

FastAPI, SQLite, Groq, PayPal Orders v2 (Sandbox), plain HTML/JS front end, hosted on Render.

## Run locally (optional)

Install dependencies with pip install -r requirements.txt, then create a file named .env (it is gitignored, so you must make your own) containing PAYPAL_CLIENT_ID, PAYPAL_CLIENT_SECRET, PAYPAL_BASE=https://api-m.sandbox.paypal.com, GROQ_API_KEY and BACKEND_URL=http://localhost:8000. Start with: uvicorn main:app --reload

## Limitations (honest)

- PayPal Sandbox only; no real money moves.
- No reviewer login: anyone with the URL can approve. Reviewer authentication and identity in the audit trail are the next step.
- Seeded 12-product catalog, not live merchant data.
- SQLite on free hosting resets on redeploy.

## Roadmap

Reviewer authentication, PostgreSQL, live merchant catalog adapters (for example Shopify and WooCommerce) governed by the same policy engine, and PayPal webhook verification.

## License

MIT
