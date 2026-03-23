# dashboard.py

import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime
import matplotlib.pyplot as plt

st.markdown("""
<style>
.block-container {
    padding-top: 1rem;
    padding-bottom: 1rem;
}
</style>
""", unsafe_allow_html=True)

st.set_page_config(
    page_title="AI Investment Agent",
    layout="centered"
)

# --- HEADER ---
st.title("🤖 AI Investment Agent")
st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

st.divider()

# Load data
try:
    history = pd.read_csv("history.csv")
except:
    history = pd.DataFrame()

try:
    portfolio = pd.read_csv("portfolio.csv")
except:
    portfolio = pd.DataFrame()

# --- Portfolio Section ---
st.subheader("💼 Portfolio")

try:
    pv = pd.read_csv("portfolio_value.csv")
    pv["date"] = pd.to_datetime(pv["date"])

    latest_value = pv.iloc[-1]["portfolio_value"]
    first_value = pv.iloc[0]["portfolio_value"]

    total_return = latest_value - first_value
    total_pct = (total_return / first_value) * 100

    col1, col2 = st.columns(2)

    col1.metric(
        "Value",
        f"${latest_value:,.0f}"
    )

    col2.metric(
        "Return",
        f"{total_pct:.2f}%",
        delta=f"${total_return:,.0f}"
    )

    st.line_chart(pv.set_index("date")["portfolio_value"])

except:
    st.info("No portfolio data yet")

# --- Portfolio Value ---

st.header("💼 Portfolio Value")

try:
    pv = pd.read_csv("portfolio_value.csv")
    pv["date"] = pd.to_datetime(pv["date"])

    latest_value = pv.iloc[-1]["portfolio_value"]
    first_value = pv.iloc[0]["portfolio_value"]

    # --- Short-term change ---
    if len(pv) > 1:
        previous_value = pv.iloc[-2]["portfolio_value"]
        change = latest_value - previous_value
        pct_change = (change / previous_value) * 100
    else:
        change = 0
        pct_change = 0

    # --- Total return since start ---
    total_return = latest_value - first_value
    total_pct = (total_return / first_value) * 100

    st.metric(
        "Total Portfolio Value",
        f"${latest_value:,.2f}",
        delta=f"{change:,.2f} ({pct_change:.2f}%)"
    )

    # 🔥 NEW: Total return display
    st.success(f"Total Return: {total_return:,.2f} ({total_pct:.2f}%)")

    # Chart
    st.line_chart(pv.set_index("date")["portfolio_value"])

except Exception as e:
    st.write("No portfolio value data yet")
    st.write(e)

# --- Trade Recommendations ---
st.divider()
st.subheader("💰 Trade Recommendations")

if not history.empty:
    latest = history.sort_values("date").drop_duplicates("symbol", keep="last")

    for _, row in latest.iterrows():
        symbol = row["symbol"]
        allocation = row["allocation"]
        score = row["score"]

        if allocation < 20:
            st.write(f"⚪ {symbol}: Skip")
        elif score < 0:
            st.warning(f"{symbol}: Cautious Buy ${allocation:.0f}")
        else:
            st.success(f"{symbol}: Buy ${allocation:.0f}")

# --- Latest Signals ---
st.divider()
st.subheader("📈 Signals")

if not history.empty:
    for _, row in latest.iterrows():
        symbol = row["symbol"]
        rsi = row["rsi"]
        trend = row["trend"]

        if rsi < 30:
            signal = "🟢 BUY"
        elif rsi > 70:
            signal = "🔴 SELL"
        else:
            signal = "🟡 HOLD"

        st.write(f"**{symbol}** — {signal} | RSI {rsi:.1f} | {trend}")
else:
    st.write("No history data")

# --- Stock Charts ---

st.divider()
st.subheader("📊 Chart")

if not history.empty:
    selected_symbol = st.selectbox(
        "Select asset",
        latest["symbol"]
    )

    ticker = yf.Ticker(selected_symbol)
    data = ticker.history(period="6mo")
    data.index = data.index.tz_localize(None)

    st.line_chart(data["Close"])
    
    # Moving averages
    data["MA20"] = data["Close"].rolling(20).mean()
    data["MA50"] = data["Close"].rolling(50).mean()

    fig, ax = plt.subplots()

    ax.plot(data.index, data["Close"], label="Price")
    ax.plot(data.index, data["MA20"], label="MA20")
    ax.plot(data.index, data["MA50"], label="MA50")

    # --- HISTORICAL SIGNALS ---
    symbol_history = history[history["symbol"] == selected_symbol]

    for _, row in symbol_history.iterrows():
        signal_date = pd.to_datetime(row["date"]).tz_localize(None)

        # Find closest date in price data
        closest_date = data.index.get_indexer([signal_date], method="nearest")

        if closest_date[0] == -1:
            continue

        price = data["Close"].iloc[closest_date[0]]
        plot_date = data.index[closest_date[0]]

        rsi = row["rsi"]

        if rsi < 30:
            color = "green"
        elif rsi > 70:
            color = "red"
        else:
            color = "orange"

        ax.scatter(plot_date, price, color=color, s=80)

    ax.legend()
    ax.set_title(f"{selected_symbol} Price + Signals")

    st.pyplot(fig)

# --- Portfolio Snapshot ---
st.header("📊 Portfolio Snapshot")

if not history.empty:
    total_value = latest["allocation"].sum()
    st.metric("Total Monthly Allocation", f"${total_value:.2f}")

# --- RSI Visualization ---
st.header("📉 RSI Overview")

if not history.empty:
    st.bar_chart(latest.set_index("symbol")["rsi"])

# --- Allocation ---
st.header("💰 Allocation Summary")

if not history.empty:
    alloc = latest[["symbol", "allocation"]].set_index("symbol")
    st.bar_chart(alloc)

# --- Performance ---
st.header("📊 Performance Tracking")

if not history.empty:
    history["date"] = pd.to_datetime(history["date"])
    performance = history.groupby("date")["price"].mean()
    st.line_chart(performance)

# --- Raw Data ---
st.header("🗂 Raw History Data")
st.dataframe(history)


