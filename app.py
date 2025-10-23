import streamlit as st
import requests
import time
import json
import pandas as pd
from datetime import datetime

# --- Configuration ---
st.set_page_config(page_title="Polymarket Portugal Monitor", layout="wide")

# --- API Endpoints ---
GAMMA_API_EVENT_URL = "https://gamma-api.polymarket.com/events/slug/portugal-presidential-election"
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
    end_phrase = " win the 2026 Portugal presidential election?"
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
    new_row = pd.DataFrame({
        "buy_sum": [buy_sum],
        "sell_sum": [sell_sum]
    }, index=[datetime.now()])
    df = pd.concat([df, new_row])
    df.to_csv(HISTORICAL_FILE)
    return df

def fetch_candidate_data():
    """Fetch order book data for the 4 target candidates."""
    try:
        # Get event data
        event_data = robust_fetch(GAMMA_API_EVENT_URL)
        if not isinstance(event_data, dict):
            return None, "Invalid event data format"

        markets = event_data.get('markets', [])
        if not markets:
            return None, "No markets found in event"

        st.info(f"Found {len(markets)} markets, filtering for 4 target candidates...")

        candidates_data = []
        found_names = set()

        # Process each market
        for market in markets:
            if not isinstance(market, dict):
                continue

            # Use 'id' field, NOT 'conditionId'
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
                st.success(f"Found: {candidate_name}")

                # Parse outcomes and token IDs
                outcomes_raw = market_data.get('outcomes', '[]')
                try:
                    outcomes = json.loads(outcomes_raw) if isinstance(outcomes_raw, str) else outcomes_raw
                except json.JSONDecodeError:
                    outcomes = []

                if not isinstance(outcomes, list) or 'Yes' not in outcomes:
                    st.warning(f"No 'Yes' outcome for {candidate_name}")
                    continue

                yes_idx = outcomes.index('Yes')

                clob_ids_raw = market_data.get('clobTokenIds', '[]')
                try:
                    token_ids = json.loads(clob_ids_raw) if isinstance(clob_ids_raw, str) else clob_ids_raw
                except json.JSONDecodeError:
                    token_ids = []
                if not isinstance(token_ids, list) or yes_idx >= len(token_ids):
                    st.warning(f"Invalid token IDs for {candidate_name}")
                    continue

                token_yes = token_ids[yes_idx]
                token_no = token_ids[1 - yes_idx] if len(token_ids) > 1 - yes_idx else None

                # Try Yes first, fallback to No if 404 or empty
                order_book = robust_fetch(f"{CLOB_API_ORDERBOOK_URL}?token_id={token_yes}")
                if order_book:
                    asks = order_book.get('asks', [])
                    bids = order_book.get('bids', [])
                    buy_price = calculate_fill_price(asks, 100)
                    sell_price = calculate_fill_price(bids, 100)
                else:
                    st.info(f"{candidate_name}: Low liquidity on Yes, trying No...")
                    buy_price = sell_price = None

                # Fallback to No and invert
                if buy_price is None or sell_price is None:
                    if token_no:
                        order_book_no = robust_fetch(f"{CLOB_API_ORDERBOOK_URL}?token_id={token_no}")
                        if order_book_no:
                            asks_no = order_book_no.get('asks', [])
                            bids_no = order_book_no.get('bids', [])
                            buy_no = calculate_fill_price(asks_no, 100)
                            sell_no = calculate_fill_price(bids_no, 100)
                            if buy_no:
                                buy_price = 1 - buy_no
                            if sell_no:
                                sell_price = 1 - sell_no
                        else:
                            st.info(f"{candidate_name}: Low liquidity on No too")
                            buy_price = sell_price = 0
                    else:
                        buy_price = sell_price = 0

                midpoint = (buy_price + sell_price) / 2 if (buy_price or sell_price) else 0

                candidates_data.append({
                    'name': candidate_name,
                    'buy_price': buy_price,
                    'sell_price': sell_price,
                    'midpoint': midpoint
                })

                if len(candidates_data) == 4:
                    break

            except Exception as e:
                st.warning(f"Error processing market {market_id}: {e}")
                continue

        if not candidates_data:
            return None, f"Could not find any of the 4 target candidates. Found: {found_names}"

        return candidates_data, None

    except Exception as e:
        return None, f"Error in fetch_candidate_data: {e}"

# --- Main Dashboard ---
st.title("🇵🇹 Polymarket Portugal Election Monitor")
st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# Auto-refresh toggle
auto_refresh = st.checkbox("Auto-refresh every 30 seconds", value=False)
if auto_refresh:
    time.sleep(30)
    st.rerun()

# Fetch data
with st.spinner("Fetching market data for 4 candidates..."):
    candidates_data, error = fetch_candidate_data()

if error:
    st.error(error)
    st.stop()

if not candidates_data:
    st.error("Could not fetch data for any candidates")
    st.stop()

# Sort by midpoint price
candidates_data.sort(key=lambda x: x['midpoint'] or 0, reverse=True)

# --- Display Metrics ---
st.subheader("📊 Top 4 Candidates - 100 Contract Prices")
cols = st.columns(4)
total_buy = 0
total_sell = 0

