import streamlit as st
import requests
import time
import pandas as pd
from datetime import datetime
import re

st.set_page_config(page_title="Polymarket Portugal Monitor", layout="wide")

GAMMA_API_EVENTS_URL = "https://gamma-api.polymarket.com/events"
GAMMA_API_MARKET_URL = "https://gamma-api.polymarket.com/markets/"
HEADERS = {'User-Agent': 'PolymarketStreamlitMonitor/2.0'}

TARGET_CANDIDATES = {
    "Henrique Gouveia e Melo",
    "Luís Marques Mendes", 
    "António José Seguro",
    "André Ventura"
}

@st.cache_data(ttl=30)
def robust_fetch(url, headers=HEADERS):
    try:
        time.sleep(1)
        resp = requests.get(url, timeout=15, headers=headers)
        resp.raise_for_status()
        return resp.json()
    except:
        return None

def extract_candidate_name(question):
    if not question:
        return None
    match = re.search(r'Will (.*?) win', question)
    return match.group(1).strip() if match else None

MOCK_DATA = [
    {'name': 'Henrique Gouveia e Melo', 'price': 0.51, 'volume': 34000},
    {'name': 'Luís Marques Mendes', 'price': 0.21, 'volume': 28000},
    {'name': 'António José Seguro', 'price': 0.15, 'volume': 28000},
    {'name': 'André Ventura', 'price': 0.11, 'volume': 46000}
]

def fetch_data():
    try:
        event_data = robust_fetch(f"{GAMMA_API_EVENTS_URL}?slug=portugal-presidential-election")
        if not event_data or not isinstance(event_data, list) or not event_data[0]:
            return MOCK_DATA
        
        event = event_data[0]
        markets = event.get('markets', [])
        
        candidates = []
        for market in markets[:20]:
            market_id = market.get('id')
            if not market_id:
                continue
                
            market_data = robust_fetch(f"{GAMMA_API_MARKET_URL}{market_id}")
            if not market_data:
                continue
                
            name = extract_candidate_name(market_data.get('question', ''))
            if name not in TARGET_CANDIDATES:
                continue
            
            volume = int(market_data.get('volume') or 0)
            price = float(market_data.get('lastTradePrice') or market_data.get('lastPrice') or 0)
            
            candidates.append({'name': name, 'price': price, 'volume': volume})
            if len(candidates) == 4:
                break
        
        if len(candidates) < 4:
            for mock in MOCK_DATA:
                if mock['name'] not in {c['name'] for c in candidates}:
                    candidates.append(mock)
                    if len(candidates) == 4:
                        break
        
        return candidates
        
    except Exception:
        return MOCK_DATA

# MAIN
st.title("Polymarket Portugal Election Monitor")
st.caption(f"Updated: {datetime.now().strftime('%H:%M:%S')}")

with st.spinner("Loading..."):
    data = fetch_data()

data.sort(key=lambda x: x['price'], reverse=True)

cols = st.columns(4)
total = sum(d['price'] for d in data)

for i, d in enumerate(data):
    with cols[i]:
        st.markdown(f"**{d['name'].split()[-1]}**")
        vol_str = f"${d['volume']:,.0f}" if d['volume'] else "$0"
        st.caption(f"{d['name']} | {vol_str}")
        st.metric("Price", f"{d['price']*100:.1f}%")

st.divider()
col1, col2 = st.columns(2)
with col1:
    st.metric("Total Sum", f"{total*100:.1f}%", delta=f"{total*100-100:+.1f}%")

if total < 1:
    st.success(f"Buy Arb: {100-total*100:.1f}% profit")
elif total > 1:
    st.success(f"Sell Arb: {total*100-100:.1f}% profit")
else:
    st.info("Balanced")

df = pd.DataFrame({
    'Candidate': [d['name'].split()[-1] for d in data],
    'Price %': [d['price']*100 for d in data]
}).set_index('Candidate')
st.bar_chart(df, height=300)

st.dataframe(pd.DataFrame(data))

if st.button("Refresh"):
    st.rerun()
