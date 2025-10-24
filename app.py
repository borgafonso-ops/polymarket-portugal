import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import time

st.set_page_config(page_title="Polymarket Portugal Monitor", layout="wide")

# Polymarket CLOB API endpoints
CLOB_API = "https://clob.polymarket.com"

CANDIDATES = {
    "Henrique Gouveia e Melo": "portugal presidential",
    "Luís Marques Mendes": "portugal presidential",
    "António José Seguro": "portugal presidential",
    "André Ventura": "portugal presidential"
}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

def search_all_markets():
    """Fetch all portugal presidential markets"""
    try:
        resp = requests.get(
            f"{CLOB_API}/markets",
            params={"search": "portugal presidential", "limit": 100},
            headers=HEADERS,
            timeout=10
        )
        resp.raise_for_status()
        markets = resp.json()
        return markets if isinstance(markets, list) else []
    except Exception as e:
        st.error(f"Market search error: {e}")
        return []

def find_candidate_market(candidate_name, all_markets):
    """Find market for specific candidate from all markets"""
    for market in all_markets:
        market_question = market.get("question", "").lower()
        candidate_lower = candidate_name.lower()
        if candidate_lower in market_question:
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
    
    # Fetch all markets once
    all_markets = search_all_markets()
    
    if not all_markets:
        st.error("Could not fetch markets from API")
        return candidates
    
    for i, display_name in enumerate(CANDIDATES.keys()):
        # Find market for this candidate
        market = find_candidate_market(display_name, all_markets)
        
        if market:
            market_id = market.get("id")
            bid, ask = get_orderbook(market_id)
        else:
            bid, ask = 0.0, 0.0
        
        candidates.append({
            'name': display_name,
            'bid': bid,
            'ask': ask
        })
        
        progress.progress((i + 1) / len(CANDIDATES))
        time.sleep(0.3)
    
    return candidates

# MAIN
st.title("🇵🇹 Polymarket Portugal - Bid/Offer Arb Monitor")
st.caption(f"Updated: {datetime.now().strftime('%H:%M:%S')}")

with st.spinner("Fetching LIVE bid/offer from Polymarket API..."):
    data = fetch_data()

# Show debug info
with st.expander("Debug Info"):
    for d in data:
        st.write(f"{d['name']}: Bid={d['bid']}, Ask={d['ask']}")

data.sort(key=lambda x: x['ask'], reverse=True)

# METRICS
cols = st.columns(4)
total_bid = 0
total_ask = 0

for i, d in enumerate(data):
    with cols[i]:
        st.markdown(f"**{d['name'].split()[-1]}**")
        ask_pct = d['ask'] * 100
        bid_pct = d['bid'] * 100
        
        st.metric("Ask (Offer)", f"{ask_pct:.2f}%")
        st.metric("Bid", f"{bid_pct:.2f}%")
        
        total_ask += d['ask']
        total_bid += d['bid']

# BASKET
st.divider()
col1, col2 = st.columns(2)
with col1:
    st.metric("TOTAL ASK COST", f"{total_ask*100:.2f}%", f"{total_ask*100-100:+.2f}%")
with col2:
    st.metric("TOTAL BID VALUE", f"{total_bid*100:.2f}%", f"{total_bid*100-100:+.2f}%")

# ARB
st.subheader("ARBITRAGE")
if total_ask > 0 and total_ask < 1:
    profit = 100 - total_ask * 100
    st.success(f"🟢 BUY ARB: {profit:.2f}% PROFIT")
elif total_bid > 0 and total_bid > 1:
    profit = total_bid * 100 - 100
    st.success(f"🔴 SELL ARB: {profit:.2f}% PROFIT")
else:
    st.info("No Arb - Prices not available or no opportunity")

# CHART
st.subheader("Bid/Ask Spreads")
candidates_short = [d['name'].split()[-1] for d in data]
ask_data = [d['ask']*100 for d in data]
bid_data = [d['bid']*100 for d in data]

chart_data = pd.DataFrame({
    candidates_short[0]: [ask_data[0], bid_data[0]],
    candidates_short[1]: [ask_data[1], bid_data[1]],
    candidates_short[2]: [ask_data[2], bid_data[2]],
    candidates_short[3]: [ask_data[3], bid_data[3]]
}, index=['Ask', 'Bid'])

st.bar_chart(chart_data, height=350)

# TABLE
table_data = []
for d in data:
    table_data.append({
        'Candidate': d['name'],
        'Ask %': f"{d['ask']*100:.2f}",
        'Bid %': f"{d['bid']*100:.2f}",
        'Spread %': f"{(d['ask']-d['bid'])*100:.2f}"
    })
st.dataframe(table_data, use_container_width=True)

if st.button("🔄 REFRESH"):
    st.rerun()
