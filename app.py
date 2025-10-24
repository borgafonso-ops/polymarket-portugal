import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import re

st.set_page_config(page_title="Polymarket Portugal Monitor", layout="wide")

CANDIDATES = [
    "Henrique Gouveia e Melo",
    "Luís Marques Mendes",
    "António José Seguro",
    "André Ventura"
]

def scrape_portugal_election_page():
    """Scrape all candidate prices from the main Portugal election page"""
    try:
        url = "https://polymarket.com/event/portugal-presidential-election"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        
        content = resp.text
        
        data = []
        
        # For each candidate, find their price on the page
        for candidate in CANDIDATES:
            # Find the candidate name in the content
            candidate_lower = candidate.lower()
            pos = content.lower().find(candidate_lower)
            
            if pos == -1:
                data.append({'name': candidate, 'bid': 0.0, 'ask': 0.0})
                continue
            
            # Look in a window around the candidate (within 1000 chars after)
            search_area = content[pos:min(len(content), pos+1000)]
            
            # Look for percentage or decimal price
            # Try to find patterns like "51%", "0.51", "51.5%"
            percent_matches = re.findall(r'>(\d+\.?\d*)%<', search_area)
            decimal_matches = re.findall(r'0\.(\d{2})', search_area)
            
            bid = 0.0
            ask = 0.0
            
            if percent_matches:
                # If we find percentage, use it
                price = float(percent_matches[0]) / 100
                bid = price
                ask = price
            elif decimal_matches:
                # Otherwise use decimal
                price = float("0." + decimal_matches[0])
                bid = price
                ask = price
            
            data.append({'name': candidate, 'bid': bid, 'ask': ask})
        
        return data
        
    except Exception as e:
        st.error(f"Error scraping: {str(e)}")
        return []

# MAIN
st.title("🇵🇹 Polymarket Portugal - Bid/Offer Monitor")
st.caption(f"Updated: {datetime.now().strftime('%H:%M:%S')}")

with st.spinner("Fetching prices from Polymarket..."):
    data = scrape_portugal_election_page()

with st.expander("Debug Info"):
    if data:
        total = sum(d['bid'] for d in data)
        for d in data:
            st.write(f"**{d['name']}**: Bid={d['bid']:.4f}, Ask={d['ask']:.4f}")
        st.write(f"**Total**: {total:.4f}")
    else:
        st.write("No data fetched")

if not data or all(d['bid'] == 0 for d in data):
    st.error("Could not fetch prices")
    st.stop()

data.sort(key=lambda x: x['bid'], reverse=True)

# METRICS
cols = st.columns(4)

for i, d in enumerate(data):
    with cols[i]:
        st.markdown(f"**{d['name'].split()[-1]}**")
        bid_pct = d['bid'] * 100
        ask_pct = d['ask'] * 100
        
        st.metric("Bid %", f"{bid_pct:.2f}%")
        st.metric("Ask %", f"{ask_pct:.2f}%")

# TOTALS
st.divider()
total_bid = sum(d['bid'] for d in data)
total_ask = sum(d['ask'] for d in data)

col1, col2 = st.columns(2)
with col1:
    st.metric("Total Bid", f"{total_bid*100:.2f}%", f"{total_bid*100-100:+.2f}%")
with col2:
    st.metric("Total Ask", f"{total_ask*100:.2f}%", f"{total_ask*100-100:+.2f}%")

# ARB
st.subheader("ARBITRAGE")
if total_bid > 0:
    if total_bid < 1:
        profit = (1 - total_bid) * 100
        st.success(f"🟢 BUY ALL: {profit:.2f}% PROFIT")
    elif total_bid > 1:
        loss = (total_bid - 1) * 100
        st.error(f"🔴 SELL ALL: {loss:.2f}% LOSS")
    else:
        st.info("Market is fairly priced")

# CHART
st.subheader("Market Odds")
candidates_short = [d['name'].split()[-1] for d in data]
bids = [d['bid'] * 100 for d in data]

chart_data = pd.DataFrame({
    'Candidate': candidates_short,
    'Probability %': bids
})

st.bar_chart(chart_data.set_index('Candidate'), height=350)

# TABLE
table_data = []
for d in data:
    table_data.append({
        'Candidate': d['name'],
        'Bid %': f"{d['bid']*100:.2f}",
        'Ask %': f"{d['ask']*100:.2f}",
        'Spread %': f"{(d['bid']-d['ask'])*100:.2f}"
    })
st.dataframe(table_data, use_container_width=True)

if st.button("🔄 REFRESH"):
    st.rerun()
