import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import json
import re

st.set_page_config(page_title="Polymarket Portugal Monitor", layout="wide")

CANDIDATES = [
    "Henrique Gouveia e Melo",
    "Luís Marques Mendes", 
    "António José Seguro",
    "André Ventura"
]

def scrape_portugal_market():
    """Scrape the Portugal presidential election market"""
    try:
        url = "https://polymarket.com/event/portugal-presidential-election"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        content = resp.text
        
        # Look for JSON data embedded in the page (Next.js stores it in __NEXT_DATA__)
        next_data_match = re.search(r'<script id="__NEXT_DATA__"[^>]*>({.*?})</script>', content, re.DOTALL)
        
        data = []
        
        if next_data_match:
            try:
                json_data = json.loads(next_data_match.group(1))
                st.write("✓ Found market JSON data")
                # Store for inspection
                st.session_state.market_json = json_data
            except:
                st.write("Could not parse JSON")
        
        # Fallback: Extract prices directly from visible text
        # Look for patterns: "51%", "21%", "15%", "10%"
        # More specifically, look for the outcome cards
        
        # Find all outcome sections with candidate names and prices
        for candidate in CANDIDATES:
            # Look for the candidate name followed by a percentage
            pattern = candidate.replace("(", r"\(").replace(")", r"\)")
            
            # Find candidate in content
            match = re.search(f'{pattern}.*?(\d+\.?\d*)%', content, re.IGNORECASE | re.DOTALL)
            
            if match:
                price_str = match.group(1)
                mid_price = float(price_str) / 100
                
                # Assume small bid/ask spread of ±1%
                bid = mid_price + 0.01
                ask = mid_price - 0.01
                
                data.append({
                    'name': candidate,
                    'mid': mid_price,
                    'bid': bid,
                    'ask': ask
                })
            else:
                data.append({
                    'name': candidate,
                    'mid': 0.0,
                    'bid': 0.0,
                    'ask': 0.0
                })
        
        return data
        
    except Exception as e:
        st.error(f"Error: {e}")
        return []

# MAIN
st.title("🇵🇹 Polymarket Portugal - Bid/Offer Monitor")
st.caption(f"Updated: {datetime.now().strftime('%H:%M:%S')}")

with st.spinner("Fetching data..."):
    data = scrape_portugal_market()

with st.expander("Debug Info"):
    if data:
        total_mid = sum(d['mid'] for d in data)
        total_bid = sum(d['bid'] for d in data)
        total_ask = sum(d['ask'] for d in data)
        
        for d in data:
            st.write(f"**{d['name']}**: Mid={d['mid']*100:.2f}%, Bid={d['bid']*100:.2f}%, Ask={d['ask']*100:.2f}%")
        st.write(f"**Totals**: Mid={total_mid*100:.2f}%, Bid={total_bid*100:.2f}%, Ask={total_ask*100:.2f}%")

if not data or all(d['mid'] == 0 for d in data):
    st.error("Could not fetch prices")
    st.stop()

data.sort(key=lambda x: x['mid'], reverse=True)

# METRICS
cols = st.columns(4)
total_bid = 0
total_ask = 0

for i, d in enumerate(data):
    with cols[i]:
        st.markdown(f"**{d['name'].split()[-1]}**")
        
        st.metric("Mid %", f"{d['mid']*100:.2f}%")
        st.metric("Bid %", f"{d['bid']*100:.2f}%")
        st.metric("Ask %", f"{d['ask']*100:.2f}%")
        
        total_bid += d['bid']
        total_ask += d['ask']

# TOTALS
st.divider()
col1, col2 = st.columns(2)
with col1:
    st.metric("Total Bid", f"{total_bid*100:.2f}%")
with col2:
    st.metric("Total Ask", f"{total_ask*100:.2f}%")

# TABLE
table_data = []
for d in data:
    spread = (d['bid'] - d['ask']) * 100
    table_data.append({
        'Candidate': d['name'],
        'Mid %': f"{d['mid']*100:.2f}",
        'Bid %': f"{d['bid']*100:.2f}",
        'Ask %': f"{d['ask']*100:.2f}",
        'Spread (¢)': f"{spread:.1f}"
    })
st.dataframe(table_data, use_container_width=True)

if st.button("🔄 REFRESH"):
    st.rerun()
