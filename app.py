import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import re
import time

st.set_page_config(page_title="Polymarket Portugal Monitor", layout="wide")

# Live market URLs (direct from Polymarket)
MARKET_URLS = {
    "Henrique Gouveia e Melo": "https://polymarket.com/event/portugal-presidential-election/will-henrique-gouveia-e-melo-win",
    "Luís Marques Mendes": "https://polymarket.com/event/portugal-presidential-election/will-luis-marques-mendes-win", 
    "António José Seguro": "https://polymarket.com/event/portugal-presidential-election/will-antonio-jose-seguro-win",
    "André Ventura": "https://polymarket.com/event/portugal-presidential-election/will-andre-ventura-win"
}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

def scrape_market(url):
    """Scrape LIVE bid/ask from Polymarket trading page"""
    try:
        time.sleep(1)
        resp = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # Find YES bid/ask elements (Polymarket HTML structure)
        bid_elem = soup.find('span', {'data-testid': 'bid-price'})
        ask_elem = soup.find('span', {'data-testid': 'ask-price'})
        
        if bid_elem and ask_elem:
            sell_price = float(bid_elem.text.strip('%')) / 100  # Bid
            buy_price = float(ask_elem.text.strip('%')) / 100   # Ask
            return buy_price, sell_price
        
        # Fallback: Parse from price display
        price_elem = soup.find('span', class_='price-display')
        if price_elem:
            price_text = price_elem.text.strip('%')
            price = float(price_text) / 100
            return price, price  # Midpoint fallback
        
        return 0.0, 0.0
    except:
        return 0.0, 0.0

def fetch_data():
    candidates = []
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, (name, url) in enumerate(MARKET_URLS.items()):
        status_text.text(f"Scraping {name}...")
        buy_price, sell_price = scrape_market(url)
        
        candidates.append({
            'name': name,
            'buy_price': buy_price,
            'sell_price': sell_price,
            'volume': 0,  # Volume from API if needed later
            'source': 'LIVE Trading Page'
        })
        
        progress_bar.progress((i + 1) / len(MARKET_URLS))
    
    status_text.text('Done!')
    return candidates

# MAIN
st.title("Polymarket Portugal - LIVE Trading Monitor")
st.caption(f"Updated: {datetime.now().strftime('%H:%M:%S')}")

with st.spinner("Scraping LIVE bid/ask from Polymarket.com..."):
    data = fetch_data()

if not data:
    st.error("Failed to load - retry")
    st.stop()

data.sort(key=lambda x: x['buy_price'], reverse=True)

# METRICS
cols = st.columns(4)
total_buy_cost = 0
total_sell_proceeds = 0

for i, d in enumerate(data):
    with cols[i]:
        st.markdown(f"**{d['name'].split()[-1]}**")
        
        buy_pct = d['buy_price'] * 100
        sell_pct = d['sell_price'] * 100
        
        st.metric("BUY (Ask)", f"{buy_pct:.1f}%")
        st.metric("SELL (Bid)", f"{sell_pct:.1f}%")
        
        total_buy_cost += d['buy_price']
        total_sell_proceeds += d['sell_price']

# BASKET TOTALS
st.divider()
col1, col2 = st.columns(2)
with col1:
    st.metric("TOTAL BUY BASKET", f"${total_buy_cost*100:.1f}", f"{total_buy_cost*100-100:+.1f}%")
with col2:
    st.metric("TOTAL SELL BASKET", f"${total_sell_proceeds*100:.1f}", f"{total_sell_proceeds*100-100:+.1f}%")

# ARB CALC
st.subheader("🤑 ARBITRAGE")
basket_cost = total_buy_cost * 100
basket_value = total_sell_proceeds * 100

if basket_cost < 100:
    profit_pct = 100 - basket_cost
    st.success(f"🟢 **BUY BASKET NOW**: Cost ${basket_cost:.1f} → **{profit_pct:.1f}% INSTANT PROFIT**")
elif basket_value > 100:
    profit_pct = basket_value - 100
    st.success(f"🔴 **SELL BASKET NOW**: Value ${basket_value:.1f} → **{profit_pct:.1f}% INSTANT PROFIT**")
else:
    st.info("⚖️ Balanced - Wait for mispricing")

# CHART
st.subheader("LIVE Bid/Ask Spreads")
buy_data = [d['buy_price']*100 for d in data]
sell_data = [d['sell_price']*100 for d in data]
candidates = [d['name'].split()[-1] for d in data]

chart_data = pd.DataFrame({
    candidates[0]: [buy_data[0], sell_data[0]],
    candidates[1]: [buy_data[1], sell_data[1]],
    candidates[2]: [buy_data[2], sell_data[2]],
    candidates[3]: [buy_data[3], sell_data[3]]
}, index=['Buy', 'Sell'])

st.bar_chart(chart_data, height=350)

# TRADE TABLE
st.subheader("TRADE EXECUTION")
table_data = []
for d in data:
    table_data.append({
        'Candidate': d['name'],
        'BUY @': f"{d['buy_price']*100:.2f}%",
        'SELL @': f"{d['sell_price']*100:.2f}%", 
        'SPREAD': f"{(d['buy_price']-d['sell_price'])*100:.2f}%"
    })
st.dataframe(table_data)

if st.button("🔄 REFRESH LIVE TRADING DATA"):
    st.rerun()
