import os
import pandas as pd
from dotenv import load_dotenv
import yfinance as yf
from openai import OpenAI
import ta
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
import requests
import re

def parse_allocation(text):
    allocations = {}
    lines = text.split("\n")

    for line in lines:
        match = re.match(r"- (\w+): \$?([\d\.]+)", line)
        if match:
            symbol = match.group(1)
            amount = float(match.group(2))
            allocations[symbol] = amount

    return allocations

def send_email_alert(subject, body):
    sender = os.getenv("EMAIL_USER")
    password = os.getenv("EMAIL_PASS")
    receiver = sender  # send to yourself

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = receiver

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, password)
            server.send_message(msg)
        print("📧 Alert sent!")
    except Exception as e:
        print("Email error:", e)

def send_telegram_alert(message):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    url = f"https://api.telegram.org/bot{token}/sendMessage"

    payload = {
        "chat_id": chat_id,
        "text": message
    }

    try:
        response = requests.post(url, data=payload)
        if response.status_code == 200:
            print("📲 Telegram alert sent!")
        else:
            print("Telegram error:", response.text)
    except Exception as e:
        print("Telegram exception:", e)

try:
    signal_df = pd.read_csv("signals.csv")
except FileNotFoundError:
    signal_df = pd.DataFrame(columns=["symbol", "last_signal"])

# Load env
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

portfolio = pd.read_csv("portfolio.csv")

monthly_budget = 500  # 👈 change anytime

today = datetime.now().strftime("%Y-%m-%d")
history_rows = []

print("\n=== Portfolio Analysis + Allocation ===\n")

allocations = []
alerts = []
new_signals = []

for index, row in portfolio.iterrows():
    symbol = row["symbol"]

    ticker = yf.Ticker(symbol)
    data = ticker.history(period="3mo")

    # Indicators
    data["RSI"] = ta.momentum.RSIIndicator(data["Close"]).rsi()
    data["MA_20"] = data["Close"].rolling(window=20).mean()
    data["MA_50"] = data["Close"].rolling(window=50).mean()

    rsi = data["RSI"].iloc[-1]
    ma20 = data["MA_20"].iloc[-1]
    ma50 = data["MA_50"].iloc[-1]

    # === SIGNAL TYPE (NEW) ===
    if rsi < 30:
        current_signal = "BUY"
    elif rsi > 70:
        current_signal = "SELL"
    else:
        current_signal = "HOLD"

    # === PREVIOUS SIGNAL CHECK (NEW) ===
    prev = signal_df[signal_df["symbol"] == symbol]

    if not prev.empty:
        last_signal = prev["last_signal"].values[0]
    else:
        last_signal = None

    # Only alert if signal changed
    if current_signal != last_signal:
        alerts.append(f"{symbol}: {current_signal} signal (RSI {rsi:.2f})")

    # Store for saving later
    new_signals.append({
        "symbol": symbol,
        "last_signal": current_signal
    })

    # === EXISTING SCORING (UNCHANGED) ===
    score = 0

    if rsi < 30:
        score += 2
    elif rsi > 70:
        score -= 2

    if ma20 > ma50:
        score += 1
    else:
        score -= 1

    allocations.append((symbol, score))

# Normalize scores
total_score = sum(max(s, 0) for _, s in allocations)

print("=== Suggested Allocation ===\n")

for symbol, score in allocations:

    # Smarter weighting system
    if score >= 2:
        weight = 3
    elif score == 1:
        weight = 2
    elif score == 0:
        weight = 1
    else:
        weight = 0.5

    if total_score > 0:
        allocation = (weight / total_score) * monthly_budget
    else:
        allocation = monthly_budget / len(allocations)

    print(f"{symbol}: ${allocation:.2f}")

    # Re-fetch data for logging (simple approach)
    ticker = yf.Ticker(symbol)
    data = ticker.history(period="3mo")

    data["RSI"] = ta.momentum.RSIIndicator(data["Close"]).rsi()
    data["MA_20"] = data["Close"].rolling(window=20).mean()
    data["MA_50"] = data["Close"].rolling(window=50).mean()

    latest_price = data["Close"].iloc[-1]
    rsi = data["RSI"].iloc[-1]
    trend_signal = "BULLISH" if data["MA_20"].iloc[-1] > data["MA_50"].iloc[-1] else "BEARISH"

    # Save to memory
    history_rows.append({
        "date": today,
        "symbol": symbol,
        "price": round(latest_price, 2),
        "rsi": round(rsi, 2),
        "trend": trend_signal,
        "allocation": round(allocation, 2),
        "score": score,                     # ✅ numeric
        "recommendation": trend_signal      # optional label
    })
