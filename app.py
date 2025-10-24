import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import re
import json

st.set_page_config(page_title="Polymarket Portugal Monitor", layout="wide")

MARKET_URLS = {
    "Henrique Gouveia e Melo": "https://polymarket.com/event/portugal-presidential-election/will-henrique-gouveia-e-melo-win-the-portugal-presidential-election",
    "Luís Marques Mendes": "https://polymarket.com/event/portugal-presidential-election/will-luis-marques-mendes-win-the-portugal-presidential-election",
    "António José Seguro": "https://polymarket.com/event/portugal-presidential-election/will-antonio-jose-seguro-win-the-portugal-presidential-election",
    "André Ventura": "https://polymarket.com/event/portugal-presidential-election/will-andre-ventura-win-the-portugal-presidential-election"
}

def extract_market_id_from_url(url):
    """Extract market ID from URL if possible"""
    try:
        # Try direct API search for the market
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        # Fetch the page to look for market ID in JSON
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        
        content = resp.text
        
        # Look for market ID patterns in the page (usually in JSON data)
        # Market IDs are long hex strings starting with 0x
        market_ids = re.findall(r'"id":"(0x[a-f0-9]{64})"', content)
        
        if market_ids:
            return market_ids[0]
        
        return None
        
    except Exception as e:
        return None

def get_orderbook_data(market_id):
    """Fetch orderbook data from API"""
    try:
        url = f"https://clob.polymarket.com/orderbook/{market_id}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        
        orderbook = resp.json()
        
        bid = 0.0
        ask = 0.0
        
        # Get best bid (highest bid price)
        if isinstance(orderbook, dict) and "bids" in orderbook:
            bids = orderbook.get("bids", [])
            if bids and len(bids) > 0:
                bid = float(bids[0].get("price", 0))
        
        # Get best ask (lowest ask price)
        if isinstance(orderbook, dict) and "asks" in orderbook:
            asks = orderbook.get("asks", [])
            if asks and len(asks) > 0:
                ask = float(asks[0].get("price", 0))
        
        return bid, ask
        
    except Exception as e:
        return 0.0, 0.0

def scrape_market_data(url, name):
    """Scrape bid/ask data for a specific market"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        
        content = resp.text
        
        # Extract market ID from the page
        market_id = extract_market_id_from_url(url)
        
        if market_id:
            bid, ask = get_orderbook_data(market_id)
            if bid > 0 or ask > 0:
                return bid, ask
        
        # Fallback: try to extract prices from HTML
        # Look for price patterns like "0.51" or "51¢" or "51%"
        prices = []
        
        # Find decimal prices (0.XX)
        decimal_matches = re.findall(r'0\.\d{2}', content)
        prices.extend([float(m) for m in decimal_matches])
        
        # Find cent prices (XX¢)
        cent_matches = re.findall(r'>(\d+)¢<', content)
        prices.extend([int(m) / 100 for m in cent_matches])
        
        if prices:
            prices = sorted(list(set(prices)))
            if len(prices) >= 2:
                return prices[-1], prices[0]  # bid (high), ask (low)
            elif len(prices) == 1:
                return prices[0], prices[0]
        
        return 0.0, 0.0
        
    except Exception as e:
        st.warning(f"{name}: {str(e)[:50]}")
        return 0.0, 0.0

def fetch_data():
    """Fetch data for all candidates"""
    data = []
    progress = st.progress(0)
    status = st.empty()
    
    for i, (name, url) in enumerate(MARKET_URLS.items()):
        status.text(f"Fetching {name}...")
        bid, ask = scrape_market_data(url, name)
        
        data.append({
            'name': name,
            'bid': bid,
            'ask': ask
        })
        
        progress.progress((i + 1) / len(MARKET_URLS))
    
    status.empty()
    return data

# MAIN
st.title("🇵🇹 Polymarket Portugal - Bid/Offer Arb Monitor")
st.caption(f"Updated: {datetime.now().strftime('%H:%M:%S')}")

with st.spinner("Fetching LIVE bid/offer data..."):
    data = fetch_data()

with st.expander("Debug Info"):
    if data:
        for d in data:
            st.write(f"**{d['name']}**: Bid={d['bid']:.4f}, Ask={d['ask']:.4f}")
    else:
        st.write("No data fetched")

if not data or all(d['ask'] == 0 for d in data):
    st.error("Could not fetch bid/ask data")
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
        
        st.metric("Ask", f"{ask_pct:.2f}%")
        st.metric("Bid", f"{bid_pct:.2f}%")
        
        if d['ask'] > 0 and d['bid'] > 0:
            total_ask += d['ask']
            total_bid += d['bid']
            valid_count += 1

# BASKET
if valid_count > 0:
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
        st.info("No Arb Opportunity")

    # CHART
    st.subheader("Bid/Ask Spreads")
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
