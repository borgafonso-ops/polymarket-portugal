import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import time

st.set_page_config(page_title="Polymarket Portugal Monitor", layout="wide")

# Polymarket CLOB API endpoints
CLOB_API = "https://clob.polymarket.com"

CANDIDATES = {
    "Henrique Gouveia e Melo": "henrique",
    "Luís Marques Mendes": "marques mendes",
    "António José Seguro": "seguro",
    "André Ventura": "ventura"
}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

def search_all_markets():
    """Fetch all portugal presidential markets"""
    try:
        resp = requests.get(
            f"{CLOB_API}/markets",
            params={"search": "portugal", "limit": 100},
            headers=HEADERS,
            timeout=10
        )
        resp.raise_for_status()
        markets = resp.json()
        return markets if isinstance(markets, list) else []
    except Exception as e:
        st.error(f"Market search error: {e}")
        return []

def find_candidate_market(candidate_name, candidate_keyword, all_markets):
    """Find market for specific candidate from all markets"""
    for market in all_markets:
        market_question = market.get("question", "").lower()
        # Check if both candidate name and keyword are in question
        if candidate_keyword.lower() in market_question:
            return market
    return None

def get_orderbook(market_id):
    """Fetch bid/ask prices from orderbook"""
    try:
        resp = requests.get(
            f"{CLOB_API}/orderbook/{market_id}",
            headers=HEADERS,
            timeout=10
        )
        resp.raise_for_status()
        orderbook = resp.json()
        
        bid = 0.0
        ask = 0.0
        
        # Get best bid (highest bid price)
        if "bids" in orderbook and len(orderbook["bids"]) > 0:
            bid = float(orderbook["bids"][0]["price"])
        
        # Get best ask (lowest ask price)
        if "asks" in orderbook and len(orderbook["asks"]) > 0:
            ask = float(orderbook["asks"][0]["price"])
        
        return bid, ask
    except Exception as e:
        return 0.0, 0.0

def fetch_data():
    """Fetch data for all candidates"""
    candidates = []
    progress = st.progress(0)
    status_text = st.empty()
    
    # Fetch all markets once
    status_text.text("Fetching markets...")
    all_markets = search_all_markets()
    
    status_text.text(f"Found {len(all_markets)} markets, searching for candidates...")
    
    if not all_markets:
        st.error("Could not fetch markets from API")
        return candidates
    
    for i, (display_name, keyword) in enumerate(CANDIDATES.items()):
        status_text.text(f"Searching for {display_name}...")
        
        # Find market for this candidate
        market = find_candidate_market(display_name, keyword, all_markets)
        
        if market:
            market_id = market.get("id")
            market_question = market.get("question", "")
            bid, ask = get_orderbook(market_id)
            candidates.append({
                'name': display_name,
                'bid': bid,
                'ask': ask,
                'market_id': market_id,
                'question': market_question
            })
        else:
            candidates.append({
                'name': display_name,
                'bid': 0.0,
                'ask': 0.0,
                'market_id': 'NOT FOUND',
                'question': 'Market not found'
            })
        
        progress.progress((i + 1) / len(CANDIDATES))
        time.sleep(0.3)
    
    status_text.empty()
    return candidates

# MAIN
st.title("🇵🇹 Polymarket Portugal - Bid/Offer Arb Monitor")
st.caption(f"Updated: {datetime.now().strftime('%H:%M:%S')}")

with st.spinner("Fetching LIVE bid/offer from Polymarket API..."):
    data = fetch_data()

# Show debug info
with st.expander("Debug Info - Market Search Results"):
    for d in data:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.write(f"**{d['name']}**")
        with col2:
            st.write(f"Market ID: {d['market_id']}")
        with col3:
            st.write(f"Bid: {d['bid']:.4f} | Ask: {d['ask']:.4f}")
        st.caption(f"Question: {d['question'][:100]}...")

if not data:
    st.error("No data fetched. Check debug info above.")
    st.stop()

data.sort(key=lambda x: x['ask'], reverse=True)

# METRICS
cols = st.columns(4)
total_bid = 0
total_ask = 0
valid_count = 0

for i, d in enumerate(data):
    with cols[i]:
        st.markdown(f"**{d['name'].split()[-1]}**")
        ask_pct = d['ask'] * 100
        bid_pct = d['bid'] * 100
        
        st.metric("Ask (Offer)", f"{ask_pct:.2f}%")
        st.metric("Bid", f"{bid_pct:.2f}%")
        
        if d['ask'] > 0 and d['bid'] > 0:
            total_ask += d['ask']
            total_bid += d['bid']
            valid_count += 1

# BASKET
st.divider()
col1, col2 = st.columns(2)
with col1:
    st.metric("TOTAL ASK COST", f"{total_ask*100:.2f}%", f"{total_ask*100-100:+.2f}%")
with col2:
    st.metric("TOTAL BID VALUE", f"{total_bid*100:.2f}%", f"{total_bid*100-100:+.2f}%")

# ARB
st.subheader("ARBITRAGE")
if valid_count > 0:
    if total_ask > 0 and total_ask < 1:
        profit = 100 - total_ask * 100
        st.success(f"🟢 BUY ARB: {profit:.2f}% PROFIT")
    elif total_bid > 0 and total_bid > 1:
        profit = total_bid * 100 - 100
        st.success(f"🔴 SELL ARB: {profit:.2f}% PROFIT")
    else:
        st.info("No Arb Opportunity")
else:
    st.warning("No valid price data available - check markets are trading")

# CHART
st.subheader("Bid/Ask Spreads")
if valid_count >= 2:
    candidates_short = [d['name'].split()[-1] for d in data if d['ask'] > 0]
    ask_data = [d['ask']*100 for d in data if d['ask'] > 0]
    bid_data = [d['bid']*100 for d in data if d['ask'] > 0]
    
    if len(candidates_short) > 0:
        chart_dict = {}
        for i, name in enumerate(candidates_short):
            chart_dict[name] = [ask_data[i], bid_data[i]]
        
        chart_data = pd.DataFrame(chart_dict, index=['Ask', 'Bid'])
        st.bar_chart(chart_data, height=350)
    else:
        st.info("No valid data to chart")
else:
    st.info("Need at least 2 candidates with valid prices to display chart")

# TABLE
table_data = []
for d in data:
    table_data.append({
        'Candidate': d['name'],
        'Ask %': f"{d['ask']*100:.2f}",
        'Bid %': f"{d['bid']*100:.2f}",
        'Spread %': f"{(d['ask']-d['bid'])*100:.2f}",
        'Market ID': d['market_id'][:12] + "..." if len(d['market_id']) > 12 else d['market_id']
    })
st.dataframe(table_data, use_container_width=True)

if st.button("🔄 REFRESH"):
    st.rerun()
