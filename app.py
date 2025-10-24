import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import re
import time

st.set_page_config(page_title="Polymarket Portugal Monitor", layout="wide")

MARKET_URLS = {
    "Henrique Gouveia e Melo": "https://polymarket.com/event/portugal-presidential-election/will-henrique-gouveia-e-melo-win-the-portugal-presidential-election",
    "Luís Marques Mendes": "https://polymarket.com/event/portugal-presidential-election/will-luis-marques-mendes-win-the-portugal-presidential-election", 
    "António José Seguro": "https://polymarket.com/event/portugal-presidential-election/will-antonio-jose-seguro-win-the-portugal-presidential-election",
    "André Ventura": "https://polymarket.com/event/portugal-presidential-election/will-andre-ventura-win-the-portugal-presidential-election"
}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

def scrape_market(url, name):
    try:
        time.sleep(1)
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if "error" in resp.text.lower() or "issue" in resp.text.lower():
            st.warning(f"{name}: Site error - no prices available")
            return 0.0, 0.0
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # Look for bid/ask in price classes or text
        price_elems = soup.find_all(['span', 'div'], class_=re.compile(r'price|bid|ask|odds|button'))
        prices = []
        for elem in price_elems:
            text = elem.text.strip()
            # Match numbers with % or ¢
            matches = re.findall(r'(\d+\.?\d*)([%¢$])', text)
            for num, unit in matches:
                price = float(num)
                if unit == '%':
                    price /= 100
                elif unit in '¢$':
                    price /= 100 if price < 1 else 1  # 50¢ = 0.50, $50 = 50%
                prices.append(price)
        
        # Deduplicate and sort
        prices = sorted(set(prices))
        if len(prices) >= 2:
            return prices[-1], prices[0]  # Ask (highest), Bid (lowest)
        elif len(prices) == 1:
            return prices[0], prices[0]  # Single price as both (rare)
        
        st.warning(f"{name}: No prices found - returning 0.0/0.0")
        return 0.0, 0.0
        
    except Exception as e:
        st.warning(f"{name}: Scrape error {e} - 0.0/0.0")
        return 0.0, 0.0

def fetch_data():
    candidates = []
    progress = st.progress(0)
    
    for i, (name, url) in enumerate(MARKET_URLS.items()):
        buy_price, sell_price = scrape_market(url, name)
        
        candidates.append({
            'name': name,
            'buy_price': buy_price,
            'sell_price': sell_price
        })
        
        progress.progress((i + 1) / 4)
    
    return candidates

# MAIN
st.title("🇵🇹 Polymarket Portugal - Bid/Offer Arb Monitor")
st.caption(f"Updated: {datetime.now().strftime('%H:%M:%S')}")

with st.spinner("Scraping LIVE bid/offer..."):
    data = fetch_data()

data.sort(key=lambda x: x['buy_price'], reverse=True)

# METRICS
cols = st.columns(4)
total_buy = 0
total_sell = 0

for i, d in enumerate(data):
    with cols[i]:
        st.markdown(f"**{d['name'].split()[-1]}**")
        buy_pct = d['buy_price'] * 100
        sell_pct = d['sell_price'] * 100
        
        st.metric("Offer (Ask)", f"{buy_pct:.1f}%")
        st.metric("Bid (Sell)", f"{sell_pct:.1f}%")
        
        total_buy += d['buy_price']
        total_sell += d['sell_price']

# BASKET
st.divider()
col1, col2 = st.columns(2)
with col1:
    st.metric("TOTAL OFFER COST", f"{total_buy*100:.1f}%", f"{total_buy*100-100:+.1f}%")
with col2:
    st.metric("TOTAL BID VALUE", f"{total_sell*100:.1f}%", f"{total_sell*100-100:+.1f}%")

# ARB
st.subheader("ARBITRAGE")
if total_buy < 1:
    profit = 100 - total_buy * 100
    st.success(f"🟢 BUY ARB: {profit:.1f}% PROFIT")
elif total_sell > 1:
    profit = total_sell * 100 - 100
    st.success(f"🔴 SELL ARB: {profit:.1f}% PROFIT")
else:
    st.info("No Arb - All 0.0/0.0 due to site errors")

# CHART
st.subheader("Bid/Offer Spreads")
candidates_short = [d['name'].split()[-1] for d in data]
buy_data = [d['buy_price']*100 for d in data]
sell_data = [d['sell_price']*100 for d in data]

chart_data = pd.DataFrame({
    candidates_short[0]: [buy_data[0], sell_data[0]],
    candidates_short[1]: [buy_data[1], sell_data[1]],
    candidates_short[2]: [buy_data[2], sell_data[2]],
    candidates_short[3]: [buy_data[3], sell_data[3]]
}, index=['Offer', 'Bid'])

st.bar_chart(chart_data, height=350)

# TABLE
table_data = []
for d in data:
    table_data.append({
        'Candidate': d['name'],
        'Offer %': f"{d['buy_price']*100:.1f}",
        'Bid %': f"{d['sell_price']*100:.1f}",
        'Spread': f"{(d['buy_price']-d['sell_price'])*100:.1f}%"
    })
st.dataframe(table_data)

if st.button("🔄 REFRESH"):
    st.rerun()
