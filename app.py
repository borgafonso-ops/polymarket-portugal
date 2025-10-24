import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import re

st.set_page_config(page_title="Polymarket Portugal Monitor", layout="wide")

CANDIDATES = [
    "Henrique Gouveia e Melo",
    "Luís Marques Mendes",
    "António José Seguro",
    "André Ventura"
]

def scrape_portugal_prices():
    """Scrape prices from the Portugal election page"""
    try:
        url = "https://polymarket.com/event/portugal-presidential-election"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        
        content = resp.text
        
        data = []
        
        for candidate in CANDIDATES:
            # Look for price patterns near candidate names
            # Prices appear as "51%", "21%", etc.
            candidate_lower = candidate.lower()
            
            # Find position of candidate name
            pos = content.lower().find(candidate_lower)
            
            if pos == -1:
                data.append({'name': candidate, 'price': 0.0})
                continue
            
            # Look for percentage in nearby text (within 500 chars)
            search_area = content[max(0, pos-200):min(len(content), pos+500)]
            
            # Find percentage pattern
            matches = re.findall(r'(\d+\.?\d*)%', search_area)
            
            if matches:
                # Take the first percentage found
                price = float(matches[0]) / 100
                data.append({'name': candidate, 'price': price})
            else:
                data.append({'name': candidate, 'price': 0.0})
        
        return data
        
    except Exception as e:
        st.error(f"Error scraping: {str(e)}")
        return []

# MAIN
st.title("🇵🇹 Polymarket Portugal - Presidential Election Odds")
st.caption(f"Updated: {datetime.now().strftime('%H:%M:%S')}")

with st.spinner("Fetching prices from Polymarket..."):
    data = scrape_portugal_prices()

with st.expander("Debug Info"):
    if data:
        for d in data:
            st.write(f"**{d['name']}**: {d['price']*100:.1f}%")
    else:
        st.write("No data fetched")

if not data:
    st.error("Could not fetch data")
    st.stop()

data.sort(key=lambda x: x['price'], reverse=True)

# METRICS
cols = st.columns(4)

for i, d in enumerate(data):
    with cols[i]:
        st.markdown(f"**{d['name'].split()[-1]}**")
        price_pct = d['price'] * 100
        st.metric("Implied Probability", f"{price_pct:.1f}%")

# CHART
st.subheader("Market Odds")
candidates_short = [d['name'].split()[-1] for d in data]
prices = [d['price'] * 100 for d in data]

chart_data = pd.DataFrame({
    'Candidate': candidates_short,
    'Probability %': prices
})

st.bar_chart(chart_data.set_index('Candidate'), height=350)

# TABLE
table_data = []
total = sum(d['price'] for d in data)

for d in data:
    table_data.append({
        'Candidate': d['name'],
        'Probability %': f"{d['price']*100:.1f}%",
        'Odds': f"1 in {int(1/d['price']) if d['price'] > 0 else 0}"
    })

st.dataframe(table_data, use_container_width=True)

st.caption(f"Total probability: {total*100:.1f}% (market is {'well-calibrated' if 99 < total*100 < 101 else 'not arbitrage-free'})")

if st.button("🔄 REFRESH"):
    st.rerun()
