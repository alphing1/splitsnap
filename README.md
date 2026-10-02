# 🧾 SplitSnap

An AI expense tracker and emergency bill splitter. Photograph a receipt and
Gemini reads it into **structured data** (merchant, items, prices, tax, tip,
total). You tick who had what, and SplitSnap works out exactly what each
person owes. One click emails you the breakdown.

Built with Streamlit, Google Gemini (vision + structured JSON output) and Gmail SMTP.

## Features
- One-time onboarding: name, email, who is splitting, currency
- Receipt photo -> structured JSON (Pydantic schema) instead of loose text
- Editable table: fix misread prices, add/delete rows
- Even split or item-by-item split (tick-boxes per person)
- Tax and tip shared in proportion to what each person ordered
- Exact-to-the-cent maths in Python (not trusted to the AI)
- Warning when the items do not add up to the printed total
- Chat for follow-up questions, scoped to receipts and bills only
- Email breakdown + CSV download

## Screenshots
_Add 2-3 screenshots of your deployed app here._

## Run locally
1. `python -m venv venv` and activate it
2. `pip install -r requirements.txt`
3. Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and fill in
   your Gemini API key, Gmail address and Gmail App Password
4. `streamlit run app.py`
5. Optional: `python test_splitter.py` checks the split maths

## Project structure
- `app.py` - the Streamlit app
- `prompts.py` - the AI's instructions, kept separate from the logic
- `splitter.py` - receipt schema and bill-splitting maths
- `test_splitter.py` - small tests for the maths

## Deploy
Push to GitHub (never commit `secrets.toml`), deploy on share.streamlit.io and
paste your secrets under Settings -> Secrets.