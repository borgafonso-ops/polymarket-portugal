import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import json

st.set_page_config(page_title="Polymarket Portugal Monitor", layout="wide")

# Your credentials
FUNDER = "0x0B309C3fDa618c0a9555bf23eFfB0ba75009C0B6"

CANDIDATES = {
    "Henrique Gouveia e Melo": "0x2b1e18ef56cb7222ce2fb03d6cd9fb8fcca06d80b64d0dacbe6ce2f00ab31d00",
    "Luís Marques Mendes": "0xed888eb64bffa457086fb5904e9b2046da9aa31c5db36e9d4a303efa7e850d76",
    "António José Seguro": "0xa062dea464f0e8fc3381176494198cf45574ec190eca77a40f49988320fa15f2",
    "André Ventura": "0xbcb33ad98c8141b10f2350ef687eddf0660484ecc15be42ecdae64339e64dce1"
}

def fetch_market_by_condition_id(condition_id):
    """Fetch market data by condition ID"""
    try:
        url = "https://gamma-api.polymarket.com/markets"
        params = {"condition_ids": condition_id}
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        resp.raise_for_status()
        
        markets = resp.json()
        return markets[0] if markets else None
        
    except Exception as e:
        return None

def fetch_orderbook(token_id):
    """Fetch orderbook for a token"""
    try:
        url = f"https://clob.polymarket.com/orderbook/{token_id}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'POLY-ADDRESS': FUNDER,
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
    except Exception as e:
        return 0.0, 0.0

def fetch_all_data():
    """Fetch data for all candidates"""
    data = []
    progress = st.progress(0)
    status = st.empty()
    
    for idx, (candidate_name, condition_id) in enumerate(CANDIDATES.items()):
        status.text(f"Fetching {candidate_name}...")
        
        # Fetch market
        market = fetch_market_by_condition_id(condition_id)
        
        if market:
            st.write(f"✓ {candidate_name}: Found market")
            
            # Get token IDs for the YES outcome
            clob_token_ids = market.get("clobTokenIds", "")
            if isinstance(clob_token_ids, str) and clob_token_ids:
                try:
                    token_ids = json.loads(clob_token_ids)
                except:
                    token_ids = clob_token_ids.split(",") if "," in clob_token_ids else [clob_token_ids]
            else:
                token_ids = []
            
            # Get the YES token (usually first one)
            if token_ids:
                yes_token_id = token_ids[0]
                bid, ask = fetch_orderbook(yes_token_id)
                
                data.append({
                    'name': candidate_name,
                    'bid': bid,
                    'ask': ask,
                    'token_id': yes_token_id
                })
            else:
                st.write(f"✗ {candidate_name}: No token IDs found")
        else:
            st.write(f"✗ {candidate_name}: Market not found")
        
        progress.progress((idx + 1) / len(CANDIDATES))
    
    status.empty()
    return data

# MAIN
st.title("🇵🇹 Polymarket Portugal - Bid/Offer Monitor")
st.caption(f"Updated: {datetime.now().strftime('%H:%M:%S')}")

with st.spinner("Fetching LIVE data..."):
    data = fetch_all_data()

with st.expander("Debug Info"):
    if data:
        total_bid = sum(d['bid'] for d in data)
        total_ask = sum(d['ask'] for d in data)
        
        for d in data:
            st.write(f"**{d['name']}**")
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
        st.metric("Spread (¢)", f"{(d['bid']-d['ask'])*100:.2f}")
        
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
        'Spread (¢)': f"{spread:.2f}"
    })
st.dataframe(table_data, use_container_width=True)

if st.button("🔄 REFRESH"):
    st.rerun()
