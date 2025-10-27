import streamlit as st
import requests
import pandas as pd
import time

st.set_page_config(page_title="Polymarket Portugal Election Tracker", layout="wide")

# ---- CONFIG ----
EVENT_ID = "1761563334297"  # Portugal Presidential Election
CANDIDATES = [
    "Henrique Gouveia e Melo (IND)",
    "Luís Marques Mendes (PSD)",
    "António José Seguro (IND)",
    "André Ventura (CH)",
]
THRESHOLD_LOW = 0.97
THRESHOLD_HIGH = 1.03
DEPTH = 100

# ---- FUNCTIONS ----
@st.cache_data(ttl=30)
def get_orderbooks():
    url = f"https://clob.polymarket.com/markets?event_id={EVENT_ID}"
    resp = requests.get(url)
    resp.raise_for_status()
    data = resp.json()
    return {m["question"]: m for m in data["markets"]}

def top_price_with_volume(orders, target_volume=DEPTH):
    filled, weighted_price = 0, 0
    for o in orders:
        v = min(target_volume - filled, o["size"])
        weighted_price += o["price"] * v
        filled += v
        if filled >= target_volume:
            break
    return weighted_price / filled if filled else None

def get_best_prices(market):
    bids = market["orderbook"]["bids"]
    asks = market["orderbook"]["asks"]
    return top_price_with_volume(bids), top_price_with_volume(asks)

def get_market_data():
    markets = get_orderbooks()
    rows = []
    for cand in CANDIDATES:
        m = markets.get(cand)
        if not m:
            continue
        bid, ask = get_best_prices(m)
        rows.append({"Candidate": cand, "Bid": bid, "Ask": ask})
    return pd.DataFrame(rows)

# ---- UI ----
st.title("🇵🇹 Polymarket – Portugal Presidential Election Tracker")

auto_refresh = st.checkbox("Auto-refresh every 30s", value=True)
if st.button("Refresh now") or auto_refresh:
    df = get_market_data()
    sum_bids = df["Bid"].sum()
    sum_asks = df["Ask"].sum()

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Sum of Best Bids", f"{sum_bids:.3f}")
    with col2:
        st.metric("Sum of Best Asks", f"{sum_asks:.3f}")

    if sum_bids < THRESHOLD_LOW:
        st.warning(f"Market Undervalued (<{THRESHOLD_LOW}) → possible long arb")
    elif sum_asks > THRESHOLD_HIGH:
        st.error(f"Market Overvalued (>{THRESHOLD_HIGH}) → possible short arb")
    else:
        st.success("Market within normal bounds.")

    st.dataframe(df.round(3), use_container_width=True)

    st.caption("Data pulled from Polymarket’s public CLOB API.")
else:
    st.info("Click 'Refresh now' to fetch data.")

