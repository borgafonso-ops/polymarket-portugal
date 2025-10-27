import re
import requests
import streamlit as st
import pandas as pd

st.set_page_config(
    page_title="🇵🇹 Polymarket – Portugal Presidential Election Tracker",
    layout="wide"
)

# ---- CONFIG ----
EVENT_SLUG = "portugal-presidential-election"  # derived from the URL
CANDIDATES = [
    "Henrique Gouveia e Melo (IND)",
    "Luís Marques Mendes (PSD)",
    "António José Seguro (IND)",
    "André Ventura (CH)",
]

THRESHOLD_LOW = 0.97
THRESHOLD_HIGH = 1.03
DEPTH = 100  # volume depth (shares) to consider


@st.cache_data(ttl=300)
def get_event_id(slug: str) -> str:
    """Fetch the correct event_id from the slug name."""
    resp = requests.get("https://clob.polymarket.com/markets")
    resp.raise_for_status()
    data = resp.json()

    for m in data:
        if slug in m.get("slug", ""):
            return m.get("event_id")
    raise ValueError(f"No event found for slug '{slug}'")


@st.cache_data(ttl=30)
def get_orderbooks(event_slug: str):
    """Fetch orderbooks for all submarkets in the event."""
    event_id = get_event_id(event_slug)
    url = f"https://clob.polymarket.com/markets?event_id={event_id}"
    resp = requests.get(url)
    resp.raise_for_status()
    data = resp.json()

    markets = data.get("markets") or data.get("data") or data
    if not isinstance(markets, list):
        raise ValueError("Unexpected API response format")

    return {m.get("question") or m.get("title") or "Unknown": m for m in markets}


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
    orderbook = market.get("orderbook")
    if not orderbook:
        mid = market.get("id") or market.get("market_id")
        ob_resp = requests.get(f"https://clob.polymarket.com/orderbook?market={mid}")
        if ob_resp.status_code != 200:
            return None, None
        orderbook = ob_resp.json()

    bids, asks = orderbook.get("bids", []), orderbook.get("asks", [])
    return top_price_with_volume(bids), top_price_with_volume(asks)


def get_market_data():
    markets = get_orderbooks(EVENT_SLUG)
    rows = []
    for cand in CANDIDATES:
        market = markets.get(cand)
        if not market:
            continue
        bid, ask = get_best_prices(market)
        rows.append({"Candidate": cand, "Bid": bid, "Ask": ask})
    return pd.DataFrame(rows)


# ---- STREAMLIT UI ----
st.title("🇵🇹 Polymarket – Portugal Presidential Election Tracker")
st.caption("Tracks the sum of bids and asks for top candidates. Data from Polymarket’s public CLOB API.")

try:
    df = get_market_data()

    if df.empty:
        st.warning("No market data found. Try again later or check event slug.")
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
