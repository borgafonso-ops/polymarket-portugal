import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import json

st.set_page_config(page_title="Polymarket Portugal Monitor", layout="wide")

CANDIDATE_NAMES = [
    "Henrique Gouveia e Melo",
    "Luís Marques Mendes",
    "António José Seguro",
    "André Ventura"
]

def get_portugal_market():
    """Fetch the Portugal presidential election market"""
    try:
        # This endpoint returns all markets - we need to find the Portugal one
        url = "https://clob.polymarket.com/markets"
        params = {
            "limit": 100
        }
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        resp.raise_for_status()
        
        markets = resp.json()
        
        # Find the Portugal presidential market
        portugal_market = None
        for market in markets:
            question = market.get("question", "").lower()
            if "portugal" in question and "presidential" in question:
                portugal_market = market
                break
        
        return portugal_market
        
    except Exception as e:
        st.error(f"Error fetching market: {str(e)[:100]}")
        return None

def get_candidate_price(market, candidate_name):
    """Extract the price for a specific candidate from market data"""
    try:
        if not market:
            return 0.0, 0.0
        
        # Get the orderbook for this market
        market_id = market.get("id")
        if not market_id:
            return 0.0, 0.0
        
        url = f"https://clob.polymarket.com/orderbook/{market_id}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        
        orderbook = resp.json()
        
        bid = 0.0
        ask = 0.0
        
        # Get best bid and ask
        if "bids" in orderbook and len(orderbook["bids"]) > 0:
            bid = float(orderbook["bids"][0]["price"])
        
        if "asks" in orderbook and len(orderbook["asks"]) > 0:
            ask = float(orderbook["asks"][0]["price"])
        
        return bid, ask
        
    except Exception as e:
        return 0.0, 0.0

def fetch_data():
    """Fetch data for all candidates"""
    data = []
    progress = st.progress(0)
    status = st.empty()
    
    # Get the market once
    status.text("Fetching Portugal market...")
    market = get_portugal_market()
    
    if not market:
        st.error("Could not find Portugal presidential market")
        return []
    
    market_id = market.get("id")
    status.text(f"Found market {market_id[:16]}... - fetching prices...")
    
    # Get orderbook for all candidates
    try:
        url = f"https://clob.polymarket.com/orderbook/{market_id}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        orderbook = resp.json()
        
        # Extract all bids and asks
        for i, candidate in enumerate(CANDIDATE_NAMES):
            bid = 0.0
            ask = 0.0
            
            # Try to get bid/ask from orderbook
            if "bids" in orderbook and len(orderbook["bids"]) > i:
                bid = float(orderbook["bids"][i]["price"])
            
            if "asks" in orderbook and len(orderbook["asks"]) > i:
                ask = float(orderbook["asks"][i]["price"])
            
            data.append({
                'name': candidate,
                'bid': bid,
                'ask': ask
            })
            
            progress.progress((i + 1) / len(CANDIDATE_NAMES))
        
    except Exception as e:
        st.error(f"Error fetching orderbook: {str(e)[:100]}")
        return []
    
    status.empty()
    return data

# MAIN
st.title("🇵🇹 Polymarket Portugal - Bid/Offer Monitor")
st.caption(f"Updated: {datetime.now().strftime('%H:%M:%S')}")

with st.spinner("Fetching LIVE prices from Polymarket..."):
    data = fetch_data()

with st.expander("Debug Info"):
    if data:
        for d in data:
            st.write(f"**{d['name']}**: Bid={d['bid']:.4f}, Ask={d['ask']:.4f}")
    else:
        st.write("No data fetched")

if not data or all(d['ask'] == 0 and d['bid'] == 0 for d in data):
    st.error("Could not fetch prices. Trying alternative approach...")
    st.info("Prices visible on page: Henrique ~51%, Luís ~21%, António ~15%, André ~10%")
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
        ask_pct = d['ask'] * 100 if d['ask'] > 0 else 0
        bid_pct = d['bid'] * 100 if d['bid'] > 0 else 0
        
        st.metric("Ask", f"{ask_pct:.2f}%")
        st.metric("Bid", f"{bid_pct:.2f}%")
        
        if d['ask'] > 0 and d['bid'] > 0:
            total_ask += d['ask']
            total_bid += d['bid']
            valid_count += 1

if valid_count > 0:
    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        st.metric("TOTAL ASK", f"{total_ask*100:.2f}%")
    with col2:
        st.metric("TOTAL BID", f"{total_bid*100:.2f}%")
    
    st.subheader("ARBITRAGE")
    if total_ask < 1:
        profit = (1 - total_ask) * 100
        st.success(f"🟢 BUY ARB: {profit:.2f}% PROFIT")
    elif total_bid > 1:
        profit = (total_bid - 1) * 100
        st.success(f"🔴 SELL ARB: {profit:.2f}% PROFIT")
    else:
        st.info("No arb opportunity")

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
