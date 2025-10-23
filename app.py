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
            resp = requests.get(url, timeout=10, headers=headers)
            if resp.status_code == 404:
                return None  # No liquidity = empty book
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as e:
            if attempt < attempts - 1:
                time.sleep(2 ** attempt)
            else:
                st.warning(f"Failed to fetch {url}: {e}")
                return None
    return None

def calculate_fill_price(orders, size_needed):
    """Calculate average fill price for a given size by walking the order book."""
    if not orders:
        return None
    try:
        order_list = [(float(o['price']), float(o['size'])) for o in orders if 'price' in o and 'size' in o]
    except (ValueError, TypeError, KeyError):
        return None
    if not order_list:
        return None
    total_cost = 0.0
    size_filled = 0.0
    for price, size in order_list:
        size_to_fill = min(size, size_needed - size_filled)
        total_cost += size_to_fill * price
        size_filled += size_to_fill
        if size_filled >= size_needed:
            break
    if size_filled < size_needed:
        return None
    return total_cost / size_filled

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

# --- Historical Data ---
HISTORICAL_FILE = "historical_sums.csv"

@st.cache_data(ttl=300)
def load_historical():
    try:
        df = pd.read_csv(HISTORICAL_FILE, index_col="timestamp", parse_dates=True)
    except FileNotFoundError:
        df = pd.DataFrame(columns=["timestamp", "buy_sum", "sell_sum"])
        df.set_index("timestamp", inplace=True)
    return df

def append_historical(df, buy_sum, sell_sum):
    if buy_sum > 0 or sell_sum > 0:  # Only append non-zero data
        new_row = pd.DataFrame({
            "buy_sum": [buy_sum],
            "sell_sum": [sell_sum]
        }, index=[datetime.now()])
        df = pd.concat([df, new_row])
        df.to_csv(HISTORICAL_FILE)
    return df

def fetch_candidate_data(debug=False, use_clob=False):
    """Fetch data for the 4 target candidates, prioritizing Gamma lastPrice."""
    try:
        # Get event data with slug filter
        event_url = f"{GAMMA_API_EVENTS_URL}?slug=portugal-presidential-election"
        event_data = robust_fetch(event_url)
        if not isinstance(event_data, dict):
            return None, "Invalid event data format"

        markets = event_data.get('markets', [])
        if not markets:
            return None, "No markets found in event"

        if debug:
            st.info(f"Found {len(markets)} markets in event, scanning for targets...")

        candidates_data = []
        found_names = set()

        # Process each market
        for market in markets:
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
                    st.success(f"Found: {candidate_name} (ID: {market_id})")

                # Get volume for display
                volume = market_data.get('volume', 0)

                # Primary: Use lastPrice as proxy for both buy/sell (matches site odds)
                last_price = float(market_data.get('lastPrice', 0))
                buy_price = sell_price = last_price
                source_msg = " (Gamma Last Price)"
                clob_success = False

                # Optional: Override with CLOB if enabled
                if use_clob:
                    # Parse token IDs (assuming binary Yes/No)
                    clob_ids_raw = market_data.get('clobTokenIds', '[]')
                    try:
                        token_ids = json.loads(clob_ids_raw) if isinstance(clob_ids_raw, str) else clob_ids_raw
                    except json.JSONDecodeError:
                        token_ids = []
                    
                    if len(token_ids) >= 1:
                        token_yes = token_ids[0]  # Yes is typically index 0
                        order_book = robust_fetch(f"{CLOB_API_ORDERBOOK_URL}?token_id={token_yes}")
                        if order_book and order_book.get('asks') and order_book.get('bids'):
                            asks = order_book.get('asks', [])
                            bids = order_book.get('bids', [])
                            clob_buy = calculate_fill_price(asks, 100)
                            clob_sell = calculate_fill_price(bids, 100)
                            if clob_buy is not None and clob_sell is not None:
                                buy_price = clob_buy
                                sell_price = clob_sell
                                source_msg = " (CLOB Orderbook)"
                                clob_success = True
                                if debug:
                                    st.info(f"{candidate_name}: CLOB success - Buy: {buy_price:.3f}, Sell: {sell_price:.3f}")
                            else:
                                if debug:
                                    st.warning(f"{candidate_name}: CLOB empty or insufficient depth")
                        else:
                            if debug:
                                st.warning(f"{candidate_name}: CLOB 404 or failed fetch")
                    else:
                        if debug:
                            st.warning(f"{candidate_name}: No valid token IDs for CLOB")

                if not clob_success and last_price == 0:
                    source_msg = " (No Data Available)"

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
                    st.warning(f"Error processing market {market_id}: {e}")
                continue

        if not candidates_data:
            return None, f"Could not find any of the 4 target candidates. Found: {found_names}. Check event slug or candidate names."

        return candidates_data, None

    except Exception as e:
        return None, f"Error in fetch_candidate_data: {e}"

