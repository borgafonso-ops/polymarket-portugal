import streamlit as st
import requests
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Polymarket Portugal Monitor", layout="wide")

CANDIDATES = {
    "Henrique Gouveia e Melo": "henrique",
    "Luís Marques Mendes": "marques mendes",
    "António José Seguro": "seguro",
    "André Ventura": "ventura"
}

def fetch_all_markets():
    """Fetch all active markets from Polymarket"""
    try:
        url = "https://clob.polymarket.com/markets?active=true&limit=100"
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        
        result = resp.json()
        if isinstance(result, dict) and "data" in result:
            return result["data"]
        elif isinstance(result, list):
            return result
        return []
    except Exception as e:
        st.error(f"Failed to fetch markets: {e}")
        return []

def find_candidate_market(keyword, all_markets):
    """Find market ID for a candidate"""
    for market in all_markets:
        if isinstance(market, dict):
            question = market.get("question", "").lower()
            if keyword.lower() in question and "portugal" in question:
                return market.get("id")
    return None

def get_bid_ask(market_id):
    """Get bid/ask from orderbook for a market"""
    try:
        url = f"https://clob.polymarket.com/orderbook/{market_id}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        
        ob = resp.json()
        
        bid = 0.0
        ask = 0.0
        
        if isinstance(ob, dict):
            if "bids" in ob and ob["bids"]:
                bid = float(ob["bids"][0].get("price", 0))
            if "asks" in ob and ob["asks"]:
                ask = float(ob["asks"][0].get("price", 0))
        
        return bid, ask
    except:
        return 0.0, 0.0

def fetch_data():
    """Fetch all candidate data"""
    data = []
    status = st.empty()
    progress = st.progress(0)
    
    # Fetch all markets once
    status.text("Loading all markets...")
    all_markets = fetch_all_markets()
    
    if not all_markets:
        st.error("Could not fetch markets from API")
        return []
    
    st.write(f"Found {len(all_markets)} total markets")
    
    for i, (name, keyword) in enumerate(CANDIDATES.items()):
        status.text(f"Searching for {name}...")
        
        market_id = find_candidate_market(keyword, all_markets)
        
        if market_id:
            bid, ask = get_bid_ask(market_id)
            st.write(f"✓ {name}: Found market {market_id[:12]}...")
        else:
            bid, ask = 0.0, 0.0
            st.write(f"✗ {name}: Market not found (searched for '{keyword}')")
        
        data.append({
            'name': name,
            'bid': bid,
            'ask': ask
        })
        
        progress.progress((i + 1) / len(CANDIDATES))
    
    status.empty()
    return data

# MAIN
st.title("🇵🇹 Polymarket Portugal - Bid/Offer Monitor")
st.caption(f"Updated: {datetime.now().strftime('%H:%M:%S')}")

with st.spinner("Fetching LIVE data..."):
    data = fetch_data()

with st.expander("Debug Info"):
    if data:
        total_bid = sum(d['bid'] for d in data)
        total_ask = sum(d['ask'] for d in data)
        for d in data:
            st.write(f"**{d['name']}**: Bid={d['bid']:.4f} ({d['bid']*100:.2f}%), Ask={d['ask']:.4f} ({d['ask']*100:.2f}%)")
        st.write(f"**Totals**: Bid={total_bid:.4f} ({total_bid*100:.2f}%), Ask={total_ask:.4f} ({total_ask*100:.2f}%)")

if not data or all(d['bid'] == 0 and d['ask'] == 0 for d in data):
    st.error("Could not fetch bid/ask prices")
    st.stop()

data.sort(key=lambda x: x['bid'], reverse=True)

# METRICS
cols = st.columns(4)
total_bid = 0
total_ask = 0

for i, d in enumerate(data):
    with cols[i]:
        st.markdown(f"**{d['name'].split()[-1]}**")
        bid_pct = d['bid'] * 100
        ask_pct = d['ask'] * 100
        
        st.metric("Bid %", f"{bid_pct:.2f}%")
        st.metric("Ask %", f"{ask_pct:.2f}%")
        
        total_bid += d['bid']
        total_ask += d['ask']

# TOTALS
st.divider()
col1, col2 = st.columns(2)
with col1:
    st.metric("Total Bid", f"{total_bid*100:.2f}%", f"{total_bid*100-100:+.2f}%")
with col2:
    st.metric("Total Ask", f"{total_ask*100:.2f}%", f"{total_ask*100-100:+.2f}%")

# TABLE
table_data = []
for d in data:
    spread = (d['bid'] - d['ask']) * 100
    table_data.append({
        'Candidate': d['name'],
        'Bid %': f"{d['bid']*100:.2f}",
        'Ask %': f"{d['ask']*100:.2f}",
        'Spread (¢)': f"{spread:.1f}"
    })
st.dataframe(table_data, use_container_width=True)

if st.button("🔄 REFRESH"):
    st.rerun()
