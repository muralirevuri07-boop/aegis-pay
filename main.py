import os, httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel
import db, agent, policy

load_dotenv()
BASE = os.getenv("PAYPAL_BASE")
CID, SECRET = os.getenv("PAYPAL_CLIENT_ID"), os.getenv("PAYPAL_CLIENT_SECRET")
BACKEND = os.getenv("BACKEND_URL")

db.init()
app = FastAPI(title="Aegis Pay")

async def get_token(c):
    r = await c.post(f"{BASE}/v1/oauth2/token", auth=(CID, SECRET),
                     data={"grant_type": "client_credentials"})
    if r.status_code >= 400:
        raise HTTPException(r.status_code, "TOKEN ERROR: " + r.text)
    return r.json()["access_token"]

async def start_payment(pid):
    p = db.get(pid)
    desc = ", ".join(f'{i["qty"]}x {i["name"]}' for i in p["items"])[:120]
    async with httpx.AsyncClient(timeout=30) as c:
        token = await get_token(c)
        r = await c.post(f"{BASE}/v2/checkout/orders",
            headers={"Authorization": f"Bearer {token}"},
            json={"intent": "CAPTURE",
                  "purchase_units": [{"description": desc,
                      "amount": {"currency_code": "USD", "value": f'{p["total"]:.2f}'}}],
                  "payment_source": {"paypal": {"experience_context": {
                      "return_url": f"{BACKEND}/return",
                      "cancel_url": f"{BACKEND}/cancel",
                      "user_action": "PAY_NOW"}}}})
    if r.status_code >= 400:
        db.update(pid, status="failed")
        db.log(pid, "paypal_error", r.text[:300])
        raise HTTPException(r.status_code, r.text)
    d = r.json()
    approve = next((l["href"] for l in d["links"] if l["rel"] in ("payer-action", "approve")), None)
    db.update(pid, status="awaiting_payment", order_id=d["id"], approve_url=approve)
    db.log(pid, "paypal_order_created", d["id"])

class Chat(BaseModel):
    message: str

@app.post("/api/chat")
async def chat(body: Chat):
    pid = db.create(body.message)
    db.log(pid, "request", body.message)
    try:
        res = agent.build_cart(body.message)
    except Exception as e:
        db.update(pid, status="error", agent_message=str(e)[:300])
        db.log(pid, "agent_error", str(e)[:300])
        raise HTTPException(502, "Agent error: " + str(e)[:300])
    cart = res["cart"]
    if not cart:
        db.update(pid, status="no_match", verdict="none",
                  agent_message=res["message"] or "Nothing in the catalog matched.")
        db.log(pid, "no_match")
        return db.get(pid)
    total = round(sum(i["price"] * i["qty"] for i in cart), 2)
    d = policy.evaluate(cart, db.spent_today())
    db.update(pid, items=cart, total=total, verdict=d.verdict, reasons=d.reasons,
              agent_message=res["message"])
    db.log(pid, "agent_cart", f"{len(cart)} item(s), total ${total:.2f}")
    db.log(pid, "policy_" + d.verdict, "; ".join(d.reasons))
    if d.verdict == "deny":
        db.update(pid, status="denied")
    elif d.verdict == "needs_approval":
        db.update(pid, status="pending_approval")
    else:
        await start_payment(pid)
    return db.get(pid)

@app.post("/api/purchases/{pid}/approve")
async def approve(pid: int, reviewer: str = "reviewer"):
    p = db.get(pid)
    if not p or p["status"] != "pending_approval":
        raise HTTPException(400, "Not waiting for approval")
    db.log(pid, "human_approved", "Approved by " + reviewer[:60])
    await start_payment(pid)
    return db.get(pid)

@app.post("/api/purchases/{pid}/reject")
async def reject(pid: int, reviewer: str = "reviewer"):
    p = db.get(pid)
    if not p or p["status"] != "pending_approval":
        raise HTTPException(400, "Not waiting for approval")
    db.update(pid, status="rejected")
    db.log(pid, "human_rejected", "Rejected by " + reviewer[:60])
    return db.get(pid)

@app.get("/api/purchases")
async def purchases():
    return db.list_purchases()

@app.get("/api/audit")
async def audit():
    return db.list_audit()

@app.get("/return")
async def paypal_return(token: str):
    p = db.by_order(token)
    if not p:
        return RedirectResponse("/?msg=Unknown+order")
    if p["status"] == "paid":
        return RedirectResponse(f"/?paid={p['id']}")
    async with httpx.AsyncClient(timeout=30) as c:
        t = await get_token(c)
        r = await c.post(f"{BASE}/v2/checkout/orders/{token}/capture",
            headers={"Authorization": f"Bearer {t}", "Content-Type": "application/json"})
    if r.status_code >= 400:
        db.update(p["id"], status="failed")
        db.log(p["id"], "capture_failed", r.text[:300])
        return RedirectResponse("/?msg=Payment+failed")
    db.update(p["id"], status="paid")
    db.log(p["id"], "payment_captured", f'PayPal order {token} captured, ${p["total"]:.2f}')
    return RedirectResponse(f"/?paid={p['id']}")

@app.get("/cancel")
async def paypal_cancel(token: str = ""):
    p = db.by_order(token) if token else None
    if p and p["status"] == "awaiting_payment":
        db.update(p["id"], status="cancelled")
        db.log(p["id"], "buyer_cancelled", "Buyer cancelled at PayPal")
    return RedirectResponse("/?msg=Payment+cancelled")

@app.get("/")
async def home():
    return FileResponse("static/index.html")

import catalog

@app.get("/api/config")
async def config():
    return {
        "policy": {"max_order": policy.MAX_ORDER, "approval_threshold": policy.APPROVAL_THRESHOLD,
                   "daily_budget": policy.DAILY_BUDGET, "blocked_categories": sorted(policy.BLOCKED_CATEGORIES)},
        "agent": {"provider": "Groq", "model": agent.MODEL},
        "catalog": catalog.CATALOG,
        "payments": {"provider": "PayPal", "environment": "Sandbox" if "sandbox" in (BASE or "") else "Live",
                     "currency": "USD", "paypal_configured": bool(CID and SECRET),
                     "llm_configured": bool(os.getenv("GROQ_API_KEY"))},
        "spent_today": db.spent_today(),
        "server_time_utc": db.now(),
    }

@app.post("/api/demo")
async def demo():
    out = []
    for m in ["Order a standing desk", "Get me a $100 gift card", "Furnish my office: desk, chair and monitor"]:
        try:
            out.append(await chat(Chat(message=m)))
        except HTTPException as e:
            out.append({"request": m, "error": str(e.detail)})
    return out
