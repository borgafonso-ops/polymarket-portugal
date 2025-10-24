import streamlit as st
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
from datetime import datetime
import time

st.set_page_config(page_title="Polymarket Portugal Monitor", layout="wide")

MARKET_URLS = {
    "Henrique Gouveia e Melo": "https://polymarket.com/event/portugal-presidential-election/will-henrique-gouveia-e-melo-win-the-portugal-presidential-election",
    "Luís Marques Mendes": "https://polymarket.com/event/portugal-presidential-election/will-luis-marques-mendes-win-the-portugal-presidential-election", 
    "António José Seguro": "https://polymarket.com/event/portugal-presidential-election/will-antonio-jose-seguro-win-the-portugal-presidential-election",
    "André Ventura": "https://polymarket.com/event/portugal-presidential-election/will-andre-ventura-win-the-portugal-presidential-election"
}

def scrape_market_selenium(url, name):
    """Scrape market data using Selenium"""
    try:
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        
        driver = webdriver.Chrome(options=options)
        driver.get(url)
        
        # Wait for price elements to load
        wait = WebDriverWait(driver, 15)
        
        bid = 0.0
        ask = 0.0
        
        try:
            # Look for bid price (usually on left side)
            bid_elem = wait.until(
                EC.presence_of_all_elements_located((By.XPATH, "//span[contains(text(), 'Bid') or contains(text(), 'bid')]"))
            )
            
            # Look for ask price (usually on right side)  
            ask_elem = wait.until(
                EC.presence_of_all_elements_located((By.XPATH, "//span[contains(text(), 'Ask') or contains(text(), 'ask')]"))
            )
            
            # Try to extract numeric prices from text content
            for elem in driver.find_elements(By.XPATH, "//span[@class]"):
                text = elem.text.strip()
                try:
                    # Check if it's a price (contains ¢ or is a decimal between 0-1)
                    if '¢' in text:
                        price = float(text.replace('¢', '').strip()) / 100
                        if 0 <= price <= 1:
                            if bid == 0.0:
                                bid = price
                            else:
                                ask = price
                    elif text.startswith('0.') or text.startswith('1.'):
                        price = float(text)
                        if 0 <= price <= 1:
                            if bid == 0.0:
                                bid = price
                            else:
                                ask = price
                except:
                    pass
            
            driver.quit()
            return bid, ask
            
        except Exception as e:
            driver.quit()
            return 0.0, 0.0
            
    except Exception as e:
        st.warning(f"{name}: Selenium error - {str(e)[:50]}")
        return 0.0, 0.0

def fetch_data():
    """Fetch data for all candidates"""
    candidates = []
    progress = st.progress(0)
    status = st.empty()
    
    for i, (name, url) in enumerate(MARKET_URLS.items()):
        status.text(f"Scraping {name}...")
        bid, ask = scrape_market_selenium(url, name)
        
        candidates.append({
            'name': name,
            'bid': bid,
            'ask': ask
        })
        
        progress.progress((i + 1) / len(MARKET_URLS))
        time.sleep(1)
    
    status.empty()
    return candidates

# MAIN
st.title("🇵🇹 Polymarket Portugal - Bid/Offer Arb Monitor")
st.caption(f"Updated: {datetime.now().strftime('%H:%M:%S')}")

with st.spinner("Scraping LIVE bid/offer from Polymarket..."):
    data = fetch_data()

# Show debug info
with st.expander("Debug Info"):
    for d in data:
        st.write(f"**{d['name']}**: Bid={d['bid']:.4f}, Ask={d['ask']:.4f}")

if not data or all(d['ask'] == 0 for d in data):
    st.error("Could not fetch any prices. Markets may not be accessible.")
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
