import streamlit as st
import requests
import time
import pandas as pd
from datetime import datetime
import re
import json

st.set_page_config(page_title="Polymarket Portugal Monitor", layout="wide")

GAMMA_API_EVENTS_URL = "https://gamma-api.polymarket.com/events"
GAMMA_API_MARKET_URL = "https://gamma-api.polymarket.com/markets/"
CLOB_PRICES_URL = "https://clob.polymarket.com/prices"
HEADERS = {'User-Agent': 'PolymarketStreamlitMonitor/2.0', 'Content-Type': 'application/json'}

TARGET_CANDIDATES = {
    "Henrique Gouveia e Melo",
    "Luís Marques Mendes", 
    "António José Seguro",
    "André Ventura"
}

@st.cache_data(ttl=10)
def robust_fetch(url, method='GET', json_data=None):
    try:
        time.sleep(0.5)
        if method == 'POST':
            resp = requests.post(url, headers=HEADERS, json=json_data, timeout=10)
        else:
            resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except:
        return None

def safe_int(value):
    try:
        return int(float(value or 0))
    except:
        return 0

def safe_float(value):
    try:
        return float(value or 0)
    except:
        return 0.0

def get_prices_from_clob(token_ids):
    if not token_ids:
        return {}
    json_data = {'token_ids': token_ids}
    data = robust_fetch(CLOB_PRICES_URL, method='POST', json_data=json_data)
    if data:
        return data  # FIXED: {token_id: [bid, ask]} format
    return {}

def fetch_data(debug=False):
    event_data = robust_fetch(f"{GAMMA_API_EVENTS_URL}?slug=portugal-presidential-election")
    if not event_data or not isinstance(event_data, list) or not event_data[0]:
        return []
    
    event = event_data[0]
    markets = event.get('markets', [])
    
    candidates = []
    token_ids = []
    
    for market in markets:
        market_id = market.get('id')
        if not market_id:
            continue
            
        market_data = robust_fetch(f"{GAMMA_API_MARKET_URL}{market_id}")
        if not market_data:
            continue
            
        name = extract_candidate_name(market_data.get('question', ''))
        if name not in TARGET_CANDIDATES:
            continue
        
        volume = safe_int(market_data.get('volume'))
        token_ids_raw = market_data.get('clobTokenIds', [])
        if not token_ids_raw:
            continue
        yes_token = token_ids_raw[0]
        token_ids.append(yes_token)
        
        candidates.append({
            'name': name,
            'volume': volume,
            'yes_token': yes_token,
            'midpoint': safe_float(market_data.get('lastPrice') or market_data.get('lastTradePrice'))
        })
        
        if len(candidates) == 4:
            break
    
    # FIXED: CORRECT PARSING FOR [bid, ask] FORMAT
    clob_prices = get_prices_from_clob(token_ids)
    if debug:
        st.info(f"CLOB RAW: {json.dumps(clob_prices, indent=2)}")
    
    for i, cand in enumerate(candidates):
        token = cand['yes_token']
        if token in clob_prices:
            # FIXED: [bid, ask] array, not dict
            prices = clob_prices[token]
            sell_price = safe_float(prices[0])  # bid
            buy_price = safe_float(prices[1])   # ask
            source = "CLOB (Real Bid/Ask)"
        else:
            buy_price = sell_price = cand['midpoint']
            source = "Midpoint (No CLOB)"
        
        candidates[i]['buy_price'] = buy_price
        candidates[i]['sell_price'] = sell_price
        candidates[i]['source'] = source
    
    return candidates

def extract_candidate_name(question):
    if not question:
        return None
    match = re.search(r'Will (.*?) win', question)
    return match.group(1).strip() if match else None

# MAIN
st.title("Polymarket Portugal - 100 Contract Basket Arb")
st.caption(f"Updated: {datetime.now().strftime('%H:%M:%S')}")

debug = st.checkbox("Debug: Show CLOB Response", value=False)

with st.spinner("Fetching CLOB prices..."):
    data = fetch_data(debug=debug)

if not data:
    st.error("No data")
    st.stop()

data.sort(key=lambda x: x['buy_price'], reverse=True)

# METRICS
cols = st.columns(4)
total_buy_cost = 0
total_sell_proceeds = 0

for i, d in enumerate(data):
    with cols[i]:
        st.markdown(f"**{d['name'].split()[-1]}**")
        st.caption(f"{d['name'][:15]}... | ${d['volume']:,.0f}")
        
        buy_pct = d['buy_price'] * 100
        sell_pct = d['sell_price'] * 100
        
        st.metric("Buy", f"{buy_pct:.1f}%")
        st.metric("Sell", f"{sell_pct:.1f}%")
        
        total_buy_cost += d['buy_price']
        total_sell_proceeds += d['sell_price']

# BASKET
st.divider()
col1, col2 = st.columns(2)
with col1:
    st.metric("TOTAL BUY", f"{total_buy_cost*100:.1f}%", f"{total_buy_cost*100-100:+.1f}%")
with col2:
    st.metric("TOTAL SELL", f"{total_sell_proceeds*100:.1f}%", f"{total_sell_proceeds*100-100:+.1f}%")

# ARB
st.subheader("ARBITRAGE")
if total_buy_cost < 1:
    profit = 100 - total_buy_cost * 100
    st.success(f"BUY ARB: {profit:.1f}% PROFIT")
elif total_sell_proceeds > 1:
    profit = total_sell_proceeds * 100 - 100
    st.success(f"SELL ARB: {profit:.1f}% PROFIT")
else:
    st.info("No Arb")

# CHART
st.subheader("Bid/Ask Spreads")
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

# TABLE
table_data = []
for d in data:
    table_data.append({
        'Candidate': d['name'],
        'Buy %': f"{d['buy_price']*100:.2f}",
        'Sell %': f"{d['sell_price']*100:.2f}",
        'Spread': f"{(d['buy_price']-d['sell_price'])*100:.2f}%",
        'Volume': f"${d['volume']:,.0f}"
    })
st.dataframe(table_data)

if st.button("Refresh"):
    st.rerun()
