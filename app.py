import streamlit as st
import pandas as pd
from datetime import datetime
import re
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import Orderbook
import json

st.set_page_config(page_title="Polymarket Portugal Monitor", layout="wide")

# SDK Setup (public, no key needed for read)
client = ClobClient(host="https://clob.polymarket.com", key="", chain_id=137)

TARGET_CANDIDATES = {
    "Henrique Gouveia e Melo",
    "Luís Marques Mendes", 
    "António José Seguro",
    "André Ventura"
}

def safe_float(value):
    try:
        return float(value or 0)
    except:
        return 0.0

def safe_int(value):
    try:
        return int(float(value or 0))
    except:
        return 0

def walk_orderbook_orders(orders, size_needed, is_ask=True):
    if not orders:
        return 0.0
    total_cost = 0.0
    filled = 0.0
    if is_ask:
        sorted_orders = sorted(orders, key=lambda x: x.price)  # ASC for asks
    else:
        sorted_orders = sorted(orders, key=lambda x: x.price, reverse=True)  # DESC for bids
    for order in sorted_orders:
        to_fill = min(float(order.size), size_needed - filled)
        total_cost += to_fill * float(order.price)
        filled += to_fill
        if filled >= size_needed:
            return total_cost / size_needed
    return 0.0

def get_orderbook_prices(token_id):
    try:
        orderbook = client.get_orderbook(token_id)
        if not orderbook:
            return 0.0, 0.0
        buy_price = walk_orderbook_orders(orderbook.asks, 100, is_ask=True)
        sell_price = walk_orderbook_orders(orderbook.bids, 100, is_ask=False)
        return buy_price, sell_price
    except:
        return 0.0, 0.0

def fetch_data(debug=False):
    event_data = requests.get(f"https://gamma-api.polymarket.com/events?slug=portugal-presidential-election").json()
    if not event_data or not isinstance(event_data, list) or not event_data[0]:
        return []
    
    event = event_data[0]
    markets = event.get('markets', [])
    
    candidates = []
    for market in markets:
        market_id = market.get('id')
        if not market_id:
            continue
            
        market_data = requests.get(f"https://gamma-api.polymarket.com/markets/{market_id}").json()
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
        
        buy_price, sell_price = get_orderbook_prices(yes_token)
        
        if buy_price > 0 and sell_price > 0:
            source = "SDK Orderbook (Real)"
            if debug:
                st.success(f"{name}: Real prices - Buy {buy_price*100:.2f}% | Sell {sell_price*100:.2f}%")
        else:
            midpoint = safe_float(market_data.get('lastPrice') or market_data.get('lastTradePrice'))
            buy_price = sell_price = midpoint
            source = "Midpoint (No Book Depth)"
            if debug:
                st.warning(f"{name}: SDK no depth - Using midpoint {midpoint*100:.2f}%")
        
        candidates.append({
            'name': name,
            'buy_price': buy_price,
            'sell_price': sell_price,
            'volume': volume,
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

debug = st.checkbox("Debug: Show SDK Logs", value=False)

with st.spinner("Fetching live orderbooks via SDK..."):
    data = fetch_data(debug=debug)

if not data:
    st.error("No data - check API")
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
    st.metric("TOTAL SPREAD", f"{(total_buy_cost-total_sell_proceeds)*100:.1f}%")

# ARB
st.subheader("ARBITRAGE")
if total_buy_cost < 1:
    profit = 100 - total_buy_cost * 100
    st.success(f"🟢 **BUY BASKET**: ${total_buy_cost*100:.1f} → **{profit:.1f}% PROFIT**")
elif total_sell_proceeds > 1:
    profit = total_sell_proceeds * 100 - 100
    st.success(f"🔴 **SELL BASKET**: ${total_sell_proceeds*100:.1f} → **{profit:.1f}% PROFIT**")
else:
    st.info("⚖️ No Arb (balanced ~100%) - Monitor for deviations")

# CHART
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

# TABLE
st.subheader("Details")
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

if st.button("🔄 REFRESH"):
    st.rerun()
