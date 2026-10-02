"""Receipt data model + all the bill-splitting maths (no Streamlit in here)."""
from pydantic import BaseModel


class Item(BaseModel):
    name: str
    price: float  # total price of the line, e.g. 2 x 150 -> 300


class Receipt(BaseModel):
    is_receipt: bool
    merchant: str
    items: list[Item]
    subtotal: float
    tax: float
    tip: float
    total: float


def to_cents(amount):
    """12.34 -> 1234. Money is handled in whole cents to avoid float errors."""
    return int(round(float(amount) * 100))


def money(cents, symbol):
    sign = "-" if cents < 0 else ""
    return f"{sign}{symbol}{abs(cents) / 100:,.2f}"


def parse_people(text):
    """'Asha, Ravi , asha' -> ['Asha', 'Ravi'] (trimmed, no duplicates)."""
    names, seen = [], set()
    for part in text.split(","):
        name = part.strip()
        if name and name.lower() not in seen:
            seen.add(name.lower())
            names.append(name)
    return names


def split_bill(items, people, extras_cents):
    """items: list of (price_in_cents, [people who shared it]).
    Tax + tip (extras_cents) are shared in proportion to what each person ordered.
    Returns ({person: total_in_cents}, unassigned_cents). Totals add up exactly."""
    if not people:
        return {}, 0

    subtotals = {person: 0 for person in people}
    unassigned = 0
    for price_cents, assigned in items:
        assigned = [p for p in assigned if p in subtotals]
        if not assigned:
            unassigned += price_cents
            continue
        base, remainder = divmod(price_cents, len(assigned))
        for index, person in enumerate(assigned):
            subtotals[person] += base + (1 if index < remainder else 0)

    extra = {person: 0 for person in people}
    ordered_subtotal = sum(subtotals.values())
    if extras_cents:
        if ordered_subtotal > 0:
            for person in people:
                extra[person] = extras_cents * subtotals[person] // ordered_subtotal
        else:
            base, remainder = divmod(extras_cents, len(people))
            for index, person in enumerate(people):
                extra[person] = base + (1 if index < remainder else 0)
        # hand out leftover cents so the shares add up exactly
        leftover = extras_cents - sum(extra.values())
        order = sorted(people, key=lambda p: subtotals[p], reverse=True)
        step = 1 if leftover > 0 else -1
        position = 0
        while leftover != 0:
            extra[order[position % len(order)]] += step
            leftover -= step
            position += 1

    totals = {person: subtotals[person] + extra[person] for person in people}
    return totals, unassigned


def build_breakdown(merchant, rows, tax_cents, tip_cents, totals, unassigned, symbol):
    """rows: list of (name, price_in_cents, [people]). Returns plain text for the email."""
    subtotal = sum(price for _, price, _ in rows)
    grand = subtotal + tax_cents + tip_cents
    lines = [f"Bill: {merchant or 'Receipt'}", "", "Items:"]
    for name, price, assigned in rows:
        who = ", ".join(assigned) if assigned else "not assigned"
        lines.append(f"- {name}: {money(price, symbol)} ({who})")
    lines += [
        "",
        f"Subtotal: {money(subtotal, symbol)}",
        f"Tax / service: {money(tax_cents, symbol)}",
        f"Tip: {money(tip_cents, symbol)}",
        f"Grand total: {money(grand, symbol)}",
        "",
        "Who pays what:",
    ]
    for person, cents in totals.items():
        lines.append(f"- {person}: {money(cents, symbol)}")
    if unassigned:
        lines.append("")
        lines.append(f"Note: {money(unassigned, symbol)} of items were not assigned to anyone.")
    return "\n".join(lines)