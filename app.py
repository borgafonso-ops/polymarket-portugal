import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import json
import re

st.set_page_config(page_title="Polymarket Portugal Monitor", layout="wide")

CANDIDATES = [
    {"name": "Henrique Gouveia e Melo", "id": "0x6"},
    {"name": "Luís Marques Mendes", "id": "0x7"},
    {"name": "António José Seguro", "id": "0x8"},
    {"name": "André Ventura", "id": "0x9"}
]

def get_market_data(candidate_name):
    """Fetch market data from Polymarket API"""
    try:
        # Search for the market
        search_url = "https://clob.polymarket.com/markets"
        params = {
            "search": candidate_name,
            "limit": 10
        }
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        resp = requests.get(search_url, params=params, headers=headers, timeout=10)
        resp.raise_for_status()
        
        markets = resp.json()
        
        if not markets or len(markets) == 0:
            return 0.0, 0.0
        
        # Get the first matching market
        market = markets[0]
        market_id = market.get("id")
        
        if not market_id:
            return 0.0, 0.0
        
        # Fetch orderbook for this market
        orderbook_url = f"https://clob.polymarket.com/orderbook/{market_id}"
        ob_resp = requests.get(orderbook_url, headers=headers, timeout=10)
        ob_resp.raise_for_status()
        
        orderbook = ob_resp.json()
        
        bid = 0.0
        ask = 0.0
        
        # Get best bid
        if "bids" in orderbook and len(orderbook["bids"]) > 0:
            bid = float(orderbook["bids"][0]["price"])
        
        # Get best ask
        if "asks" in orderbook and len(orderbook["asks"]) > 0:
            ask = float(orderbook["asks"][0]["price"])
        
        return bid, ask
        
    except requests.exceptions.Timeout:
        st.warning(f"{candidate_name}: Request timeout")
        return 0.0, 0.0
    except requests.exceptions.ConnectionError:
        st.warning(f"{candidate_name}: Connection error")
        return 0.0, 0.0
    except Exception as e:
        st.warning(f"{candidate_name}: {str(e)[:60]}")
        return 0.0, 0.0

def fetch_data():
    """Fetch data for all candidates"""
    data = []
    progress = st.progress(0)
    status = st.empty()
    
    for i, candidate in enumerate(CANDIDATES):
        status.text(f"Fetching {candidate['name']}...")
        bid, ask = get_market_data(candidate['name'])
        
        data.append({
            'name': candidate['name'],
            'bid': bid,
            'ask': ask
        })
        
        progress.progress((i + 1) / len(CANDIDATES))
    
    status.empty()
    return data

# MAIN
st.title("🇵🇹 Polymarket Portugal - Bid/Offer Arb Monitor")
st.caption(f"Updated: {datetime.now().strftime('%H:%M:%S')}")

with st.spinner("Fetching LIVE prices from Polymarket API..."):
    data = fetch_data()

with st.expander("Debug Info"):
    for d in data:
        st.write(f"**{d['name']}**: Bid={d['bid']:.4f}, Ask={d['ask']:.4f}")

if not data or all(d['ask'] == 0 for d in data):
    st.error("Could not fetch any prices from Polymarket API.")
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
    st.warning("No valid price data available")

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
