from flask import Flask, request, jsonify
import ccxt
import os
import logging
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# إعدادات
OKX_API_KEY = os.getenv("OKX_API_KEY")
OKX_API_SECRET = os.getenv("OKX_API_SECRET")
OKX_PASSPHRASE = os.getenv("OKX_PASSPHRASE")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

TRADE_AMOUNT_USDT = 800
DEFAULT_SYMBOL = "ETHUSDT"

# OKX Client
client = ccxt.okx({
    'apiKey': OKX_API_KEY,
    'secret': OKX_API_SECRET,
    'password': OKX_PASSPHRASE,
    'enableRateLimit': True,
    'sandbox': True
})

# Stats
stats = {
    "total_trades": 0,
    "successful_trades": 0,
    "total_profit": 0.0,
    "last_buy_price": 0.0
}

def send_telegram(message):
    """إرسال رسالة Telegram"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        })
        logger.info("✅ Telegram sent")
    except Exception as e:
        logger.error(f"❌ Telegram error: {e}")

@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "Bot is running ✅"}), 200

@app.route("/stats", methods=["GET"])
def get_stats():
    win_rate = 0
    if stats["total_trades"] > 0:
        win_rate = (stats["successful_trades"] / stats["total_trades"]) * 100
    return jsonify({
        "total_trades": stats["total_trades"],
        "successful_trades": stats["successful_trades"],
        "win_rate": f"{win_rate:.1f}%",
        "total_profit": f"${stats['total_profit']:.2f}"
    }), 200

@app.route("/webhook", methods=["POST"])
def webhook():
    """استقبال الإشارة من TradingView"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No data"}), 400
        
        # استخراج البيانات من TradingView (Algo Sniper v2)
        signal = data.get("signal", "").lower()  # "buy" أو "sell"
        ticker = data.get("ticker", DEFAULT_SYMBOL).upper()  # "BONKUSDT"
        
        # تحويل ticker إلى صيغة OKX (مثل BONK/USDT)
        if "/" not in ticker:
            symbol = ticker.replace("USDT", "") + "/USDT"
        else:
            symbol = ticker
        
        # اقبل buy أو sell بس
        if signal not in ["buy", "sell"]:
            logger.warning(f"❌ Invalid signal: {signal}")
            return jsonify({"error": "Invalid signal"}), 400
        
        logger.info(f"📨 Signal: {signal.upper()} | {symbol}")
        
        try:
            ticker_data = client.fetch_ticker(symbol)
            price = ticker_data['last']
            quantity = round(TRADE_AMOUNT_USDT / price, 4)
            
            logger.info(f"💰 Amount: ${TRADE_AMOUNT_USDT} | Price: ${price} | Qty: {quantity}")
            
            if signal == "buy":
                order = client.create_market_buy_order(symbol, quantity)
                stats["last_buy_price"] = price
                stats["total_trades"] += 1
                
                message = f"""
🟢 <b>صفقة شراء جديدة!</b>

💎 <b>العملة:</b> {symbol}
💵 <b>المبلغ:</b> ${TRADE_AMOUNT_USDT}
📊 <b>السعر:</b> ${price:.8f}
🔢 <b>الكمية:</b> {quantity}
🕐 <b>الوقت:</b> {datetime.now().strftime('%H:%M:%S')}

━━━━━━━━━━━━━━━━━━━━
📈 <b>الإحصائيات:</b>
📊 إجمالي الصفقات: {stats['total_trades']}
✅ صفقات ناجحة: {stats['successful_trades']}
🎯 نسبة النجاح: {(stats['successful_trades'] / stats['total_trades'] * 100 if stats['total_trades'] > 0 else 0):.1f}%
💰 إجمالي الربح: ${stats['total_profit']:.2f}
                """
                send_telegram(message)
                
                logger.info(f"✅ BUY executed")
                return jsonify({"status": "BUY ✅", "symbol": symbol, "price": price}), 200
            
            elif signal == "sell":
                order = client.create_market_sell_order(symbol, quantity)
                stats["total_trades"] += 1
                
                message = f"""
🔴 <b>صفقة بيع جديدة!</b>

💎 <b>العملة:</b> {symbol}
💵 <b>المبلغ:</b> ${TRADE_AMOUNT_USDT}
📊 <b>السعر:</b> ${price:.8f}
🔢 <b>الكمية:</b> {quantity}​​​​​​​​​​​​​​​​
