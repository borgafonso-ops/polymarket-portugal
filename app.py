import streamlit as st
import requests
import time
import pandas as pd
from datetime import datetime

# --- Configuration ---
st.set_page_config(page_title="Polymarket Portugal Monitor", layout="wide")

# --- API Endpoints ---
GAMMA_API_EVENTS_URL = "https://gamma-api.polymarket.com/events"
GAMMA_API_MARKET_URL = "https://gamma-api.polymarket.com/markets/"
HEADERS = {'User-Agent': 'PolymarketStreamlitMonitor/2.0'}

# Target candidates - only these 4
TARGET_CANDIDATES = {
    "Henrique Gouveia e Melo",
    "Luís Marques Mendes",
    "António José Seguro",
    "André Ventura"
}

# --- Helper Functions ---
@st.cache_data(ttl=30)
def robust_fetch(url, headers=HEADERS, attempts=3):
    """Fetches data from a URL with exponential backoff on failure."""
    for attempt in range(attempts):
        try:
            time.sleep(1)  # Light rate limit buffer
            resp = requests.get(url, timeout=15, headers=headers)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as e:
            if attempt < attempts - 1:
                time.sleep(2 ** attempt)
            else:
                st.sidebar.warning(f"Failed to fetch {url}: {e}")
                return None
    return None

def extract_candidate_name(question):
    """Extract candidate name from question (flexible for '2026' or 'the')."""
    if not question or not isinstance(question, str):
        return None
    question = question.strip()
    # Common patterns: "Will [NAME] win the 2026 Portugal presidential election?"
    # Or: "Will [NAME] win the Portugal Presidential Election?"
    import re
    match = re.search(r'Will (.*?) win', question)
    if match:
        return match.group(1).strip()
    return None

# Mock data fallback (updated to API-like values)
MOCK_DATA = [
    {'name': 'Henrique Gouveia e Melo', 'price': 0.51, 'volume': 34000, 'source_msg': ' (Fallback)'},
    {'name': 'Luís Marques Mendes', 'price': 0.21, 'volume': 28000, 'source_msg': ' (Fallback)'},
    {'name': 'António José Seguro', 'price': 0.15, 'volume': 28000, 'source_msg': ' (Fallback)'},
    {'name': 'André Ventura', 'price': 0.11, 'volume': 46000, 'source_msg': ' (Fallback)'}
]

def fetch_candidate_data(debug=False):
    """Fetch data for the 4 target candidates, handling array format."""
    try:
        # Get event data with slug filter
        event_url = f"{GAMMA_API_EVENTS_URL}?slug=portugal-presidential-election"
        if debug:
            st.sidebar.info(f"Fetching: {event_url}")
        event_data = robust_fetch(event_url)
        
        if not event_data:
            st.sidebar.error("Empty event response—using mock")
            return MOCK_DATA, "API Empty: Using Mock"
        
        if not isinstance(event_data, list) or len(event_data) == 0:
            st.sidebar.error(f"Unexpected format (not list): {type(event_data)}—using mock")
            return MOCK_DATA, "Format Error: Using Mock"
        
        # Fix: Extract the first (and only) event dict from the array
        event_dict = event_data[0]
        if not isinstance(event_dict, dict):
            st.sidebar.error("Event item not dict—using mock")
            return MOCK_DATA, "Parse Error: Using Mock"
        
        markets = event_dict.get('markets', [])
        if not markets:
            st.sidebar.error("No 'markets' key—using mock")
            return MOCK_DATA, "No Markets: Using Mock"
        
        if debug:
            st.sidebar.success(f"Loaded {len(markets)} markets from event")

        candidates_data = []
        found_names = set()

        # Process markets (limit to 50 for speed)
        for market in markets[:50]:
            if not isinstance(market, dict):
                continue

            market_id = market.get('id')
            if not market_id:
                continue

            try:
                # Fetch full market data
                market_url = f"{GAMMA_API_MARKET_URL}{market_id}"
                market_data = robust_fetch(market_url)
                if not isinstance(market_data, dict):
                    continue

                # Extract candidate name
                question = market_data.get('question', '')
                candidate_name = extract_candidate_name(question)

                # Only process if it's one of our target candidates
                if not candidate_name or candidate_name not in TARGET_CANDIDATES:
                    continue

                # Avoid duplicates
                if candidate_name in found_names:
                    continue

                found_names.add(candidate_name)
                if debug:
                    st.sidebar.success(f"Found: {candidate_name} (ID: {market_id})")

                # Get volume
                volume = market_data.get('volume', 0)

                # Primary: Use lastTradePrice as proxy (more reliable)
                last_price = float(market_data.get('lastTradePrice', 0) or market_data.get('lastPrice', 0))
                buy_price = sell_price = last_price if last_price > 0 else 0
                source_msg = " (Live Gamma)" if last_price > 0 else " (No Trades)"

                midpoint = (buy_price + sell_price) / 2

                candidates_data.append({
                    'name': candidate_name,
                    'buy_price': buy_price,
                    'sell_price': sell_price,
                    'midpoint': midpoint,
                    'volume': volume,
                    'source_msg': source_msg
                })

                if len(candidates_data) == 4:
                    break

            except Exception as e:
                if debug:
                    st.sidebar.warning(f"Error for market {market_id}: {e}")
                continue

        if not candidates_data:
            st.sidebar.warning(f"No targets found. Available candidates in markets: {found_names}")
            return MOCK_DATA, "No Targets: Using Mock"

        # Pad with mocks if <4 (rare, but safe)
        while len(candidates_data) < 4:
            for mock in MOCK_DATA:
                if mock['name'] not in {c['name'] for c in candidates_data}:
                    candidates_data.append(mock)
                    break

        return candidates_data, None

    except Exception as e:
        st.sidebar.error(f"Overall fetch error: {e}")
        return MOCK_DATA, "Exception: Using Mock"

