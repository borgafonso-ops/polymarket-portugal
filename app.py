import streamlit as st
import requests
import time
import pandas as pd
from datetime import datetime
import re

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

@st.cache_data(ttl=10)  # Faster refresh for live books
def robust_fetch(url):
    try:
        time.sleep(0.5)
        resp = requests.get(url, timeout=10, headers=HEADERS)
        resp.raise_for_status()
        return resp.json()
    except:
        return None

def walk_orderbook(orders, size_needed):
    """Walk orderbook to fill size_needed at average price."""
    if not orders:
        return None
    total_cost = 0.0
    filled = 0.0
    for price, size in sorted(orders):
        to_fill = min(size, size_needed - filled)
        total_cost += to_fill * price
        filled += to_fill
        if filled >= size_needed:
            return total_cost / size_needed
    return None if filled < size_needed else total_cost / size_needed

def get_orderbook_prices(token_id):
    """Get bid/ask for 100 contracts."""
    book = robust_fetch(f"{CLOB_URL}?token_id={token_id}")
    if not book:
        return None, None
    
    # Parse asks (sorted by price ASC)
    asks = []
    for ask in book.get('asks', []):
        price = float(ask.get('price', 0))
        size = float(ask.get('size', 0))
        if price > 0 and size > 0:
            asks.append((price, size))
    
    # Parse bids (sorted by price DESC)
    bids = []
    for bid in book.get('bids', []):
        price = float(bid.get('price', 0))
        size = float(bid.get('size', 0))
        if price > 0 and size > 0:
            bids.append((price, size))
    
    buy_price = walk_orderbook(asks, 100)  # Cost to BUY 100
    sell_price = walk_orderbook(bids, 100) # Proceeds from SELL 100
    
    return buy_price, sell_price

def fetch_data():
    event_data = robust_fetch(f"{GAMMA_API_EVENTS_URL}?slug=portugal-presidential-election")
    if not event_data or not isinstance(event_data, list):
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
        
        # Get YES token ID (index 0)
        token_ids = market_data.get('clobTokenIds', [])
        if not token_ids:
            continue
        yes_token = token_ids[0]
        
        # GET LIVE ORDERBOOK PRICES
        buy_price, sell_price = get_orderbook_prices(yes_token)
        
        # Fallback to last price if no liquidity
        if buy_price is None:
            buy_price = float(market_data.get('lastTradePrice') or 0)
        if sell_price is None:
            sell_price = float(market_data.get('lastTradePrice') or 0)
        
        volume = int(market_data.get('volume') or 0)
        
        candidates.append({
            'name': name,
            'buy_price': buy_price,      # Cost per share to BUY
            'sell_price': sell_price,    # Proceeds per share to SELL
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

# MAIN DASHBOARD
st.title("Polymarket Portugal - 100 Contract Basket Arb")
st.caption(f"Updated: {datetime.now().strftime('%H:%M:%S')}")

with st.spinner("Fetching LIVE orderbooks..."):
    data = fetch_data()

if not data:
    st.error("No data - check connection")
    st.stop()

# SORT & DISPLAY
data.sort(key=lambda x: x['buy_price'], reverse=True)

cols = st.columns(4)
total_buy_cost = 0
total_sell_proceeds = 0

for i, d in enumerate(data):
    with cols[i]:
        st.markdown(f"**{d['name'].split()[-1]}**")
        vol_str = f"${d['volume']:,.0f}"
        st.caption(f"{d['name'][:15]}... | {vol_str}")
        
        buy_pct = d['buy_price'] * 100
        sell_pct = d['sell_price'] * 100
        
        st.metric("Buy (Ask)", f"{buy_pct:.1f}%")
        st.metric("Sell (Bid)", f"{sell_pct:.1f}%")
        
        total_buy_cost += d['buy_price']
        total_sell_proceeds += d['sell_price']

# BASKET TOTALS
st.divider()
col1, col2, col3 = st.columns(3)
with col1:
    buy_total_pct = total_buy_cost * 100
    st.metric("TOTAL BUY COST", f"{buy_total_pct:.1f}%", 
              delta=f"{buy_total_pct-100:+.1f}% vs 100%")
with col2:
    sell_total_pct = total_sell_proceeds * 100
    st.metric("TOTAL SELL PROCEEDS", f"{sell_total_pct:.1f}%", 
              delta=f"{sell_total_pct-100:+.1f}% vs 100%")
with col3:
    spread = (total_buy_cost - total_sell_proceeds) * 100
    st.metric("SPREAD", f"{spread:.1f}%")

# ARBITRAGE ALERTS
st.subheader("ARBITRAGE OPPORTUNITIES")
if buy_total_pct < 100:
    profit = 100 - buy_total_pct
    st.success(f"🟢 **BUY BASKET ARB**: Buy all 4 for {buy_total_pct:.1f}¢ → **{profit:.1f}% PROFIT**")
elif sell_total_pct > 100:
    profit = sell_total_pct - 100
    st.success(f"🔴 **SELL BASKET ARB**: Sell all 4 for {sell_total_pct:.1f}¢ → **{profit:.1f}% PROFIT**")
else:
    st.info("⚖️ No arb - market balanced")

# CHART
st.subheader("100-Contract Prices")
chart_data = pd.DataFrame({
    'Candidate': [d['name'].split()[-1] for d in data],
    'Buy (Ask)': [d['buy_price']*100 for d in data],
    'Sell (Bid)': [d['sell_price']*100 for d in data]
}).set_index('Candidate')
st.bar_chart(chart_data, height=350)

# DETAILED TABLE
st.subheader("Orderbook Details (100 Contracts)")
table_data = []
for d in data:
    table_data.append({
        'Candidate': d['name'],
        'Buy Cost %': f"{d['buy_price']*100:.2f}",
        'Sell Proceeds %': f"{d['sell_price']*100:.2f}",
        'Spread %': f"{(d['buy_price']-d['sell_price'])*100:.2f}",
        'Volume $': f"${d['volume']:,.0f}"
    })
st.dataframe(table_data, use_container_width=True)

# REFRESH
if st.button("🔄 REFRESH LIVE ORDERBOOKS"):
    st.cache_data.clear()
    st.rerun()
