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
# ضع هنا إعداداتك
TRADE_QUANTITY = 0.001   # كمية التداول (مثال: 0.001 BTC)
SYMBOL = "BTCUSDT"       # الزوج المراد تداوله
SECRET_TOKEN = os.getenv("WEBHOOK_SECRET")  # رمز سري لحماية الـ Webhook
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

    action = data.get("action")  # "buy" أو "sell"
    symbol = data.get("symbol", SYMBOL)
    quantity = float(data.get("quantity", TRADE_QUANTITY))

    logging.info(f"📩 Signal received: {action} {quantity} {symbol}")

    try:
        if action == "buy":
            order = client.order_market_buy(
                symbol=symbol,
                quantity=quantity
            )
            logging.info(f"✅ BUY order executed: {order}")
            return jsonify({"status": "BUY executed", "order": order}), 200

        elif action == "sell":
            order = client.order_market_sell(
                symbol=symbol,
                quantity=quantity
            )
            logging.info(f"✅ SELL order executed: {order}")
            return jsonify({"status": "SELL executed", "order": order}), 200

        else:
            return jsonify({"error": "Invalid action. Use 'buy' or 'sell'"}), 400

    except BinanceAPIException as e:
        logging.error(f"❌ Binance error: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
