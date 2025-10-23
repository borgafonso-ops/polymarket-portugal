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

@st.cache_data(ttl=10)
def robust_fetch(url):
    try:
        time.sleep(0.5)
        resp = requests.get(url, timeout=10, headers=HEADERS)
        resp.raise_for_status()
        return resp.json()
    except:
        return None

def walk_orderbook(orders, size_needed, is_ask=True):
    if not orders:
        return 0.0
    total_cost = 0.0
    filled = 0.0
    if is_ask:
        sorted_orders = sorted(orders)  # ASC for asks
    else:
        sorted_orders = sorted(orders, reverse=True)  # DESC for bids
    for price, size in sorted_orders:
        to_fill = min(size, size_needed - filled)
        total_cost += to_fill * price
        filled += to_fill
        if filled >= size_needed:
            return total_cost / size_needed
    return 0.0

def get_orderbook_prices(token_id):
    book = robust_fetch(f"{CLOB_URL}?token_id={token_id}")
    if not book or not book.get('asks') or not book.get('bids'):
        return 0.0, 0.0
    
    asks = [(float(ask['price']), float(ask['size'])) for ask in book.get('asks', []) if ask.get('price')]
    bids = [(float(bid['price']), float(bid['size'])) for bid in book.get('bids', []) if bid.get('price')]
    
    buy_price = walk_orderbook(asks, 100, is_ask=True)
    sell_price = walk_orderbook(bids, 100, is_ask=False)
    
    return buy_price, sell_price

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

def fetch_data(debug=False):
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
        
        # PRIORITIZE CLOB IF DEPTH >0
        if buy_price > 0 and sell_price > 0:
            source = "CLOB (Live)"
        else:
            # FALLBACK: Midpoint from lastPrice + ESTIMATED SPREAD (your 50/52 example → ±0.5%)
            midpoint = safe_float(market_data.get('lastPrice') or market_data.get('lastTradePrice'))
            spread_half = 0.005  # 0.5% half-spread (adjustable)
            buy_price = midpoint + spread_half
            sell_price = midpoint - spread_half
            source = "Est. Spread (Site Midpoint)"
            if debug:
                st.info(f"{name}: CLOB empty → Est. {midpoint*100:.1f}% ±0.5% = Buy {buy_price*100:.1f}% / Sell {sell_price*100:.1f}%")
        
        candidates.append({
            'name': name,
            'buy_price': buy_price,
            'sell_price': sell_price,
            'volume': volume,
            'yes_token': yes_token,
            'source': source
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

debug = st.checkbox("Debug: Show CLOB Fallbacks & Token IDs", value=False)

with st.spinner("Fetching LIVE orderbooks..."):
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
        st.caption(f"{d['name'][:15]}... | ${d['volume']:,.0f} | {d['source']}")
        
        buy_pct = d['buy_price'] * 100
        sell_pct = d['sell_price'] * 100
        spread_pct = buy_pct - sell_pct
        
        st.metric("Buy", f"{buy_pct:.1f}%")
        st.metric("Sell", f"{sell_pct:.1f}%")
        st.caption(f"Spread: {spread_pct:.1f}%")
        
        total_buy_cost += d['price']
        total_sell_proceeds += d['sell_price']

# BASKET
st.divider()
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("TOTAL BUY", f"{total_buy_cost*100:.1f}%", f"{total_buy_cost*100-100:+.1f}%")
with col2:
    st.metric("TOTAL SELL", f"{total_sell_proceeds*100:.1f}%", f"{total_sell_proceeds*100-100:+.1f}%")
with col3:
    st.metric("TOTAL SPREAD", f"{(total_buy_cost-total_sell_proceeds)*100:.1f}%")

# ARB ALERTS
st.subheader("ARBITRAGE")
if total_buy_cost < 1:
    profit = 100 - total_buy_cost * 100
    st.success(f"🟢 **BUY BASKET**: ${total_buy_cost*100:.1f} → **{profit:.1f}% PROFIT**")
elif total_sell_proceeds > 1:
    profit = total_sell_proceeds * 100 - 100
    st.success(f"🔴 **SELL BASKET**: ${total_sell_proceeds*100:.1f} → **{profit:.1f}% PROFIT**")
else:
    st.info("⚖️ No Arb Opportunity (balanced ~100%)")

# CHART - SIDE-BY-SIDE
st.subheader("100-Contract Spreads")
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

# DETAILED TABLE
st.subheader("Orderbook Details")
table_data = []
for d in data:
    table_data.append({
        'Candidate': d['name'],
        'Source': d['source'],
        'Buy %': f"{d['buy_price']*100:.2f}",
        'Sell %': f"{d['sell_price']*100:.2f}",
        'Spread %': f"{(d['buy_price']-d['sell_price'])*100:.2f}",
        'Volume $': f"${d['volume']:,.0f}"
    })
st.dataframe(table_data)

if st.button("🔄 REFRESH LIVE"):
    st.rerun()
