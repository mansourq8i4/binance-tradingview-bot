from flask import Flask, request, jsonify
from binance.client import Client
from binance.exceptions import BinanceAPIException
from dotenv import load_dotenv
import os
import logging

load_dotenv()

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# اتصال Binance
client = Client(
    api_key=os.getenv("BINANCE_API_KEY"),
    api_secret=os.getenv("BINANCE_SECRET_KEY")
)

# ==============================
# ⚙️ الإعدادات — غيّر هنا فقط
TRADE_AMOUNT_USDT = 800   # ← المبلغ بالدولار لكل صفقة
SYMBOL = "ETHUSDT"        # ← العملة الافتراضية
SECRET_TOKEN = os.getenv("WEBHOOK_SECRET")
# ==============================


@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "Bot is running ✅"}), 200


@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()

    # التحقق من الرمز السري
    if not data or data.get("token") != SECRET_TOKEN:
        logging.warning("❌ Unauthorized request")
        return jsonify({"error": "Unauthorized"}), 401

    action = data.get("action")           # "buy" أو "sell"
    symbol = data.get("symbol", SYMBOL)   # العملة (اختياري في الرسالة)

    logging.info(f"📩 Signal: {action} | Symbol: {symbol}")

    try:
        # احسب الكمية بناءً على السعر الحالي
        price = float(client.get_symbol_ticker(symbol=symbol)["price"])
        quantity = round(TRADE_AMOUNT_USDT / price, 4)

        logging.info(f"💰 Amount: ${TRADE_AMOUNT_USDT} | Price: {price} | Qty: {quantity}")

        if action == "buy":
            order = client.order_market_buy(
                symbol=symbol,
                quantity=quantity
            )
            logging.info(f"✅ BUY executed: {order}")
            return jsonify({
                "status": "BUY executed ✅",
                "symbol": symbol,
                "amount_usdt": TRADE_AMOUNT_USDT,
                "quantity": quantity,
                "price": price
            }), 200

        elif action == "sell":
            order = client.order_market_sell(
                symbol=symbol,
                quantity=quantity
            )
            logging.info(f"✅ SELL executed: {order}")
            return jsonify({
                "status": "SELL executed ✅",
                "symbol": symbol,
                "amount_usdt": TRADE_AMOUNT_USDT,
                "quantity": quantity,
                "price": price
            }), 200

        else:
            return jsonify({"error": "Invalid action. Use 'buy' or 'sell'"}), 400

    except BinanceAPIException as e:
        logging.error(f"❌ Binance error: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=10000)