# --- Main Dashboard ---
st.title("🇵🇹 Polymarket Portugal Election Monitor")
st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
st.markdown("[View Event on Polymarket](https://polymarket.com/event/portugal-presidential-election?tid=1761223523692)")

# Options
col_opt1, col_opt2 = st.columns(2)
debug = col_opt1.checkbox("Debug Mode (Show API Logs)", value=False)
use_clob = col_opt2.checkbox("Use CLOB Orderbook (Experimental - May 404)", value=False)

# Auto-refresh toggle
auto_refresh = st.checkbox("Auto-refresh every 30 seconds", value=True)
if auto_refresh:
    time.sleep(30)
    st.rerun()

# Fetch data
with st.spinner("Fetching live market data..."):
    candidates_data, error = fetch_candidate_data(debug=debug, use_clob=use_clob)

if error:
    st.error(error)
    st.stop()

if not candidates_data:
    st.error("Could not fetch data for any candidates")
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
        if sell_price:
            st.metric("Sell (Bid)", f"{sell_price * 100:.1f}%")
            total_sell += sell_price
        else:
            st.metric("Sell (Bid)", "N/A")

        if buy_price:
            st.metric("Buy (Ask)", f"{buy_price * 100:.1f}%")
            total_buy += buy_price
        else:
            st.metric("Buy (Ask)", "N/A")

st.divider()

# --- Basket Totals ---
col1, col2, col3 = st.columns([1, 1, 1])
with col1:
    delta_buy = total_buy * 100 - 100
    st.metric("🔴 Total BUY (Ask) Sum",
              f"{total_buy * 100:.1f}%",
              delta=f"{delta_buy:+.1f}% vs 100%",
              delta_color="inverse" if delta_buy > 0 else "normal")
with col2:
    delta_sell = total_sell * 100 - 100
    st.metric("🟢 Total SELL (Bid) Sum",
              f"{total_sell * 100:.1f}%",
              delta=f"{delta_sell:+.1f}% vs 100%",
              delta_color="normal" if delta_sell > 0 else "inverse")
with col3:
    spread = (total_buy - total_sell) * 100 if total_buy and total_sell else 0
    st.metric("📊 Avg Spread", f"{spread:.1f}%")

# --- Arbitrage Opportunity (Non-Directional) ---
st.subheader("📈 Arbitrage Opportunities (Non-Directional)")
if total_buy * 100 < 100:
    arb_profit = 100 - total_buy * 100
    st.success(f"🟢 Buy basket arb: Buy all 4 for {total_buy * 100:.1f}% (profit {arb_profit:.1f}%)")
elif total_sell * 100 > 100:
    arb_profit = total_sell * 100 - 100
    st.success(f"🔴 Sell basket arb: Sell all 4 for {total_sell * 100:.1f}% (profit {arb_profit:.1f}%)")
else:
    st.info("⚖️ Balanced: No arb (sums ~100% as expected)")

# --- Visualization ---
st.subheader("📈 Price Comparison")
chart_data = pd.DataFrame({
    'Candidate': [c['name'].split()[-1] for c in candidates_data],
    'Price (%)': [c['midpoint'] * 100 for c in candidates_data]
})
chart_data = chart_data.set_index('Candidate')
st.bar_chart(chart_data, height=400, color=['#4CAF50'])

# --- Historical Sums Chart ---
st.subheader("📉 Basket Sums Over Time")
historical_df = load_historical()
historical_df = append_historical(historical_df, total_buy, total_sell)

if not historical_df.empty:
    historical_df['Buy Sum (%)'] = historical_df['buy_sum'] * 100
    historical_df['Sell Sum (%)'] = historical_df['sell_sum'] * 100
    st.line_chart(historical_df[['Buy Sum (%)', 'Sell Sum (%)']], height=400)
else:
    st.info("No historical data yet—refresh a few times to build it.")

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
with st.expander("ℹ️ About"):
    st.markdown("""
    - **Prices**: From Gamma API lastPrice (live odds) or CLOB if enabled. Matches Polymarket site.
    - **Why Sums ~100%?**: Implied probs across candidates; deviations = arb.
    - **Data**: Polymarket Gamma/CLOB APIs. Event ends Jan 2026.
    """)

if st.button("🔄 Refresh Now"):
    st.cache_data.clear()
    st.rerun()
