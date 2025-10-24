import streamlit as st
import pandas as pd
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import re
import time

st.set_page_config(page_title="Polymarket Portugal Monitor", layout="wide")

MARKET_URLS = {
    "Henrique Gouveia e Melo": "https://polymarket.com/event/portugal-presidential-election/will-henrique-gouveia-e-melo-win-the-portugal-presidential-election",
    "Luís Marques Mendes": "https://polymarket.com/event/portugal-presidential-election/will-luis-marques-mendes-win-the-portugal-presidential-election", 
    "António José Seguro": "https://polymarket.com/event/portugal-presidential-election/will-antonio-jose-seguro-win-the-portugal-presidential-election",
    "André Ventura": "https://polymarket.com/event/portugal-presidential-election/will-andre-ventura-win-the-portugal-presidential-election"
}

def setup_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    return webdriver.Chrome(options=options)

def scrape_market(url, name):
    driver = None
    try:
        driver = setup_driver()
        driver.get(url)
        
        # Wait for price elements (YES market bid/ask)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//*[contains(@class, 'price') or contains(@class, 'bid') or contains(@class, 'ask')]"))
        )
        
        # Find bid/ask elements (YES market)
        elements = driver.find_elements(By.XPATH, "//*[contains(@class, 'price') or contains(@class, 'bid') or contains(@class, 'ask')]")
        prices = []
        for elem in elements:
            text = elem.text
            match = re.search(r'(\d+\.?\d*)[%¢$]', text)
            if match:
                price = float(match.group(1))
                if '¢' in text or ('$' in text and price < 1):
                    price /= 100  # Convert cents to decimal (50¢ = 0.50)
                elif '%' in text:
                    price /= 100  # Convert % to decimal (50% = 0.50)
                prices.append(price)
        
        if len(prices) >= 2:
            return max(prices), min(prices)  # Buy (ask, higher), Sell (bid, lower)
        return 0.0, 0.0  # No prices found
        
    except Exception as e:
        st.warning(f"Failed to scrape {name}: {e}")
        return 0.0, 0.0
    finally:
        if driver:
            driver.quit()

def fetch_data():
    candidates = []
    progress = st.progress(0)
    
    for i, (name, url) in enumerate(MARKET_URLS.items()):
        with st.spinner(f"Scraping {name}..."):
            buy_price, sell_price = scrape_market(url, name)
        
        candidates.append({
            'name': name,
            'buy_price': buy_price,
            'sell_price': sell_price,
            'source': 'Live Selenium Scrape'
        })
        
        progress.progress((i + 1) / 4)
        time.sleep(1)
    
    return candidates

# MAIN
st.title("🇵🇹 Polymarket Portugal - Live Trading Arb")
st.caption(f"Updated: {datetime.now().strftime('%H:%M:%S')}")

debug = st.checkbox("Debug: Show Scrape Errors", value=False)

with st.spinner("Scraping LIVE bid/ask from Polymarket..."):
    data = fetch_data()

if not data or all(d['buy_price'] == 0.0 and d['sell_price'] == 0.0 for d in data):
    st.error("No bid/ask data - check Polymarket site or retry")
    st.stop()

data.sort(key=lambda x: x['buy_price'], reverse=True)

# METRICS
cols = st.columns(4)
total_buy = 0
total_sell = 0

for i, d in enumerate(data):
    with cols[i]:
        st.markdown(f"**{d['name'].split()[-1]}**")
        st.caption(f"{d['name'][:15]}... | {d['source']}")
        
        buy_pct = d['buy_price'] * 100
        sell_pct = d['sell_price'] * 100
        
        st.metric("Buy (Ask)", f"{buy_pct:.1f}%")
        st.metric("Sell (Bid)", f"{sell_pct:.1f}%")
        
        total_buy += d['buy_price']
        total_sell += d['sell_price']

# BASKET
st.divider()
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Buy Basket Cost", f"${total_buy*100:.1f}", f"{total_buy*100-100:+.1f}%")
with col2:
    st.metric("Sell Basket Value", f"${total_sell*100:.1f}", f"{total_sell*100-100:+.1f}%")
with col3:
    st.metric("Avg Spread", f"{(total_buy-total_sell)*100:.1f}%")

# ARB
st.subheader("💰 Arbitrage")
if total_buy < 1:
    profit = 100 - total_buy * 100
    st.success(f"🟢 BUY BASKET: ${total_buy*100:.1f} → {profit:.1f}% PROFIT")
elif total_sell > 1:
    profit = total_sell * 100 - 100
    st.success(f"🔴 SELL BASKET: ${total_sell*100:.1f} → {profit:.1f}% PROFIT")
else:
    st.info("⚖️ No Arb")

# CHART
st.subheader("Live Bid/Ask Spreads")
candidates_short = [d['name'].split()[-1] for d in data]
buy_data = [d['buy_price']*100 for d in data]
sell_data = [d['sell_price']*100 for d in data]

chart_data = pd.DataFrame({
    candidates_short[0]: [buy_data[0], sell_data[0]],
    candidates_short[1]: [buy_data[1], sell_data[1]],
    candidates_short[2]: [buy_data[2], sell_data[2]],
    candidates_short[3]: [buy_data[3], sell_data[3]]
}, index=['Buy', 'Sell'])

st.bar_chart(chart_data, height=350)

# TABLE
st.subheader("Trade Execution")
table_data = []
for d in data:
    table_data.append({
        'Candidate': d['name'],
        'Buy @': f"{d['buy_price']*100:.1f}%",
        'Sell @': f"{d['sell_price']*100:.1f}%",
        'Spread': f"{(d['buy_price']-d['sell_price'])*100:.1f}%",
        'Cost (100)': f"${d['buy_price']*100:.1f}",
        'Value (100)': f"${d['sell_price']*100:.1f}"
    })
st.dataframe(table_data, use_container_width=True)

if st.button("🔄 Refresh Live"):
    st.rerun()
