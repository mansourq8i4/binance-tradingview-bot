from flask import Flask, request, jsonify
import ccxt
import os
import logging
import requests
from datetime import datetime
from dotenv import load_dotenv

# تحميل المتغيرات البيئية
load_dotenv()

# إعدادات السجل
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==================== الإعدادات ====================
# OKX
OKX_API_KEY = os.getenv("OKX_API_KEY")
OKX_API_SECRET = os.getenv("OKX_API_SECRET")
OKX_PASSPHRASE = os.getenv("OKX_PASSPHRASE")

# Telegram
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Trading
SYMBOL = "ETH/USDT"  # العملة الافتراضية
TRADE_AMOUNT_USDT = 800  # المبلغ بالـ USDT
SECRET_TOKEN = os.getenv("WEBHOOK_SECRET")

# ==================== إعدادات OKX ====================
exchange = ccxt.okx({
    'apiKey': OKX_API_KEY,
    'secret': OKX_API_SECRET,
    'password': OKX_PASSPHRASE,
    'enableRateLimit': True,
    'sandbox': True  # ✅ Demo Trading
})

# ==================== إحصائيات التداول ====================
stats = {
    "total_trades": 0,
    "successful_trades": 0,
    "total_profit": 0.0,
    "last_buy_price": 0.0,
    "trades_history": []
}

# ==================== دالة إرسال Telegram ====================
def send_telegram(message):
    """إرسال رسالة Telegram"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        })
        logger.info("✅ تم إرسال رسالة Telegram")
    except Exception as e:
        logger.error(f"❌ خطأ في إرسال Telegram: {e}")

# ==================== حساب الربح/الخسارة ====================
def calculate_profit(action, price, quantity):
    """حساب الربح والخسارة"""
    profit = 0.0
    if action == "sell" and stats["last_buy_price"] > 0:
        profit = (price - stats["last_buy_price"]) * quantity
        stats["total_profit"] += profit
        if profit > 0:
            stats["successful_trades"] += 1
    return profit

# ==================== دالة التنفيذ ====================
def execute_trade(action, symbol, quantity, price):
    """تنفيذ الصفقة على OKX"""
    try:
        if action == "buy":
            order = exchange.create_market_buy_order(symbol, quantity)
            stats["last_buy_price"] = price
            stats["total_trades"] += 1
            
            logger.info(f"✅ BUY executed: {order}")
            return {
                "status": "BUY executed ✅",
                "quantity": quantity,
                "price": price,
                "order": order
            }
            
        elif action == "sell":
            order = exchange.create_market_sell_order(symbol, quantity)
            profit = calculate_profit("sell", price, quantity)
            stats["total_trades"] += 1
            
            logger.info(f"✅ SELL executed: {order}")
            return {
                "status": "SELL executed ✅",
                "quantity": quantity,
                "price": price,
                "profit": profit,
                "order": order
            }
        else:
            return {"error": "Invalid action"}
            
    except Exception as e:
        error_msg = str(e)
        logger.error(f"❌ OKX error: {error_msg}")
        send_telegram(f"❌ <b>خطأ في التداول</b>\n\n{error_msg}")
        return {"error": error_msg}

# ==================== Routes ====================

@app.route("/", methods=["GET"])
def home():
    """فحص البوت"""
    return jsonify({"status": "Bot is running ✅"}), 200

@app.route("/stats", methods=["GET"])
def get_stats():
    """عرض الإحصائيات"""
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
        # التحقق من الـ Token
        data = request.get_json()
        
        if not data or data.get("token") != SECRET_TOKEN:
            logger.warning("❌ Unauthorized request")
            return jsonify({"error": "Unauthorized"}), 401
        
        # استخراج البيانات
        action = data.get("action", "").lower()  # buy أو sell
        symbol = data.get("symbol", SYMBOL)
        
        if action not in ["buy", "sell"]:
            return jsonify({"error": "Invalid action"}), 400
        
        logger.info(f"📨 Signal: {action} | Symbol: {symbol}")
        
        try:
            # الحصول على السعر الحالي
            ticker = exchange.fetch_ticker(symbol)
            price = ticker['last']
            
            # حساب الكمية
            quantity = round(TRADE_AMOUNT_USDT / price, 4)
            
            logger.info(f"💰 Amount: ${TRADE_AMOUNT_USDT} | Price: {price} | Qty: {quantity}")
            
            # تنفيذ الصفقة
            result = execute_trade(action, symbol, quantity, price)
            
            # حساب نسبة النجاح
            win_rate = 0
            if stats["total_trades"] > 0:
                win_rate = (stats["successful_trades"] / stats["total_trades"]) * 100
            
            profit_emoji = "🟢" if result.get("profit", 0) >= 0 else "🔴"
            
            # بناء الرسالة
            if action == "buy":
                message = f"""
🟢 <b>صفقة شراء جديدة!</b>

💎 <b>العملة:</b> {symbol}
💵 <b>المبلغ:</b> ${TRADE_AMOUNT_USDT}
📊 <b>السعر:</b> ${price:.2f}
🔢 <b>الكمية:</b> {quantity}
🕐 <b>الوقت:</b> {datetime.now().strftime('%H:%M:%S')}

━━━━━━━━━━━━━━━━━━━━
📈 <b>الإحصائيات:</b>
📊 إجمالي الصفقات: {stats['total_trades']}
✅ صفقات ناجحة: {stats['successful_trades']}
🎯 نسبة النجاح: {win_rate:.1f}%
💰 إجمالي الربح: ${stats['total_profit']:.2f}
                """
            else:  # sell
                profit = result.get("profit", 0)
                message = f"""
🔴 <b>صفقة بيع جديدة!</b>

💎 <b>العملة:</b> {symbol}
💵 <b>المبلغ:</b> ${TRADE_AMOUNT_USDT}
📊 <b>السعر:</b> ${price:.2f}
🔢 <b>الكمية:</b> {quantity}
🕐 <b>الوقت:</b> {datetime.now().strftime('%H:%M:%S')}

━━━━━━━━━━━━━━━━━━━━
📈 <b>الإحصائيات:</b>
📊 إجمالي الصفقات: {stats['total_trades']}
✅ صفقات ناجحة: {stats['successful_trades']}
🎯 نسبة النجاح: {win_rate:.1f}%
{profit_emoji} <b>الربح/الخسارة:</b> ${profit:.2f}
💰 <b>إجمالي الربح:</b> ${stats['total_profit']:.2f}
                """
            
            # إرسال الرسالة
            send_telegram(message)
            
            return jsonify({
                "status": result.get("status", "executed"),
                "quantity": quantity,
                "price": price,
                "profit": result.get("profit", 0)
            }), 200
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ Exchange error: {error_msg}")
            send_telegram(f"❌ <b>خطأ في الاتصال</b>\n\n{error_msg}")
            return jsonify({"error": error_msg}), 500
    
    except Exception as e:
        logger.error(f"❌ Webhook error: {e}")
        return jsonify({"error": str(e)}), 500

# ==================== تشغيل البوت ====================
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
