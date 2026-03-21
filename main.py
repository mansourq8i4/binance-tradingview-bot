from flask import Flask, request, jsonify
from binance.client import Client
from binance.exceptions import BinanceAPIException
from dotenv import load_dotenv
import os
import logging
import requests
from datetime import datetime

load_dotenv()

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# اتصال Binance
client = Client(
    api_key=os.getenv("BINANCE_API_KEY"),
    api_secret=os.getenv("BINANCE_SECRET_KEY"),
    testnet=True
)

# ==============================
# ⚙️ الإعدادات — غيّر هنا فقط
TRADE_AMOUNT_USDT = 800
SYMBOL = "ETHUSDT"
SECRET_TOKEN = os.getenv("WEBHOOK_SECRET")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
# ==============================

# إحصائيات التداول
stats = {
    "total_trades": 0,
    "successful_trades": 0,
    "total_profit": 0.0,
    "last_buy_price": 0.0,
    "trades_history": []
}


def send_telegram(message):
    """إرسال رسالة لـ Telegram"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        })
    except Exception as e:
        logging.error(f"Telegram error: {e}")


def calculate_profit(action, price, quantity):
    """حساب الربح والخسارة"""
    profit = 0.0
    if action == "sell" and stats["last_buy_price"] > 0:
        profit = (price - stats["last_buy_price"]) * quantity
        stats["total_profit"] += profit
        if profit > 0:
            stats["successful_trades"] += 1
    return profit


@app.route("/", methods=["GET"])
def home():
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
    data = request.get_json()

    if not data or data.get("token") != SECRET_TOKEN:
        logging.warning("❌ Unauthorized request")
        return jsonify({"error": "Unauthorized"}), 401

    action = data.get("action")
    symbol = data.get("symbol", SYMBOL)

    logging.info(f"📩 Signal: {action} | Symbol: {symbol}")

    try:
        # احسب الكمية
        price = float(client.get_symbol_ticker(symbol=symbol)["price"])
        quantity = round(TRADE_AMOUNT_USDT / price, 4)

        logging.info(f"💰 Amount: ${TRADE_AMOUNT_USDT} | Price: {price} | Qty: {quantity}")

        if action == "buy":
            order = client.order_market_buy(symbol=symbol, quantity=quantity)
            stats["last_buy_price"] = price
            stats["total_trades"] += 1

            # إرسال تقرير Telegram
            send_telegram(
                f"🟢 <b>صفقة شراء جديدة!</b>\n"
                f"━━━━━━━━━━━━━━\n"
                f"💎 العملة: {symbol}\n"
                f"💵 المبلغ: ${TRADE_AMOUNT_USDT}\n"
                f"📊 السعر: ${price:,.2f}\n"
                f"🔢 الكمية: {quantity}\n"
                f"⏰ الوقت: {datetime.now().strftime('%H:%M:%S')}\n"
                f"━━━━━━━━━━━━━━\n"
                f"📈 إجمالي الصفقات: {stats['total_trades']}"
            )

            logging.info(f"✅ BUY executed: {order}")
            return jsonify({"status": "BUY executed ✅", "quantity": quantity, "price": price}), 200

        elif action == "sell":
            order = client.order_market_sell(symbol=symbol, quantity=quantity)
            stats["total_trades"] += 1
            profit = calculate_profit("sell", price, quantity)

            # حساب نسبة النجاح
            win_rate = 0
            if stats["total_trades"] > 0:
                win_rate = (stats["successful_trades"] / stats["total_trades"]) * 100

            profit_emoji = "🟢" if profit >= 0 else "🔴"

            # إرسال تقرير Telegram
            send_telegram(
                f"🔴 <b>صفقة بيع جديدة!</b>\n"
                f"━━━━━━━━━━━━━━\n"
                f"💎 العملة: {symbol}\n"
                f"💵 المبلغ: ${TRADE_AMOUNT_USDT}\n"
                f"📊 السعر: ${price:,.2f}\n"
                f"🔢 الكمية: {quantity}\n"
                f"⏰ الوقت: {datetime.now().strftime('%H:%M:%S')}\n"
                f"━━━━━━━━━━━━━━\n"
                f"📊 <b>الإحصائيات:</b>\n"
                f"📈 إجمالي الصفقات: {stats['total_trades']}\n"
                f"✅ صفقات ناجحة: {stats['successful_trades']}\n"
                f"🎯 نسبة النجاح: {win_rate:.1f}%\n"
                f"{profit_emoji} الربح/الخسارة: ${profit:,.2f}\n"
                f"💰 إجمالي الربح: ${stats['total_profit']:,.2f}"
            )

            logging.info(f"✅ SELL executed: {order}")
            return jsonify({"status": "SELL executed ✅", "quantity": quantity, "price": price, "profit": profit}), 200

        else:
            return jsonify({"error": "Invalid action"}), 400

    except BinanceAPIException as e:
        error_msg = str(e)
        logging.error(f"❌ Binance error: {error_msg}")
        send_telegram(f"❌ <b>خطأ في التداول!</b>\n{error_msg}")
        return jsonify({"error": error_msg}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
