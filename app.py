import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import re
import time

st.set_page_config(page_title="Polymarket Portugal Monitor", layout="wide")

# Direct market URLs (update if slugs change)
MARKET_URLS = {
    "Henrique Gouveia e Melo": "https://polymarket.com/event/portugal-presidential-election/will-henrique-gouveia-e-melo-win-the-portugal-presidential-election",
    "Luís Marques Mendes": "https://polymarket.com/event/portugal-presidential-election/will-luis-marques-mendes-win-the-portugal-presidential-election",
    "António José Seguro": "https://polymarket.com/event/portugal-presidential-election/will-antonio-jose-seguro-win-the-portugal-presidential-election",
    "André Ventura": "https://polymarket.com/event/portugal-presidential-election/will-andre-ventura-win-the-portugal-presidential-election"
}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

def scrape_market(url):
    """Scrape live bid/ask from Polymarket market page."""
    try:
        time.sleep(1)  # Rate limit
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # Target YES bid/ask (Polymarket UI classes for price display)
        # Bid (sell price): green button or .bid-price
        # Ask (buy price): red button or .ask-price
        bid_elem = soup.find('div', class_=re.compile(r'bid|sell-price')) or soup.find('span', text=re.compile(r'bid|sell'))
        ask_elem = soup.find('div', class_=re.compile(r'ask|buy-price')) or soup.find('span', text=re.compile(r'ask|buy'))
        
        if bid_elem and ask_elem:
            sell_price = float(re.search(r'(\d+\.?\d*)', bid_elem.text).group(1)) / 100 if re.search(r'(\d+\.?\d*)', bid_elem.text) else 0.0
            buy_price = float(re.search(r'(\d+\.?\d*)', ask_elem.text).group(1)) / 100 if re.search(r'(\d+\.?\d*)', ask_elem.text) else 0.0
            return buy_price, sell_price
        
        # Fallback: Midpoint from main price display
        price_elem = soup.find('div', class_=re.compile(r'price|odds'))
        if price_elem:
            price_text = re.search(r'(\d+\.?\d*)', price_elem.text)
            if price_text:
                midpoint = float(price_text.group(1)) / 100
                return midpoint, midpoint  # Bid/Ask same if no spread visible
        
        return 0.0, 0.0
    except Exception as e:
        st.warning(f"Scrape error for {url}: {e}")
        return 0.0, 0.0

def fetch_data():
    candidates = []
    progress = st.progress(0)
    
    for i, (name, url) in enumerate(MARKET_URLS.items()):
        with st.spinner(f"Scraping {name}..."):
            buy_price, sell_price = scrape_market(url)
        
        candidates.append({
            'name': name,
            'buy_price': buy_price,
            'sell_price': sell_price,
            'volume': 0,  # Add Gamma API if needed
            'source': 'Live Page Scrape'
        })
        
        progress.progress((i + 1) / len(MARKET_URLS))
    
    return candidates

# MAIN
st.title("🇵🇹 Polymarket Portugal - Live Trading Arb Monitor")
st.caption(f"Last Update: {datetime.now().strftime('%H:%M:%S')}")

debug = st.checkbox("Debug: Show Scrape Logs", value=False)

with st.spinner("Scraping live bid/ask from Polymarket pages..."):
    data = fetch_data()

if not data:
    st.error("Failed to scrape - check URLs or retry")
    st.stop()

data.sort(key=lambda x: x['buy_price'], reverse=True)

# CANDIDATE METRICS
st.subheader("Live Prices (100 Shares Each)")
cols = st.columns(4)
total_buy = 0
total_sell = 0

for i, d in enumerate(data):
    with cols[i]:
        st.markdown(f"**{d['name'].split()[-1]}**")
        st.caption(f"{d['name']} | {d['source']}")
        
        buy_pct = d['buy_price'] * 100
        sell_pct = d['sell_price'] * 100
        
        st.metric("Buy (Ask)", f"{buy_pct:.2f}%")
        st.metric("Sell (Bid)", f"{sell_pct:.2f}%")
        
        total_buy += d['buy_price']
        total_sell += d['sell_price']

# BASKET TOTALS
st.divider()
col1, col2, col3 = st.columns(3)
with col1:
    delta_buy = total_buy * 100 - 100
    st.metric("🔴 Basket Buy Cost", f"{total_buy * 100:.2f}%", delta=f"{delta_buy:+.2f}% vs 100%")
with col2:
    delta_sell = total_sell * 100 - 100
    st.metric("🟢 Basket Sell Value", f"{total_sell * 100:.2f}%", delta=f"{delta_sell:+.2f}% vs 100%")
with col3:
    spread = (total_buy - total_sell) * 100
    st.metric("📊 Avg Spread", f"{spread:.2f}%")

# ARBITRAGE
st.subheader("💰 Arbitrage Alert")
basket_cost = total_buy * 100
basket_value = total_sell * 100
spread_total = (basket_cost - basket_value)

if basket_cost < 100:
    profit = 100 - basket_cost
    st.success(f"🟢 **BUY BASKET ARB**: Buy all 4 for ${basket_cost:.2f} (profit **{profit:.2f}%**) - Execute NOW!")
elif basket_value > 100:
    profit = basket_value - 100
    st.success(f"🔴 **SELL BASKET ARB**: Sell all 4 for ${basket_value:.2f} (profit **{profit:.2f}%**) - Execute NOW!")
else:
    st.info(f"⚖️ Balanced (spread {spread_total:.2f}%) - No arb, but monitor for shifts")

# CHART
st.subheader("Live Bid/Ask Spreads")
chart_data = pd.DataFrame({
    [d['name'].split()[-1] for d in data]: [d['buy_price']*100 for d in data],
    [d['name'].split()[-1] for d in data]: [d['sell_price']*100 for d in data]
}).T
chart_data.columns = ['Buy (Ask)', 'Sell (Bid)']
st.bar_chart(chart_data)

# TABLE
st.subheader("Trade Execution Table")
table_data = []
for d in data:
    table_data.append({
        'Candidate': d['name'],
        'Buy @ %': f"{d['buy_price']*100:.2f}",
        'Sell @ %': f"{d['sell_price']*100:.2f}",
        'Spread %': f"{(d['buy_price'] - d['sell_price'])*100:.2f}",
        'Cost 100 Shares': f"${d['buy_price']*100:.2f}",
        'Value 100 Shares': f"${d['sell_price']*100:.2f}"
    })
st.dataframe(table_data, use_container_width=True)

if st.button("🔄 Refresh Live Data"):
    st.rerun()
