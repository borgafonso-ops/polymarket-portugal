import streamlit as st
import requests
import pandas as pd

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
def get_orderbooks():
    """Fetch orderbooks for all submarkets in the Portugal Presidential Election."""
    url = f"https://clob.polymarket.com/markets?event_id={EVENT_ID}"
    resp = requests.get(url)
    resp.raise_for_status()
    data = resp.json()

    # Handle possible schema variations
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

    market_dict = {}
    for m in markets:
        question = m.get("question") or m.get("title") or m.get("slug", "Unknown")
        market_dict[question] = m
    return market_dict


def top_price_with_volume(orders, target_volume=DEPTH):
    """Compute a volume-weighted average price up to the target volume."""
    filled = 0
    weighted_price = 0
    for o in orders:
        v = min(target_volume - filled, o["size"])
        weighted_price += o["price"] * v
        filled += v
        if filled >= target_volume:
            break
    return weighted_price / filled if filled else None


def get_best_prices(market):
    """Extract best bid/ask using top 100-volume depth."""
    orderbook = market.get("orderbook")
    if not orderbook:
        # If no orderbook included, fetch it separately
        market_id = market.get("id") or market.get("market_id")
        if not market_id:
            return None, None
        ob_resp = requests.get(f"https://clob.polymarket.com/orderbook?market={market_id}")
        if ob_resp.status_code != 200:
            return None, None
        orderbook = ob_resp.json()

    bids = orderbook.get("bids", [])
    asks = orderbook.get("asks", [])
    best_bid = top_price_with_volume(bids)
    best_ask = top_price_with_volume(asks)
    return best_bid, best_ask


def get_market_data():
    """Return DataFrame of candidate bid/ask data."""
    markets = get_orderbooks()
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

auto_refresh = st.checkbox("Auto-refresh every 30 seconds", value=True)

try:
    df = get_market_data()

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

if auto_refresh:
    st.experimental_rerun()
