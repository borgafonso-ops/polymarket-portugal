import streamlit as st
import requests
import time
import pandas as pd
from datetime import datetime
import re
import plotly.graph_objects as go  # For bulletproof chart

st.set_page_config(page_title="Polymarket Portugal Monitor", layout="wide")

GAMMA_API_EVENTS_URL = "https://gamma-api.polymarket.com/events"
GAMMA_API_MARKET_URL = "https://gamma-api.polymarket.com/markets/"
CLOB_URL = "https://clob.polymarket.com/orderbook"
HEADERS = {'User-Agent': 'PolymarketStreamlitMonitor/2.0'}

TARGET_CANDIDATES = {
    "Henrique Gouveia e Melo",
    "Luís Marques Mendes", 
    "António José Seguro",
    "André Ventura"
}

@st.cache_data(ttl=10)
def robust_fetch(url):
    try:
        time.sleep(0.5)
        resp = requests.get(url, timeout=10, headers=HEADERS)
        resp.raise_for_status()
        return resp.json()
    except:
        return None

def walk_orderbook(orders, size_needed):
    if not orders:
        return 0.0
    total_cost = 0.0
    filled = 0.0
    for price, size in sorted(orders):
        to_fill = min(size, size_needed - filled)
        total_cost += to_fill * price
        filled += to_fill
        if filled >= size_needed:
            return total_cost / size_needed
    return 0.0

def get_orderbook_prices(token_id):
    book = robust_fetch(f"{CLOB_URL}?token_id={token_id}")
    if not book:
        return 0.0, 0.0
    
    asks = [(float(ask['price']), float(ask['size'])) for ask in book.get('asks', []) if ask.get('price')]
    bids = [(float(bid['price']), float(bid['size'])) for bid in book.get('bids', []) if bid.get('price')]
    
    return walk_orderbook(asks, 100), walk_orderbook(bids, 100)

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

def fetch_data():
    event_data = robust_fetch(f"{GAMMA_API_EVENTS_URL}?slug=portugal-presidential-election")
    if not event_data or not isinstance(event_data, list) or not event_data[0]:
        return []
    
    event = event_data[0]
    markets = event.get('markets', [])
    
    candidates = []
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
        token_ids = market_data.get('clobTokenIds', [])
        if not token_ids:
            continue
        yes_token = token_ids[0]
        
        buy_price, sell_price = get_orderbook_prices(yes_token)
        
        if buy_price == 0:
            buy_price = safe_float(market_data.get('lastTradePrice') or market_data.get('lastPrice'))
        if sell_price == 0:
            sell_price = safe_float(market_data.get('lastTradePrice') or market_data.get('lastPrice'))
        
        candidates.append({
            'name': name,
            'buy_price': buy_price,
            'sell_price': sell_price,
            'volume': volume,
            'yes_token': yes_token
        })
        
        if len(candidates) == 4:
            break
    
    return candidates

def extract_candidate_name(question):
    if not question:
        return None
    match = re.search(r'Will (.*?) win', question)
    return match.group(1).strip() if match else None

# MAIN
st.title("Polymarket Portugal - 100 Contract Basket Arb")
st.caption(f"Updated: {datetime.now().strftime('%H:%M:%S')}")

with st.spinner("Fetching LIVE orderbooks..."):
    data = fetch_data()

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
        
        st.metric("Buy", f"{d['buy_price']*100:.1f}%")
        st.metric("Sell", f"{d['sell_price']*100:.1f}%")
        
        total_buy_cost += d['buy_price']
        total_sell_proceeds += d['sell_price']

# BASKET
st.divider()
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("TOTAL BUY", f"{total_buy_cost*100:.1f}%", f"{total_buy_cost*100-100:+.1f}%")
with col2:
    st.metric("TOTAL SELL", f"{total_sell_proceeds*100:.1f}%", f"{total_sell_proceeds*100-100:+.1f}%")
with col3:
    st.metric("SPREAD", f"{(total_buy_cost-total_sell_proceeds)*100:.1f}%")

# ARB
st.subheader("ARBITRAGE")
if total_buy_cost < 1:
    st.success(f"BUY ARB: {100-total_buy_cost*100:.1f}% PROFIT")
elif total_sell_proceeds > 1:
    st.success(f"SELL ARB: {total_sell_proceeds*100-100:.1f}% PROFIT")
else:
    st.info("No Arb")

# FIXED CHART - PLOTLY SIDE-BY-SIDE BARS (NO STACKING!)
st.subheader("100-Contract Bid/Ask Spreads")
candidates_short = [d['name'].split()[-1] for d in data]
buy_values = [d['buy_price']*100 for d in data]
sell_values = [d['sell_price']*100 for d in data]

fig = go.Figure(data=[
    go.Bar(name='Buy (Ask)', x=candidates_short, y=buy_values, marker_color='red', opacity=0.7),
    go.Bar(name='Sell (Bid)', x=candidates_short, y=sell_values, marker_color='green', opacity=0.7)
])

fig.update_layout(
    barmode='group',  # SIDE-BY-SIDE (not 'stack'!)
    title="Buy vs Sell Prices (Red=Cost to Buy, Green=Proceeds to Sell)",
    xaxis_title="Candidate",
    yaxis_title="Price (%)",
    height=350
)
st.plotly_chart(fig, use_container_width=True)

# TABLE
table_data = []
for d in data:
    table_data.append({
        'Candidate': d['name'],
        'Buy %': f"{d['buy_price']*100:.2f}",
        'Sell %': f"{d['sell_price']*100:.2f}",
        'Spread %': f"{(d['price']-d['sell_price'])*100:.2f}",
        'Volume': f"${d['volume']:,.0f}"
    })
st.dataframe(table_data)

if st.button("Refresh"):
    st.rerun()
