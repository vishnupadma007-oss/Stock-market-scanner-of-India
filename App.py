import streamlit as st
import pandas as pd
import pandas_ta as ta
import requests
import datetime
import time

# --- Configuration & Styling ---
st.set_page_config(
    page_title="Nifty 500 Scanner",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS for Mobile Optimization
st.markdown("""
    <style>
    .stButton>button {
        width: 100%;
        border-radius: 20px;
        height: 3em;
        background-color: #FF4B4B;
        color: white;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 10px;
        margin-bottom: 10px;
    }
    </style>
""", unsafe_allow_html=True)

# --- Classes (Simplified for Web App) ---

class DataFetcher:
    def __init__(self):
        # Using a public API proxy for Nifty data
        self.base_url = "http://nse-api-khaki.vercel.app:5000"

    @st.cache_data(ttl=3600) # Cache symbol list for 1 hour
    def get_nifty500_symbols(_self):
        # In a real app, fetch full list. For demo speed, we use a curated list of liquid stocks.
        return [
            "RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK", "SBIN", "TATAMOTORS", 
            "ITC", "LT", "BHARTIARTL", "ADANIENT", "AXISBANK", "KOTAKBANK", "BAJFINANCE",
            "MARUTI", "SUNPHARMA", "TITAN", "ULTRACEMCO", "WIPRO", "HCLTECH"
        ]

    def fetch_live_data(self, symbols):
        data_records = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        chunk_size = 5
        total_chunks = len(symbols) // chunk_size + 1
        
        for i in range(0, len(symbols), chunk_size):
            chunk = symbols[i:i+chunk_size]
            status_text.text(f"Fetching: {', '.join(chunk)}")
            progress_bar.progress(min((i / len(symbols)), 1.0))
            
            symbol_param = ",".join(chunk)
            url = f"{self.base_url}/api/quote?symbol={symbol_param}" 
            
            try:
                # 2-second timeout to fail fast on mobile
                response = requests.get(url, timeout=2) 
                data = response.json()
                results = data.get("data") or data.get("results") or []
                
                for item in results:
                    symbol_code = item.get("symbol") or item.get("ticker")
                    if not symbol_code: continue
                    
                    # Handle different API structures
                    d = item.get("data", item) if "data" in item else item
                    
                    try:
                        record = {
                            "symbol": symbol_code,
                            "price": float(d.get("last_price", 0)),
                            "open": float(d.get("open", 0)),
                            "day_high": float(d.get("day_high", 0)),
                            "day_low": float(d.get("day_low", 0)),
                            "prev_close": float(d.get("previous_close", 0))
                        }
                        if record["price"] > 0:
                            data_records.append(record)
                    except:
                        continue
            except:
                pass
                
        progress_bar.empty()
        status_text.empty()
        return pd.DataFrame(data_records)

class Strategy:
    def calculate_pivots(self, prev_close, prev_high, prev_low):
        range_val = prev_high - prev_low
        s3 = prev_close - (range_val * 1.1 / 4)
        s4 = prev_close - (range_val * 1.1 / 2)
        pp = (prev_high + prev_low + prev_close) / 3
        return s3, s4, pp

    def analyze(self, row):
        # 1. Logic: If Price is near S3 or S4 (Bottom Fishing)
        # Since we don't have history in this lightweight version, 
        # we approximate supports using CURRENT Day's Low/High as proxies for volatility
        
        # Approximate Pivots using TODAY's data (since we lack history in this simple view)
        # Note: In production, you'd fetch yesterday's OHLC.
        s3, s4, pp = self.calculate_pivots(row['prev_close'], row['day_high'], row['day_low'])
        
        price = row['price']
        
        # Setup Check
        signal = None
        confluence = []
        
        # Check S3 Support (within 0.5%)
        if abs(price - s3) <= (0.005 * price):
            confluence.append(f"Near S3 ({int(s3)})")
            
        # Check S4 Support (within 0.5%)
        if abs(price - s4) <= (0.005 * price):
            confluence.append(f"Near S4 ({int(s4)})")
            
        # Check if Intraday Oversold (Price < Day Low + 0.2%)
        if price <= row['day_low'] * 1.002:
            confluence.append("Day Low Test")

        # If we have at least 1 strong support factor
        if len(confluence) > 0:
            target = max(pp, row['prev_close'])
            stop_loss = s4 * 0.995 # 0.5% below S4
            
            # Risk Reward
            risk = price - stop_loss
            reward = target - price
            rr = reward / risk if risk > 0 else 0
            
            return {
                "Symbol": row['symbol'],
                "Price": row['price'],
                "Supports": ", ".join(confluence),
                "Stop Loss": round(stop_loss, 2),
                "Target": round(target, 2),
                "R:R": round(rr, 2)
            }
        return None

# --- Main App Interface ---

st.title("📱 Pocket Scanner")
st.caption("Nifty 500 Bottom Fisher")

col1, col2 = st.columns(2)
with col1:
    market_status = "CLOSED" if datetime.datetime.today().weekday() > 4 else "OPEN"
    st.info(f"Market: **{market_status}**")
with col2:
    st.info(f"Time: **{datetime.datetime.now().strftime('%H:%M')}**")

if st.button("RUN SCAN NOW", use_container_width=True):
    fetcher = DataFetcher()
    strategy = Strategy()
    
    with st.spinner("Connecting to NSE..."):
        symbols = fetcher.get_nifty500_symbols()
        df = fetcher.fetch_live_data(symbols)
    
    if df.empty:
        st.error("Could not fetch data. Market might be closed or API down.")
    else:
        results = []
        for index, row in df.iterrows():
            res = strategy.analyze(row)
            if res:
                results.append(res)
        
        if not results:
            st.warning("No stocks matched the bottom-fishing criteria right now.")
            st.write("Current Market Data Sample:", df.head())
        else:
            st.success(f"Found {len(results)} Opportunities!")
            
            for res in results:
                with st.container():
                    st.markdown(f"""
                    <div class="metric-card">
                        <h3 style="margin:0; color:#31333F">{res['Symbol']} <span style="font-size:0.6em; color:grey">₹{res['Price']}</span></h3>
                        <div style="display:flex; justify-content:space-between; margin-top:10px;">
                            <div style="color:#d62728"><b>🛑 SL:</b> {res['Stop Loss']}</div>
                            <div style="color:#2ca02c"><b>🎯 TGT:</b> {res['Target']}</div>
                        </div>
                        <div style="font-size:0.8em; color:grey; margin-top:5px;">
                            Trigger: {res['Supports']} | R:R: {res['R:R']}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

st.markdown("---")
st.markdown("##### 💡 How to use on Phone")
st.markdown("1. Deploy this code to **Streamlit Community Cloud** (Free).")
st.markdown("2. Copy the URL.")
st.markdown("3. Open Chrome/Safari on your phone and 'Add to Home Screen'.")

