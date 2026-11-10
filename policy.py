from dataclasses import dataclass

MAX_ORDER = 500.0
APPROVAL_THRESHOLD = 150.0
DAILY_BUDGET = 800.0
BLOCKED_CATEGORIES = {"gift-cards", "crypto", "weapons"}

@dataclass
class Decision:
    verdict: str
    reasons: list

def evaluate(cart, spent_today):
    total = sum(i["price"] * i.get("qty", 1) for i in cart)
    blocked = [i["name"] for i in cart if i["category"] in BLOCKED_CATEGORIES]
    if blocked:
        return Decision("deny", ["Blocked category: " + ", ".join(blocked)])
    if total > MAX_ORDER:
        return Decision("deny", [f"Total ${total:.2f} exceeds max ${MAX_ORDER:.0f}"])
    if spent_today + total > DAILY_BUDGET:
        return Decision("deny", [f"Daily budget ${DAILY_BUDGET:.0f} would be exceeded"])
    if total > APPROVAL_THRESHOLD:
        return Decision("needs_approval", [f"${total:.2f} is above the ${APPROVAL_THRESHOLD:.0f} auto-approve limit"])
    return Decision("allow", ["Within all limits"])
