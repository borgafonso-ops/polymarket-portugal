import streamlit as st
import requests
import time
import json
import pandas as pd
from datetime import datetime

# --- Configuration ---
st.set_page_config(page_title="Polymarket Portugal Monitor", layout="wide")

# --- API Endpoints ---
GAMMA_API_EVENTS_URL = "https://gamma-api.polymarket.com/events"
GAMMA_API_MARKET_URL = "https://gamma-api.polymarket.com/markets/"
CLOB_API_ORDERBOOK_URL = "https://clob.polymarket.com/orderbook"
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
            time.sleep(2)  # Rate limit buffer
            resp = requests.get(url, timeout=15, headers=headers)  # Longer timeout
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            data = resp.json()
            if not data:  # Explicit empty check
                st.sidebar.warning(f"Empty response from {url}")
                return None
            return data
        except requests.exceptions.RequestException as e:
            st.sidebar.warning(f"Attempt {attempt+1} failed for {url}: {e}")
            if attempt < attempts - 1:
                time.sleep(2 ** attempt)
            else:
                return None
    return None

def extract_candidate_name(question):
    """Extract candidate name from question."""
    if not question or not isinstance(question, str):
        return None
    question = question.strip()
    start_phrase = "Will "
    end_phrase = " win the Portugal Presidential Election?"
    if question.startswith(start_phrase) and question.endswith(end_phrase):
        return question[len(start_phrase):-len(end_phrase)].strip()
    return None

# Mock data fallback (current as of Oct 2025; update as needed)
MOCK_DATA = [
    {'name': 'Henrique Gouveia e Melo', 'midpoint': 0.51, 'volume': 34000, 'source_msg': ' (Mock Fallback)'},
    {'name': 'Luís Marques Mendes', 'midpoint': 0.21, 'volume': 28000, 'source_msg': ' (Mock Fallback)'},
    {'name': 'António José Seguro', 'midpoint': 0.15, 'volume': 28000, 'source_msg': ' (Mock Fallback)'},
    {'name': 'André Ventura', 'midpoint': 0.11, 'volume': 46000, 'source_msg': ' (Mock Fallback)'}
]

def fetch_candidate_data(debug=False, use_mock=False):
    """Fetch data, with mock fallback."""
    if use_mock:
        st.sidebar.success("Using mock data (API offline)")
        return MOCK_DATA, None

    try:
        event_url = f"{GAMMA_API_EVENTS_URL}?slug=portugal-presidential-election"
        st.sidebar.info(f"Fetching event: {event_url}")
        event_data = robust_fetch(event_url)
        if not isinstance(event_data, dict) or not event_data.get('markets'):
            st.sidebar.error("No event data—falling back to mock")
            return MOCK_DATA, "API Error: Using Mock"

        candidates_data = []
        markets = event_data['markets'][:20]  # Limit to first 20 for speed
        for market in markets:
            market_id = market.get('id')
            if not market_id:
                continue
            market_data = robust_fetch(f"{GAMMA_API_MARKET_URL}{market_id}")
            if not market_data:
                continue

            question = market_data.get('question', '')
            candidate_name = extract_candidate_name(question)
            if candidate_name not in TARGET_CANDIDATES:
                continue

            last_price = float(market_data.get('lastPrice', 0))
            if last_price == 0:
                continue  # Skip zero-price markets

            volume = market_data.get('volume', 0)
            candidates_data.append({
                'name': candidate_name,
                'buy_price': last_price,  # Symmetric for simplicity
                'sell_price': last_price,
                'midpoint': last_price,
                'volume': volume,
                'source_msg': ' (Live Gamma)'
            })
            if len(candidates_data) == 4:
                break

        if len(candidates_data) < 4:
            st.sidebar.warning(f"Only found {len(candidates_data)}/4 candidates—partial mock")
            # Pad with mock for missing
            found_names = {c['name'] for c in candidates_data}
            for mock in MOCK_DATA:
                if mock['name'] not in found_names:
                    candidates_data.append(mock)
                    if len(candidates_data) == 4:
                        break

        return candidates_data, None

    except Exception as e:
        st.sidebar.error(f"Fetch error: {e}")
        return MOCK_DATA, "Exception: Using Mock"

# --- Main Dashboard ---
st.title("🇵🇹 Polymarket Portugal Election Monitor")
st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# Sidebar Debug
st.sidebar.header("Debug Controls")
debug = st.sidebar.checkbox("Debug Mode", value=False)
use_mock = st.sidebar.checkbox("Force Mock Data (If API Fails)", value=False)
use_clob = st.sidebar.checkbox("Attempt CLOB (Slow)", value=False)  # Disabled by default now

# Auto-refresh
auto_refresh = st.sidebar.checkbox("Auto-refresh every 30s", value=True)
if auto_refresh:
    time.sleep(30)
    st.rerun()

# Fetch
with st.spinner("Loading..."):
    candidates_data, error = fetch_candidate_data(debug=debug, use_mock=use_mock)

if error:
    st.warning(error)

if not candidates_data:
    st.error("No data loaded—check debug sidebar.")
    st.stop()

# Sort & Display
candidates_data.sort(key=lambda x: x['midpoint'] or 0, reverse=True)
cols = st.columns(4)
total_buy = total_sell = 0
for idx, c in enumerate(candidates_data):
    with cols[idx]:
        st.markdown(f"**{c['name'].split()[-1]}**")
        st.caption(f"{c['name']} | Vol: ${c['volume']:,.0f}{c['source_msg']}")
        price = c['midpoint'] * 100
        st.metric("Price", f"{price:.1f}%")
        total_buy += c['buy_price']
        total_sell += c['sell_price']

# Basket
st.divider()
col1, col2 = st.columns(2)
with col1:
    st.metric("Total Buy Sum", f"{total_buy * 100:.1f}%", delta=f"{(total_buy * 100 - 100):+.1f}%")
with col2:
    st.metric("Total Sell Sum", f"{total_sell * 100:.1f}%", delta=f"{(total_sell * 100 - 100):+.1f}%")

# Arb Check
if total_buy * 100 < 100:
    st.success(f"Buy Arb: {100 - total_buy * 100:.1f}% profit")
elif total_sell * 100 > 100:
    st.success(f"Sell Arb: {total_sell * 100 - 100:.1f}% profit")
else:
    st.info("Balanced (~100%)")

# Chart
st.subheader("Prices")
chart_df = pd.DataFrame({
    'Candidate': [c['name'].split()[-1] for c in candidates_data],
    'Price (%)': [c['midpoint'] * 100 for c in candidates_data]
}).set_index('Candidate')
st.bar_chart(chart_df)

# Table
st.subheader("Details")
table_df = pd.DataFrame({
    'Candidate': [c['name'] + c['source_msg'] for c in candidates_data],
    'Volume': [f"${c['volume']:,.0f}" for c in candidates_data],
    'Price %': [f"{c['midpoint']*100:.1f}" for c in candidates_data]
})
st.dataframe(table_df)

# Info
with st.expander("About"):
    st.markdown("Live odds from Polymarket. Sums near 100% = fair market.")

if st.button("🔄 Refresh"):
    st.cache_data.clear()
    st.rerun()