# --- Main Dashboard ---
st.title("🇵🇹 Polymarket Portugal Election Monitor")
st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
st.markdown("[View Event on Polymarket](https://polymarket.com/event/portugal-presidential-election)")

# Options (in sidebar for clean main view)
st.sidebar.header("Controls")
debug = st.sidebar.checkbox("Debug Mode (Logs)", value=False)
auto_refresh = st.sidebar.checkbox("Auto-refresh every 30s", value=False)
if auto_refresh:
    time.sleep(30)
    st.rerun()

# Fetch data
with st.spinner("Fetching live data..."):
    candidates_data, error = fetch_candidate_data(debug=debug)

if error:
    st.warning(error)

if not candidates_data:
    st.error("No data available—check debug sidebar.")
    st.stop()

# Sort by midpoint price
candidates_data.sort(key=lambda x: x['midpoint'] or 0, reverse=True)

# --- Display Metrics ---
st.subheader("📊 Top 4 Candidates - Implied Prices")
cols = st.columns(4)
total_buy = 0
total_sell = 0

for idx, candidate in enumerate(candidates_data):
    with cols[idx]:
        name = candidate['name']
        buy_price = candidate['buy_price']
        sell_price = candidate['sell_price']
        volume = candidate['volume']
        source_msg = candidate['source_msg']

        # Display name + volume
        st.markdown(f"**{name.split()[-1]}**")
        st.caption(f"{name} | Vol: ${volume:,.0f}{source_msg}")

        # Display prices
        price_pct = (buy_price * 100) if buy_price else 0
        st.metric("Price", f"{price_pct:.1f}%")
        total_buy += buy_price
        total_sell += sell_price

st.divider()

# --- Basket Totals ---
col1, col2, col3 = st.columns([1, 1, 1])
with col1:
    delta_buy = total_buy * 100 - 100
    st.metric("🔴 Total BUY Sum",
              f"{total_buy * 100:.1f}%",
              delta=f"{delta_buy:+.1f}% vs 100%",
              delta_color="inverse" if delta_buy > 0 else "normal")
with col2:
    delta_sell = total_sell * 100 - 100
    st.metric("🟢 Total SELL Sum",
              f"{total_sell * 100:.1f}%",
              delta=f"{delta_sell:+.1f}% vs 100%",
              delta_color="normal" if delta_sell > 0 else "inverse")
with col3:
    spread = (total_buy - total_sell) * 100 if total_buy and total_sell else 0
    st.metric("📊 Avg Spread", f"{spread:.1f}%")

# --- Arbitrage Opportunity ---
st.subheader("📈 Arbitrage Opportunities")
if total_buy * 100 < 100:
    arb_profit = 100 - total_buy * 100
    st.success(f"🟢 Buy basket: {total_buy * 100:.1f}% (profit {arb_profit:.1f}%)")
elif total_sell * 100 > 100:
    arb_profit = total_sell * 100 - 100
    st.success(f"🔴 Sell basket: {total_sell * 100:.1f}% (profit {arb_profit:.1f}%)")
else:
    st.info("⚖️ No arb (balanced ~100%)")

# --- Visualization ---
st.subheader("📈 Price Comparison")
chart_data = pd.DataFrame({
    'Candidate': [c['name'].split()[-1] for c in candidates_data],
    'Price (%)': [c['midpoint'] * 100 for c in candidates_data]
})
chart_data = chart_data.set_index('Candidate')
st.bar_chart(chart_data, height=400, color=['#4CAF50'])

# --- Detailed Table ---
st.subheader("📋 Detailed Table")
table_data = []
for candidate in candidates_data:
    spread_pct = (candidate['buy_price'] - candidate['sell_price']) * 100 if (candidate['buy_price'] and candidate['sell_price']) else 0
    table_data.append({
        'Candidate': candidate['name'] + candidate['source_msg'],
        'Volume ($)': f"${candidate['volume']:,.0f}",
        'Price %': f"{candidate['midpoint'] * 100:.1f}",
        'Spread %': f"{spread_pct:.1f}"
    })
st.dataframe(table_data, use_container_width=True, hide_index=True)

# --- Additional Info ---
with st.expander("ℹ️ About This Dashboard"):
    st.markdown("""
    **Prices**: From Gamma API `lastTradePrice` (live odds for Yes shares). Falls back to mock if API issues.
    **Basket Sum**: Should ~100% for fair market; deviations = potential arb.
    **Note**: Many markets inactive/low vol—sums may skew low until trades pick up.
    **Data Source**: Polymarket Gamma API.
    """)

if st.button("🔄 Refresh Now"):
    st.cache_data.clear()
    st.rerun()
