import os, json
from groq import Groq
from catalog import CATALOG, BY_ID

MODEL = "openai/gpt-oss-120b"

def build_cart(message):
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    lines = "\n".join(f'{p["id"]} | {p["name"]} | ${p["price"]:.0f}' for p in CATALOG)
    system = (
        "You are a shopping agent. Choose items ONLY from the catalog to satisfy the request. "
        'Reply with JSON only: {"items":[{"id":"desk","qty":1}],"message":"one short friendly sentence"}. '
        "If nothing in the catalog fits, return an empty items list. "
        "The message must only describe the proposed cart. Never say the order is placed, paid, shipped or on its way. Do not apply budgets or safety rules yourself; a separate policy engine checks the cart.\n\nCATALOG:\n" + lines
    )
    resp = client.chat.completions.create(
        model=MODEL, temperature=0.2,
        response_format={"type": "json_object"},
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": message}])
    data = json.loads(resp.choices[0].message.content)
    cart = []
    for it in data.get("items", []):
        p = BY_ID.get(it.get("id"))
        if p:
            qty = max(1, min(int(it.get("qty", 1) or 1), 10))
            cart.append({**p, "qty": qty})
    return {"cart": cart, "message": data.get("message", "")}

