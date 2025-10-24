import streamlit as st
from playwright.sync_api import sync_playwright
import pandas as pd
from datetime import datetime
import time
import re

st.set_page_config(page_title="Polymarket Portugal Monitor", layout="wide")

MARKET_URLS = {
    "Henrique Gouveia e Melo": "https://polymarket.com/event/portugal-presidential-election/will-henrique-gouveia-e-melo-win-the-portugal-presidential-election",
    "Luís Marques Mendes": "https://polymarket.com/event/portugal-presidential-election/will-luis-marques-mendes-win-the-portugal-presidential-election", 
    "António José Seguro": "https://polymarket.com/event/portugal-presidential-election/will-antonio-jose-seguro-win-the-portugal-presidential-election",
    "André Ventura": "https://polymarket.com/event/portugal-presidential-election/will-andre-ventura-win-the-portugal-presidential-election"
}

def scrape_market_playwright(url, name):
    """Scrape market data using Playwright"""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_default_timeout(30000)
            
            page.goto(url, wait_until="networkidle")
            time.sleep(2)
            
            content = page.content()
            
            prices = []
            
            matches = re.findall(r'0\.\d{2}', content)
            prices.extend([float(m) for m in matches])
            
            cent_matches = re.findall(r'(\d+)¢', content)
            prices.extend([int(m) / 100 for m in cent_matches])
            
            browser.close()
            
            if not prices:
                return 0.0, 0.0
            
            prices = sorted(list(set(prices)))
            
            if len(prices) >= 2:
                bid = prices[-1]
                ask = prices[0]
                return bid, ask
            elif len(prices) == 1:
                return prices[0], prices[0]
            
            return 0.0, 0.0
            
    except Exception as e:
        st.warning(f"{name}: Error - {str(e)[:80]}")
        return 0.0, 0.0

def fetch_data():
    """Fetch data for all candidates"""
    candidates = []
    progress = st.progress(0)
    status = st.empty()
    
    for i, (name, url) in enumerate(MARKET_URLS.items()):
        status.text(f"Scraping {name}...")
        bid, ask = scrape_market_playwright(url, name)
        
        candidates.append({
            'name': name,
            'bid': bid,
            'ask': ask
        })
        
        progress.progress((i + 1) / len(MARKET_URLS))
        time.sleep(1)
    
    status.empty()
    return candidates

st.title("🇵🇹 Polymarket Portugal - Bid/Offer Arb Monitor")
st.caption(f"Updated: {datetime.now().strftime('%H:%M:%S')}")

with st.spinner("Scraping LIVE bid/offer from Polymarket..."):
    data = fetch_data()

with st.expander("Debug Info"):
    for d in data:
        st.write(f"**{d['name']}**: Bid={d['bid']:.4f}, Ask={d['ask']:.4f}")

if not data or all(d['ask'] == 0 for d in data):
    st.error("Could not fetch any prices. Markets may not be accessible.")
    st.stop()

data.sort(key=lambda x: x['ask'], reverse=True)

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

st.divider()
col1, col2 = st.columns(2)
with col1:
    st.metric("TOTAL ASK COST", f"{total_ask*100:.2f}%", f"{total_ask*100-100:+.2f}%")
with col2:
    st.metric("TOTAL BID VALUE", f"{total_bid*100:.2f}%", f"{total_bid*100-100:+.2f}%")

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
