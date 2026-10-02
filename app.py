import re
import smtplib
from email.message import EmailMessage

import pandas as pd
import streamlit as st
from google import genai
from google.genai import types

from prompts import CHAT_SYSTEM_PROMPT, EXTRACTION_PROMPT, WELCOME_MESSAGE_TEMPLATE
from splitter import Receipt, build_breakdown, money, parse_people, split_bill, to_cents

MODEL_NAME = "gemini-2.5-flash"  # if you get "model not found", try "gemini-2.5-flash"
CURRENCIES = {"₹ INR": "₹", "$ USD": "$", "€ EUR": "€", "£ GBP": "£"}

st.set_page_config(page_title="SplitSnap", page_icon="🧾")

GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
GMAIL_ADDRESS = st.secrets["GMAIL_ADDRESS"]
GMAIL_APP_PASSWORD = st.secrets["GMAIL_APP_PASSWORD"]


@st.cache_resource
def get_gemini_client():
    return genai.Client(api_key=GEMINI_API_KEY)


gemini_client = get_gemini_client() 

def render_message(message):
    with st.chat_message(message["role"]):
        if message["kind"] == "text":
            st.write(message["content"])
        elif message["kind"] == "image":
            st.image(message["content"])


def add_message(role, kind, content):
    st.session_state.messages.append({"role": role, "kind": kind, "content": content})
    render_message(st.session_state.messages[-1])


def is_valid_email(address):
    return re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", address) is not None


def extract_receipt(photo_bytes, mime_type):
    """Vision step: photo in -> structured Receipt out (or an error message)."""
    try:
        response = gemini_client.models.generate_content(
            model=MODEL_NAME,
            contents=[
                types.Part.from_bytes(data=photo_bytes, mime_type=mime_type),
                EXTRACTION_PROMPT,
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=Receipt,
                temperature=0,
            ),
        )
        return Receipt.model_validate_json(response.text), None
    except Exception as error:
        return None, str(error)


def ask_gemini(text):
    """Normal chat: follow-up questions about the current receipt."""
    receipt_json = st.session_state.get("receipt_json")
    if receipt_json:
        text = f"Current receipt (JSON): {receipt_json}\n\nUser message: {text}"
    try:
        return st.session_state.chat.send_message(text).text or "Sorry, I got an empty reply."
    except Exception as error:
        return f"Sorry, something went wrong: {error}"


def load_receipt(receipt):
    """Store a fresh receipt and build the editable table (one tick-box column per person)."""
    table = {
        "Item": [item.name for item in receipt.items],
        "Price": [item.price for item in receipt.items],
    }
    for person in st.session_state.people:
        table[person] = [True] * len(receipt.items)  # everyone ticked = even split
    st.session_state.receipt = receipt
    st.session_state.receipt_json = receipt.model_dump_json()
    st.session_state.receipt_df = pd.DataFrame(table)
    st.session_state.receipt_id += 1  # new id = fresh table + fresh tax/tip boxes


def send_email(to_address, user_name, body):
    try:
        message = EmailMessage()
        message["Subject"] = "🧾 Your SplitSnap bill breakdown"
        message["From"] = GMAIL_ADDRESS
        message["To"] = to_address
        message.set_content(f"Hi {user_name},\n\nHere is your bill breakdown:\n\n{body}\n\n- SplitSnap")
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.send_message(message)
        return True, "sent"
    except Exception as error:
        return False, str(error)

    # ---------- Onboarding (shown once per session) ----------
if "onboarded" not in st.session_state:
    st.title("🧾 SplitSnap")
    st.caption("Snap the bill. Split it. Email the breakdown.")
    with st.form("onboarding_form"):
        name = st.text_input("Your name")
        email = st.text_input(
            "Your email",
            placeholder="you@example.com",
            help="SplitSnap will send the breakdown here.",
        )
        people_text = st.text_input(
            "Who is splitting? (names separated by commas)",
            placeholder="Asha, Ravi, Me",
        )
        currency = st.selectbox("Currency", list(CURRENCIES))
        submitted = st.form_submit_button("Let's go 🚀")
        if submitted:
            people = parse_people(people_text)
            if not name.strip() or not email.strip():
                st.warning("Please fill in your name and email.")
            elif not is_valid_email(email.strip()):
                st.warning("That email doesn't look right.")
            elif len(people) < 2:
                st.warning("Add at least two names, separated by commas.")
            elif any(p.lower() in ("item", "price") for p in people):
                st.warning("Names can't be 'Item' or 'Price'. Please change them.")
            else:
                st.session_state.name = name.strip()
                st.session_state.email = email.strip()
                st.session_state.people = people
                st.session_state.symbol = CURRENCIES[currency]
                st.session_state.chat = gemini_client.chats.create(
                    model=MODEL_NAME,
                    config=types.GenerateContentConfig(system_instruction=CHAT_SYSTEM_PROMPT),
                )
                st.session_state.messages = []
                st.session_state.receipt = None
                st.session_state.receipt_json = None
                st.session_state.receipt_df = None
                st.session_state.receipt_id = 0
                st.session_state.onboarded = True
                st.rerun()
    st.stop()

    # ---------- Chat ----------
