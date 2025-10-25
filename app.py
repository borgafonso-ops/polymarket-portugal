import streamlit as st
import requests
import pandas as pd
from datetime import datetime
from eth_account import Account
from eth_account.messages import encode_defunct
import json

st.set_page_config(page_title="Polymarket Portugal Monitor", layout="wide")

# Your credentials
PRIVATE_KEY = "0xd70383d8c5d337855f12302491c56eb86cd8f34d6cf20bfb824352d1294b8c0c"
FUNDER = "0x0B309C3fDa618c0a9555bf23eFfB0ba75009C0B6"
MARKET_ID = "0x2b1e18ef56cb7222ce2fb03d6cd9fb8fcca06d80b64d0dacbe6ce2f00ab31d00"

CANDIDATES = [
    "Henrique Gouveia e Melo",
    "Luís Marques Mendes",
    "António José Seguro",
    "André Ventura"
]

def sign_message(message):
    """Sign a message with your private key"""
    try:
        account = Account.from_key(PRIVATE_KEY)
        message_hash = encode_defunct(text=message)
        signed = account.sign_message(message_hash)
        return signed.signature.hex()
    except Exception as e:
        st.error(f"Error signing message: {e}")
        return None

def fetch_orderbook(token_id):
    """Fetch orderbook for a token using authenticated API"""
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

def fetch_market_with_tokens():
    """Fetch market and token IDs"""
    try:
        url = "https://gamma-api.polymarket.com/markets"
        params = {"condition_ids": MARKET_ID}
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        resp.raise_for_status()
        
        markets = resp.json()
        return markets[0] if markets else None
        
    except Exception as e:
        st.error(f"Error fetching market: {e}")
        return None

def fetch_all_data():
    """Fetch data for all candidates"""
    data = []
    status = st.empty()
    
    status.text("Fetching Portugal presidential election market...")
    market = fetch_market_with_tokens()
    
    if not market:
        st.error("Could not fetch market")
        return []
    
    st.write(f"✓ Market: {market.get('question', 'N/A')[:80]}...")
    
    # Get outcomes and token info
    outcomes = market.get("outcomes", [])
    if isinstance(outcomes, str):
        try:
            outcomes = json.loads(outcomes)
        except:
            outcomes = []
    
    # Get CLOB token IDs
    clob_token_ids = market.get("clobTokenIds", "")
    if isinstance(clob_token_ids, str) and clob_token_ids:
        try:
            token_ids = json.loads(clob_token_ids)
        except:
            token_ids = clob_token_ids.split(",") if "," in clob_token_ids else [clob_token_ids]
    else:
        token_ids = []
    
    st.write(f"Found {len(outcomes)} outcomes, {len(token_ids)} token IDs")
    
    # Fetch orderbook for each token
    with st.spinner("Fetching live orderbooks..."):
        for i, outcome in enumerate(outcomes):
            if isinstance(outcome, dict):
                outcome_name = outcome.get("name", str(outcome))
            else:
                outcome_name = str(outcome)
            
            # Find matching candidate
            matched_candidate = None
            for candidate in CANDIDATES:
                if candidate.lower() in outcome_name.lower() or outcome_name.lower() in candidate.lower():
                    matched_candidate = candidate
                    break
            
            if matched_candidate and i < len(token_ids):
                token_id = token_ids[i]
                status.text(f"Fetching orderbook for {matched_candidate}...")
                
                bid, ask = fetch_orderbook(token_id)
                
                data.append({
                    'name': matched_candidate,
                    'bid': bid,
                    'ask': ask,
                    'token_id': token_id
                })
    
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
            st.write(f"  Token ID: {d['token_id'][:16]}...")
        
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
