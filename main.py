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
SYMBOL = "ETHUSDT"

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
        
        # اقبل أي بيانات
        if not data:
            return jsonify({"error": "No data"}), 400
        
        action = data.get("action", "").lower()
        symbol = data.get("symbol", SYMBOL)
        
        # اقبل buy أو sell بدون تحقق آخر
        if action not in ["buy", "sell"]:
            return jsonify({"error": "Invalid action"}), 400
        
        logger.info(f"📨 Signal: {action.upper()} | {symbol}")
        
        try:
            ticker = client.fetch_ticker(symbol)
            price = ticker['last']
            quantity = round(TRADE_AMOUNT_USDT / price, 4)
            
            if action == "buy":
                order = client.create_market_buy_order(symbol, quantity)
                stats["last_buy_price"] = price
                stats["total_trades"] += 1
                
                message = f"""
🟢 <b>صفقة شراء!</b>

💎 {symbol}
💵 ${TRADE_AMOUNT_USDT}
📊 ${price:.2f}
🔢 {quantity}
🕐 {datetime.now().strftime('%H:%M:%S')}

📊 الصفقات: {stats['total_trades']}
✅ الناجحة: {stats['successful_trades']}
💰 الربح: ${stats['total_profit']:.2f}
                """
                send_telegram(message)
                
                return jsonify({"status": "BUY ✅", "price": price}), 200
            
            elif action == "sell":
                order = client.create_market_sell_order(symbol, quantity)
                stats["total_trades"] += 1
                
                message = f"""
🔴 <b>صفقة بيع!</b>

💎 {symbol}
💵 ${TRADE_AMOUNT_USDT}
📊 ${price:.2f}
🔢 {quantity}
🕐 {datetime.now().strftime('%H:%M:%S')}

📊 الصفقات: {stats['total_trades']}
✅ الناجحة: {stats['successful_trades']}
💰 الربح: ${stats['total_profit']:.2f}
                """
                send_telegram(message)
                
                return jsonify({"status": "SELL ✅", "price": price}), 200
        
        except Exception as e:
            logger.error(f"❌ Error: {e}")
            send_telegram(f"❌ خطأ: {str(e)}")
            return jsonify({"error": str(e)}), 500
    
    except Exception as e:
        logger.error(f"❌ Webhook error: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    logger.info(f"🚀 Bot started on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
