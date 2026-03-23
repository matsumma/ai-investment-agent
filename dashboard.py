# dashboard.py

import streamlit as st
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt

st.set_page_config(page_title="AI Investment Agent", layout="wide")

st.title("📊 AI Investment Agent Dashboard")

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
st.header("📁 Portfolio")

if not portfolio.empty:
    st.dataframe(portfolio)
else:
    st.write("No portfolio data")

# --- Portfolio Value ---

st.header("💼 Portfolio Value")

try:
    pv = pd.read_csv("portfolio_value.csv")
    pv["date"] = pd.to_datetime(pv["date"])

    latest_value = pv.iloc[-1]["portfolio_value"]

    # Calculate change
    if len(pv) > 1:
        previous_value = pv.iloc[-2]["portfolio_value"]

        change = latest_value - previous_value
        pct_change = (change / previous_value) * 100

        st.metric(
            "Total Portfolio Value",
            f"${latest_value:,.2f}",
            delta=f"{change:,.2f} ({pct_change:.2f}%)"
        )
    else:
        st.metric("Total Portfolio Value", f"${latest_value:,.2f}")

    # Chart
    st.line_chart(pv.set_index("date")["portfolio_value"])

except Exception as e:
    st.write("No portfolio value data yet")
    st.write(e)

# --- Latest Signals ---
st.header("📈 Latest Signals")

if not history.empty:
    latest = history.sort_values("date").drop_duplicates("symbol", keep="last")

    for _, row in latest.iterrows():
        symbol = row["symbol"]
        rsi = row["rsi"]
        trend = row["trend"]
        score = row["score"]

        if rsi < 30:
            signal = "🟢 BUY"
        elif rsi > 70:
            signal = "🔴 SELL"
        else:
            signal = "🟡 HOLD"

        st.metric(
            label=symbol,
            value=signal,
            delta=f"RSI: {rsi:.2f} | Trend: {trend} | Score: {score}"
        )
else:
    st.write("No history data")

# --- Stock Charts ---

st.header("📈 Stock Charts with Signals")

if not history.empty:
    latest = history.sort_values("date").drop_duplicates("symbol", keep="last")

    selected_symbol = st.selectbox(
        "Select a stock:",
        latest["symbol"]
    )

    ticker = yf.Ticker(selected_symbol)
    data = ticker.history(period="6mo")
    data.index = data.index.tz_localize(None)
    
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

st.header("💰 Trade Recommendations")

if not history.empty:
    latest = history.sort_values("date").drop_duplicates("symbol", keep="last")

    for _, row in latest.iterrows():
        symbol = row["symbol"]
        allocation = row["allocation"]
        score = row["score"]

        if allocation < 20:
            action = "SKIP"
        elif score < 0:
            action = f"⚠️ Cautious Buy ${allocation:.2f}"
        else:
            action = f"✅ Buy ${allocation:.2f}"

        if score < 0:
            st.warning(f"{symbol}: Buy ${allocation:.2f}")
        else:
            st.success(f"{symbol}: Buy ${allocation:.2f}")