# AI refinement
prompt = f"""
You are a disciplined portfolio manager.

You may ONLY allocate capital among these assets:
{[symbol for symbol, _ in allocations]}

Rules:
- Do NOT introduce new assets
- Favor assets with higher scores
- Avoid allocating to strongly negative signals
- Maintain diversification

Suggested signal scores:
{allocations}

Monthly budget: ${monthly_budget}

Return:
1. Final allocation (dollar amounts per asset)
2. Brief reasoning
"""
response = client.chat.completions.create(
    model="gpt-5-mini",
    messages=[{"role": "user", "content": prompt}]
)

print("\n=== AI Allocation Strategy ===\n")
analysis = response.choices[0].message.content
print(analysis)

target_allocations = parse_allocation(analysis)

print("\n=== Trade Recommendations (Monthly Allocation) ===\n")

for symbol, target_value in target_allocations.items():
    if target_value < 20:
        action = "SKIP"
    else:
        action = f"BUY ${target_value:.2f}"

    print(f"{symbol}: {action}")

# Save to history.csv
history_df = pd.DataFrame(history_rows)

try:
    existing = pd.read_csv("history.csv")
    history_df = pd.concat([existing, history_df], ignore_index=True)
except FileNotFoundError:
    pass

history_df.to_csv("history.csv", index=False)

print("\n✅ History saved to history.csv")

print("\n=== Performance Check ===\n")

history = pd.read_csv("history.csv")

# Keep only latest entry per symbol
history = history.sort_values("date").drop_duplicates(subset=["symbol"], keep="last")

for index, row in history.iterrows():
    symbol = row["symbol"]
    old_price = row["price"]

    ticker = yf.Ticker(symbol)
    current_price = ticker.history(period="1d")["Close"].iloc[-1]

    change_pct = ((current_price - old_price) / old_price) * 100

    print(f"{symbol}: Then ${old_price} → Now ${current_price:.2f} ({change_pct:.2f}%)")

print("\n=== Strategy Evaluation ===\n")

history = pd.read_csv("history.csv")

results = []

for index, row in history.iterrows():
    symbol = row["symbol"]
    old_price = row["price"]

    ticker = yf.Ticker(symbol)
    current_price = ticker.history(period="1d")["Close"].iloc[-1]

    return_pct = ((current_price - old_price) / old_price) * 100

    results.append({
        "symbol": symbol,
        "score": row["score"],  # currently "score=-1"
        "trend": row["trend"],
        "return_pct": return_pct
    })

results_df = pd.DataFrame(results)

# Clean score field
#results_df["score"] = results_df["score"].str.replace("score=", "").astype(int)

# Group by score
score_performance = results_df.groupby("score")["return_pct"].mean()

print("Average Return by Score:\n")
print(score_performance)

# Group by trend
trend_performance = results_df.groupby("trend")["return_pct"].mean()

print("\nAverage Return by Trend:\n")
print(trend_performance)

new_signal_df = pd.DataFrame(new_signals)
new_signal_df.to_csv("signals.csv", index=False)

if alerts:
    # email alert
    # subject = "🚨 AI Investment Alerts"
    # body = "\n".join(alerts)
    # send_email_alert(subject, body)
    # telegram alert (enabled)
    message = "🚨 AI Investment Alerts\n\n" + "\n".join(alerts)
    send_telegram_alert(message)
else:
    print("No alerts today.")