for idx, candidate in enumerate(candidates_data):
    with cols[idx]:
        name = candidate['name']
        buy_price = candidate['buy_price']
        sell_price = candidate['sell_price']

        # Display name
        st.markdown(f"**{name.split()[-1]}**")
        st.caption(name)

        # Display prices
        if sell_price:
            st.metric("Sell (Bid)", f"{sell_price * 100:.2f}%")
            total_sell += sell_price
        else:
            st.metric("Sell (Bid)", "N/A")

        if buy_price:
            st.metric("Buy (Ask)", f"{buy_price * 100:.2f}%")
            total_buy += buy_price
        else:
            st.metric("Buy (Ask)", "N/A")

st.divider()

# --- Basket Totals ---
col1, col2, col3 = st.columns([1, 1, 1])
with col1:
    delta_buy = total_buy * 100 - 100
    st.metric("🔴 Total BUY (Ask) Sum",
              f"{total_buy * 100:.2f}%",
              delta=f"{delta_buy:+.2f}% vs 100%",
              delta_color="inverse" if delta_buy > 0 else "normal")
with col2:
    delta_sell = total_sell * 100 - 100
    st.metric("🟢 Total SELL (Bid) Sum",
              f"{total_sell * 100:.2f}%",
              delta=f"{delta_sell:+.2f}% vs 100%",
              delta_color="normal" if delta_sell > 0 else "inverse")
with col3:
    spread = (total_buy - total_sell) * 100 if total_buy and total_sell else 0
    st.metric("📊 Spread", f"{spread:.2f}%")

# --- Arbitrage Opportunity (Non-Directional) ---
st.subheader("📈 Arbitrage Opportunities (Non-Directional)")
if total_buy * 100 < 100:
    arb_profit = 100 - total_buy * 100
    st.success(f"Buy basket arbitrage: Buy all 4 for {total_buy * 100:.2f}% (profit {arb_profit:.2f}%)")
elif total_sell * 100 > 100:
    arb_profit = total_sell * 100 - 100
    st.success(f"Sell basket arbitrage: Sell all 4 for {total_sell * 100:.2f}% (profit {arb_profit:.2f}%)")
else:
    st.info("No current arbitrage opportunity")

# --- Visualization ---
st.subheader("📈 Price Comparison")
chart_data = pd.DataFrame({
    'Candidate': [c['name'].split()[-1] for c in candidates_data],
    'Sell (Bid)': [c['sell_price'] * 100 if c['sell_price'] else 0 for c in candidates_data],
    'Buy (Ask)': [c['buy_price'] * 100 if c['buy_price'] else 0 for c in candidates_data]
})
chart_data = chart_data.set_index('Candidate')
st.bar_chart(chart_data, height=400, color=['#90EE90', '#FF6B6B'])

# --- Historical Sums Chart ---
st.subheader("📉 Basket Sums Over Time (Non-Directional)")
historical_df = load_historical()
historical_df = append_historical(historical_df, total_buy, total_sell)

if not historical_df.empty:
    historical_df['Buy Sum (%)'] = historical_df['buy_sum'] * 100
    historical_df['Sell Sum (%)'] = historical_df['sell_sum'] * 100
    st.line_chart(historical_df[['Buy Sum (%)', 'Sell Sum (%)']], height=400)
else:
    st.info("No historical data yet. Refresh multiple times to build the chart.")

# --- Detailed Table ---
st.subheader("📋 Detailed Price Table")
table_data = []
for candidate in candidates_data:
    spread_pct = (candidate['buy_price'] - candidate['sell_price']) * 100 if (candidate['buy_price'] and candidate['sell_price']) else None
    table_data.append({
        'Candidate': candidate['name'],
        'Sell (Bid) %': f"{candidate['sell_price'] * 100:.2f}" if candidate['sell_price'] else "N/A",
        'Buy (Ask) %': f"{candidate['buy_price'] * 100:.2f}" if candidate['buy_price'] else "N/A",
        'Midpoint %': f"{candidate['midpoint'] * 100:.2f}" if candidate['midpoint'] else "N/A",
        'Spread %': f"{spread_pct:.2f}" if spread_pct is not None else "N/A"
    })
st.dataframe(table_data, use_container_width=True, hide_index=True)

# --- Additional Info ---
with st.expander("ℹ️ About This Dashboard"):
    st.markdown("""
    **What does this show?**
    - **Buy (Ask) Price**: The average price you'd pay to buy 100 'Yes' contracts
    - **Sell (Bid) Price**: The average price you'd receive selling 100 'Yes' contracts
    - **Spread**: The difference between buying and selling prices (wider = less liquidity)
    - **Midpoint**: Average of buy and sell prices
   
    **Why track the sum?**
    - In prediction markets, the sum of all probabilities should equal 100%
    - If the buy sum > 100%, there may be arbitrage opportunities (you can sell a basket for more than it costs)
    - If the sell sum < 100%, there may be arbitrage opportunities (you can buy a basket for less than its value)
   
    **Monitored Candidates**:
    - Henrique Gouveia e Melo
    - Luís Marques Mendes
    - António José Seguro
    - André Ventura
   
    **Data Source**: Polymarket Gamma & CLOB APIs
    """)

if st.button("🔄 Refresh Now"):
    st.cache_data.clear()
    st.rerun()
