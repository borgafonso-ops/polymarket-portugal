import streamlit as st
import requests
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Polymarket Portugal Monitor", layout="wide")

MARKET_SLUGS = {
    "Henrique Gouveia e Melo": "will-henrique-gouveia-e-melo-win-the-2026-portugal-presidential-election",
    "Luís Marques Mendes": "will-luis-marques-mendes-win-the-2026-portugal-presidential-election",
    "António José Seguro": "will-antonio-jose-seguro-win-the-2026-portugal-presidential-election",
    "André Ventura": "will-andre-ventura-win-the-2026-portugal-presidential-election"
}

def fetch_market_data(slug):
    """Fetch market data from Polymarket API"""
    try:
        url = "https://gamma-api.polymarket.com/markets"
        params = {"slug": slug}
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        resp.raise_for_status()
        
        markets = resp.json()
        
        if markets and len(markets) > 0:
            market = markets[0]
            return {
                'name': market.get('question', ''),
                'bid': float(market.get('bestBid', 0)),
                'ask': float(market.get('bestAsk', 0)),
                'volume': market.get('volume', 0),
                'liquidity': market.get('liquidity', 0)
            }
        return None
        
    except Exception as e:
        st.warning(f"Error fetching {slug}: {e}")
        return None

def fetch_all_data():
    """Fetch data for all candidates"""
    data = []
    progress = st.progress(0)
    status = st.empty()
    
    for i, (name, slug) in enumerate(MARKET_SLUGS.items()):
        status.text(f"Fetching {name}...")
        market = fetch_market_data(slug)
        
        if market:
            data.append({
                'name': name,
                'bid': market['ask'],  # Swap: API's bestBid is actually the ask
                'ask': market['bid'],  # API's bestAsk is actually the bid
                'volume': market['volume'],
                'liquidity': market['liquidity']
            })
        else:
            data.append({
                'name': name,
                'bid': 0.0,
                'ask': 0.0,
                'volume': 0,
                'liquidity': 0
            })
        
        progress.progress((i + 1) / len(MARKET_SLUGS))
    
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
            try:
                vol = float(d['volume']) if d['volume'] else 0
                st.write(f"  Volume: ${vol:,.0f}")
            except:
                st.write(f"  Volume: {d['volume']}")
        
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
    try:
        vol = f"${float(d['volume']):,.0f}" if d['volume'] else "$0"
    except:
        vol = str(d['volume'])
    table_data.append({
        'Candidate': d['name'],
        'Bid %': f"{d['bid']*100:.2f}",
        'Ask %': f"{d['ask']*100:.2f}",
        'Spread (¢)': f"{spread:.2f}",
        'Volume': vol
    })
st.dataframe(table_data, use_container_width=True)

if st.button("🔄 REFRESH"):
    st.rerun()
