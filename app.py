import streamlit as st
import requests
import pandas as pd
import time

st.set_page_config(
    page_title="🇵🇹 Polymarket – Portugal Presidential Election Tracker",
    layout="wide"
)

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
DEPTH = 100  # volume depth (shares) to consider

# ---- FUNCTIONS ----
@st.cache_data(ttl=30)
def get_markets():
    """Fetch all markets (candidates) for the Portugal Presidential Election."""
    url = f"https://clob.polymarket.com/markets?event_id={EVENT_ID}"
    resp = requests.get(url)
    resp.raise_for_status()
    data = resp.json()

    # handle possible formats
    if isinstance(data, dict):
        if "markets" in data:
            markets = data["markets"]
        elif "data" in data:
            markets = data["data"]
        else:
            raise KeyError(f"Unexpected API structure: {list(data.keys())}")
    elif isinstance(data, list):
        markets = data
    else:
        raise TypeError("Unexpected response format from Polymarket API")

    # build mapping
    market_dict = {}
    for m in markets:
        question = m.get("question") or m.get("title") or "Unknown"
        market_dict[question] = m
    return market_dict


def fetch_orderbook(market_id):
    """Get orderbook for a single market ID."""
    ob_url = f"https://clob.polymarket.com/orderbook?market={market_id}"
    r = requests.get(ob_url)
    if r.status_code != 200:
        return None, None
    ob = r.json()
    bids = ob.get("bids", [])
    asks = ob.get("asks", [])
    return bids, asks


def top_price_with_volume(orders, target_volume=DEPTH):
    """Volume-weighted average up to target volume."""
    filled = 0
    weighted_price = 0
    for o in orders:
        v = min(target_volume - filled, o["size"])
        weighted_price += o["price"] * v
        filled += v
        if filled >= target_volume:
            break
    return weighted_price / filled if filled else None


def get_market_data():
    """Return DataFrame with bid/ask data for top candidates."""
    markets = get_markets()
    rows = []
    for cand in CANDIDATES:
        m = markets.get(cand)
        if not m:
            continue
        market_id = m.get("id") or m.get("market_id")
        if not market_id:
            continue
        bids, asks = fetch_orderbook(market_id)
        best_bid = top_price_with_volume(bids) if bids else None
        best_ask = top_price_with_volume(asks) if asks else None
        rows.append({"Candidate": cand, "Bid": best_bid, "Ask": best_ask})
    return pd.DataFrame(rows)


# ---- STREAMLIT UI ----
st.title("🇵🇹 Polymarket – Portugal Presidential Election Tracker")
st.caption("Tracks the sum of bids and asks for top candidates. Data from Polymarket’s public CLOB API.")

refresh_rate = st.slider("Auto-refresh interval (seconds)", 10, 120, 30)
placeholder = st.empty()

while True:
    try:
        df = get_market_data()
        with placeholder.container():
            if df.empty:
                st.warning("No market data found. Try again later or check event ID.")
            else:
                sum_bids = df["Bid"].sum()
                sum_asks = df["Ask"].sum()

                col1, col2 = st.columns(2)
                col1.metric("Sum of Best Bids", f"{sum_bids:.3f}")
                col2.metric("Sum of Best Asks", f"{sum_asks:.3f}")

                if sum_bids < THRESHOLD_LOW:
                    st.warning(f"Market Undervalued (< {THRESHOLD_LOW}) → possible long arb opportunity")
                elif sum_asks > THRESHOLD_HIGH:
                    st.error(f"Market Overvalued (> {THRESHOLD_HIGH}) → possible short arb opportunity")
                else:
                    st.success("Market within normal bounds.")

                st.dataframe(df.round(3), use_container_width=True)

    except Exception as e:
        st.error(f"⚠️ Error fetching market data: {e}")

    time.sleep(refresh_rate)
    st.experimental_rerun()