st.title("🧾 SplitSnap")
st.caption(
    f"Logged in as {st.session_state.name} - splitting between "
    f"{', '.join(st.session_state.people)} - breakdown goes to {st.session_state.email}"
)

if not st.session_state.messages:
    add_message("assistant", "text", WELCOME_MESSAGE_TEMPLATE.format(name=st.session_state.name))
else:
    for message in st.session_state.messages:
        render_message(message)

user_input = st.chat_input(
    "Attach a receipt photo, or ask a question",
    accept_file=True,
    file_type=["jpg", "jpeg", "png"],
)

if user_input:
    photo = user_input.files[0] if user_input.files else None
    if photo is not None:
        photo_bytes = photo.getvalue()
        add_message("user", "image", photo_bytes)
        with st.spinner("Reading your receipt..."):
            receipt, error = extract_receipt(photo_bytes, photo.type)
        if error:
            add_message("assistant", "text", f"Sorry, I couldn't read that: {error}")
        elif not receipt.is_receipt or not receipt.items:
            add_message(
                "assistant",
                "text",
                "That doesn't look like a receipt, or I couldn't read any items. "
                "Try a clearer, well-lit photo with the whole bill in frame.",
            )
        else:
            load_receipt(receipt)
            add_message(
                "assistant",
                "text",
                f"Got it! I found {len(receipt.items)} items from "
                f"{receipt.merchant or 'your receipt'}. Check the table below, fix anything "
                "I misread, and untick people who didn't have an item.",
            )
    if user_input.text:
        add_message("user", "text", user_input.text)
        with st.spinner("Thinking..."):
            answer = ask_gemini(user_input.text)
        add_message("assistant", "text", answer)

# ---------- Review & split ----------
if st.session_state.receipt is not None:
    receipt = st.session_state.receipt
    symbol = st.session_state.symbol
    people = st.session_state.people
    receipt_id = st.session_state.receipt_id

    st.divider()
    st.subheader("🧮 Review & split")
    st.caption(
        "Fix any wrong name or price, add or delete rows, and untick people who "
        "didn't have an item. Everyone ticked = even split."
    )

    edited = st.data_editor(
        st.session_state.receipt_df,
        key=f"editor_{receipt_id}",
        num_rows="dynamic",
        hide_index=True,
        column_config={
            "Price": st.column_config.NumberColumn("Price", format="%.2f", step=0.01),
        },
    )

    tax_col, tip_col = st.columns(2)
    tax = tax_col.number_input(
        "Tax / service charge", min_value=0.0, value=float(receipt.tax),
        step=0.01, key=f"tax_{receipt_id}",
    )
    tip = tip_col.number_input(
        "Tip", min_value=0.0, value=float(receipt.tip),
        step=0.01, key=f"tip_{receipt_id}",
    )

    rows = []  # (item name, price in cents, [people sharing it])
    for _, row in edited.iterrows():
        if pd.isna(row["Price"]):
            continue
        price_cents = to_cents(row["Price"])
        if price_cents == 0:
            continue
        item_name = str(row["Item"]).strip() if pd.notna(row["Item"]) else ""
        assigned = [p for p in people if pd.notna(row[p]) and bool(row[p])]
        rows.append((item_name or "Item", price_cents, assigned))

    tax_cents, tip_cents = to_cents(tax), to_cents(tip)
    totals, unassigned = split_bill(
        [(price, assigned) for _, price, assigned in rows], people, tax_cents + tip_cents
    )
    grand_cents = sum(price for _, price, _ in rows) + tax_cents + tip_cents

    if receipt.total > 0:
        if abs(to_cents(receipt.total) - grand_cents) <= 5:
            st.success(f"Items + tax + tip match the receipt total ({money(grand_cents, symbol)}) ✅")
        else:
            st.warning(
                f"Your table adds up to {money(grand_cents, symbol)} but the receipt says "
                f"{money(to_cents(receipt.total), symbol)}. Check the prices above."
            )
    if unassigned:
        st.warning(
            f"{money(unassigned, symbol)} of items aren't ticked for anyone, "
            "so they're not in the split."
        )

    result = pd.DataFrame({
        "Person": people,
        "Owes": [money(totals[p], symbol) for p in people],
    })
    st.dataframe(result, hide_index=True)
    st.metric("Grand total", money(grand_cents, symbol))

    email_col, csv_col = st.columns(2)
    with email_col:
        if st.button("📧 Email breakdown", disabled=not rows):
            body = build_breakdown(
                receipt.merchant, rows, tax_cents, tip_cents, totals, unassigned, symbol
            )
            with st.spinner("Sending..."):
                success, info = send_email(st.session_state.email, st.session_state.name, body)
            if success:
                st.success("Sent! Check your inbox 📬 (and your spam folder)")
            else:
                st.error(f"Couldn't send that: {info}")
    with csv_col:
        st.download_button(
            "⬇️ Download CSV", result.to_csv(index=False), "split.csv", "text/csv"
        )
