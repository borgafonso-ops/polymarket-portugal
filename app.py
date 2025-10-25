import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import json

st.set_page_config(page_title="Polymarket Portugal Monitor", layout="wide")

MARKET_ID = "0x2b1e18ef56cb7222ce2fb03d6cd9fb8fcca06d80b64d0dacbe6ce2f00ab31d00"

CANDIDATES = [
    "Henrique Gouveia e Melo",
    "Luís Marques Mendes", 
    "António José Seguro",
    "André Ventura"
]

def fetch_market_data():
    """Fetch market data from Polymarket API"""
    try:
        url = f"https://clob.polymarket.com/rewards/markets/{MARKET_ID}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        
        return resp.json()
        
    except Exception as e:
        st.error(f"Error fetching data: {e}")
        return None

def fetch_orderbook(token_id):
    """Fetch orderbook for a specific token/outcome"""
    try:
        url = f"https://clob.polymarket.com/orderbook/{token_id}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
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

# MAIN
st.title("🇵🇹 Polymarket Portugal - Bid/Offer Monitor")
st.caption(f"Updated: {datetime.now().strftime('%H:%M:%S')}")

with st.spinner("Fetching market data..."):
    market_data = fetch_market_data()

if not market_data:
    st.error("Could not fetch market data")
    st.stop()

# Display raw market data for debugging
with st.expander("Raw Market Data"):
    st.json(market_data)

# Extract token IDs and outcomes
data = []

if isinstance(market_data, dict):
    tokens = market_data.get("tokens", [])
    
    with st.spinner("Fetching orderbooks..."):
        for i, token in enumerate(tokens):
            token_id = token.get("token_id")
            outcome = token.get("outcome")
            
            if token_id and outcome and i < len(CANDIDATES):
                bid, ask = fetch_orderbook(token_id)
                data.append({
                    'name': CANDIDATES[i],
                    'outcome': outcome,
                    'token_id': token_id,
                    'bid': bid,
                    'ask': ask
                })

# Debug info
with st.expander("Debug Info"):
    if data:
        total_bid = sum(d['bid'] for d in data)
        total_ask = sum(d['ask'] for d in data)
        
        for d in data:
            st.write(f"**{d['name']}** ({d['outcome']})")
            st.write(f"  Bid: {d['bid']:.4f} ({d['bid']*100:.2f}%)")
            st.write(f"  Ask: {d['ask']:.4f} ({d['ask']*100:.2f}%)")
            st.write(f"  Spread: {(d['bid']-d['ask'])*100:.2f}¢")
        
        st.write(f"\n**Totals**")
        st.write(f"  Total Bid: {total_bid:.4f} ({total_bid*100:.2f}%)")
        st.write(f"  Total Ask: {total_ask:.4f} ({total_ask*100:.2f}%)")

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
        
        st.metric("Bid %", f"{d['bid']*100:.2f}%")
        st.metric("Ask %", f"{d['ask']*100:.2f}%")
        st.metric("Spread (¢)", f"{(d['bid']-d['ask'])*100:.1f}")
        
        total_bid += d['bid']
        total_ask += d['ask']

# TOTALS
st.divider()
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Total Bid", f"{total_bid*100:.2f}%")
with col2:
    st.metric("Total Ask", f"{total_ask*100:.2f}%")
with col3:
    if total_bid < 1:
        profit = (1 - total_bid) * 100
        st.metric("Buy Arb", f"+{profit:.2f}%", delta_color="off")
    elif total_ask > 1:
        loss = (total_ask - 1) * 100
        st.metric("Sell Arb", f"-{loss:.2f}%", delta_color="off")

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
