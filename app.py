import streamlit as st
import requests
import pandas as pd

st.set_page_config(
    page_title="🇵🇹 Polymarket – Portugal Presidential Election Tracker",
    layout="wide"
)

# ---- CONFIG ----
EVENT_SLUG = "portugal-presidential-election"
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
@st.cache_data(ttl=300)
def get_event_id(slug: str):
    """Try to fetch the event_id from all known Polymarket endpoints."""
    urls = [
        "https://clob.polymarket.com/markets",
        "https://clob.polymarket.com/events",
    ]
    for url in urls:
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code != 200:
                continue
            data = resp.json()
            # data may be list or dict
            markets = data.get("markets") if isinstance(data, dict) else data
            if not isinstance(markets, list):
                continue
            for m in markets:
                if slug in str(m.get("slug", "")):
                    return m.get("event_id")
        except Exception:
            continue
    raise ValueError(f"Could not find event_id for slug '{slug}'")


@st.cache_data(ttl=30)
def get_orderbooks():
    """Fetch all markets for the event."""
    event_id = get_event_id(EVENT_SLUG)
    url = f"https://clob.polymarket.com/markets?event_id={event_id}"
    resp = requests.get(url)
    resp.raise_for_status()

    data = resp.json()
    # Handle schema variations
    if isinstance(data, dict):
        markets = data.get("markets") or data.get("data")
    elif isinstance(data, list):
        markets = data
    else:
        raise ValueError("Unexpected API format.")

    if not isinstance(markets, list):
        raise ValueError("Markets data missing or invalid.")

    result = {}
    for m in markets:
        q = m.get("question") or m.get("title") or m.get("slug") or str(m)
        result[q] = m
    return result


def top_price_with_volume(orders, target_volume=DEPTH):
    """Compute volume-weighted average up to a given depth."""
    if not orders:
        return None
    filled, weighted = 0, 0
    for o in orders:
        v = min(target_volume - filled, o.get("size", 0))
        weighted += o.get("price", 0) * v
        filled += v
        if filled >= target_volume:
            break
    return weighted / filled if filled else None


def get_best_prices(market):
    """Fetch orderbook if not embedded."""
    orderbook = market.get("orderbook")
    if not orderbook:
        market_id = market.get("id") or market.get("market_id")
        if not market_id:
            return None, None
        ob_url = f"https://clob.polymarket.com/orderbook?market={market_id}"
        ob_resp = requests.get(ob_url)
        if ob_resp.status_code != 200:
            return None, None
        orderbook = ob_resp.json()
    bids, asks = orderbook.get("bids", []), orderbook.get("asks", [])
    return top_price_with_volume(bids), top_price_with_volume(asks)


def get_market_data():
    """Return bid/ask for each candidate."""
    markets = get_orderbooks()
    rows = []
    for cand in CANDIDATES:
        # Try flexible matching (API questions often vary slightly)
        match = next((m for k, m in markets.items() if cand.lower() in k.lower()), None)
        if not match:
            continue
        bid, ask = get_best_prices(match)
        rows.append({"Candidate": cand, "Bid": bid, "Ask": ask})
    return pd.DataFrame(rows)


# ---- STREAMLIT UI ----
st.title("🇵🇹 Polymarket – Portugal Presidential Election Tracker")
st.caption("Tracks the sum of bids and asks for top candidates. Data from Polymarket’s public CLOB API.")

interval = st.slider("Auto-refresh interval (seconds)", 10, 120, 30)

try:
    df = get_market_data()
    if df.empty:
        st.warning("No market data found. Try again later or check event slug.")
    else:
        sum_bids = df["Bid"].sum(skipna=True)
        sum_asks = df["Ask"].sum(skipna=True)

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

st.caption("Auto-refresh enabled. Updates every few seconds automatically.")
st.experimental_rerun()
