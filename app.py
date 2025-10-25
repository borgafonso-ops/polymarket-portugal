import streamlit as st
import requests
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Polymarket Portugal Monitor", layout="wide")

CANDIDATES = [
    "Henrique Gouveia e Melo",
    "Luís Marques Mendes",
    "António José Seguro",
    "André Ventura"
]

def fetch_portugal_markets():
    """Fetch all Portugal presidential election markets"""
    try:
        url = "https://gamma-api.polymarket.com/markets"
        params = {
            "search": "portugal presidential",
            "limit": 50
        }
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        resp.raise_for_status()
        
        return resp.json()
        
    except Exception as e:
        st.warning(f"Error fetching markets: {e}")
        return []

def fetch_all_data():
    """Fetch data for all candidates"""
    data = []
    status = st.empty()
    
    status.text("Searching for Portugal presidential election market...")
    markets = fetch_portugal_markets()
    
    if not markets:
        st.error("No markets found")
        return []
    
    # Display what we found for debugging
    st.write(f"Found {len(markets)} market(s) matching 'portugal presidential'")
    
    for market in markets:
        question = market.get("question", "").lower()
        
        st.write(f"Market: {market.get('question', 'N/A')[:80]}...")
        
        # Check if this market has candidate outcomes
        outcomes = market.get("outcomes", [])
        if isinstance(outcomes, str):
            try:
                import json
                outcomes = json.loads(outcomes)
            except:
                outcomes = []
        
        st.write(f"  Found {len(outcomes)} outcomes")
        
        # Look for candidate names in outcomes
        matched_candidates = []
        for outcome in outcomes:
            if isinstance(outcome, dict):
                outcome_name = outcome.get("name", str(outcome))
            else:
                outcome_name = str(outcome)
            
            for candidate in CANDIDATES:
                if candidate.lower() in outcome_name.lower() or outcome_name.lower() in candidate.lower():
                    matched_candidates.append({
                        'candidate': candidate,
                        'outcome': outcome_name,
                        'outcome_obj': outcome
                    })
        
        if len(matched_candidates) >= 4:
            st.write(f"  ✓ This market has all 4 candidates!")
            
            # This is our market! Extract bid/ask for each
            for match in matched_candidates:
                candidate = match['candidate']
                outcome = match['outcome_obj']
                
                # Try to get price data from outcome
                bid = 0.0
                ask = 0.0
                
                if isinstance(outcome, dict):
                    # Look for bestBid/bestAsk in outcome object
                    bid = float(outcome.get('bestBid', outcome.get('price', 0)))
                    ask = float(outcome.get('bestAsk', outcome.get('price', 0)))
                
                data.append({
                    'name': candidate,
                    'bid': bid,
                    'ask': ask
                })
            
            break
    
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
