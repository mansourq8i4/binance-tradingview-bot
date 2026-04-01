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

OKX_API_KEY = os.getenv("OKX_API_KEY")
OKX_API_SECRET = os.getenv("OKX_API_SECRET")
OKX_PASSPHRASE = os.getenv("OKX_PASSPHRASE")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

TRADE_AMOUNT = 200
DEFAULT_SYMBOL = "ETHUSDT"

client = ccxt.okx({
    'apiKey': OKX_API_KEY,
    'secret': OKX_API_SECRET,
    'password': OKX_PASSPHRASE,
    'enableRateLimit': True,
    'sandbox': False
})

# تتبع الصفقات المفتوحة
open_positions = {}

stats = {"total_trades": 0, "successful_trades": 0, "total_profit": 0.0, "last_buy_price": 0.0}

def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"})
        logger.info("Telegram sent OK")
    except Exception as e:
        logger.error(f"Telegram error: {e}")

def get_okx_symbol(ticker):
    """تحويل ticker إلى صيغة OKX صحيحة"""
    ticker = ticker.upper()
    
    candidates = [
        ticker if "/" in ticker else f"{ticker.replace('USDT', '')}/USDT",
        ticker,
        f"{ticker.replace('USDT', '')}-USDT"
    ]
    
    for candidate in candidates:
        try:
            client.fetch_ticker(candidate)
            logger.info(f"Found symbol: {candidate}")
            return candidate
        except:
            continue
    
    logger.warning(f"Symbol {ticker} not found in OKX")
    return None

@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "Bot is running OK - LIVE TRADING"}), 200

@app.route("/stats", methods=["GET"])
def get_stats():
    wr = (stats["successful_trades"] / stats["total_trades"] * 100) if stats["total_trades"] > 0 else 0
    return jsonify({
        "total_trades": stats["total_trades"],
        "successful_trades": stats["successful_trades"],
        "win_rate": f"{wr:.1f}%",
        "total_profit": f"${stats['total_profit']:.2f}",
        "open_positions": open_positions
    }), 200

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data"}), 400
        
        logger.info(f"Received data: {data}")
        
        signal = data.get("signal", data.get("action", "")).lower()
        ticker = data.get("ticker", DEFAULT_SYMBOL).upper()
        trade_power = data.get("trade_power", TRADE_AMOUNT)
        
        try:
            amount = float(trade_power)
        except:
            amount = TRADE_AMOUNT
        
        if signal not in ["buy", "sell"]:
            logger.warning(f"Invalid signal: {signal}")
            return jsonify({"error": "Invalid signal"}), 400
        
        symbol = get_okx_symbol(ticker)
        if not symbol:
            error_msg = f"Symbol {ticker} not found in OKX"
            logger.error(error_msg)
            send_telegram(f"<b>Error:</b> {error_msg}")
            return jsonify({"error": error_msg}), 400
        
        logger.info(f"Signal: {signal.upper()} | Symbol: {symbol} | Amount: ${amount}")
        
        # التحقق من الصفقات المفتوحة
        if signal == "buy":
            # إذا كانت هناك صفقة مفتوحة - تجاهل الشراء
            if symbol in open_positions:
                msg = f"⏭️ <b>BUY IGNORED</b>\n\n"
                msg += f"<b>Symbol:</b> {symbol}\n"
                msg += f"<b>Reason:</b> Position already open\n"
                msg += f"<b>Entry Price:</b> ${open_positions[symbol]['entry_price']}\n"
                msg += f"<b>Time:</b> {datetime.now().strftime('%H:%M:%S')}\n"
                
                send_telegram(msg)
                logger.info(f"BUY signal ignored for {symbol} - position already open")
                return jsonify({"status": "BUY IGNORED - Position already open"}), 200
        
        elif signal == "sell":
            # إذا لم تكن هناك صفقة مفتوحة - تجاهل البيع
            if symbol not in open_positions:
                msg = f"⏭️ <b>SELL IGNORED</b>\n\n"
                msg += f"<b>Symbol:</b> {symbol}\n"
                msg += f"<b>Reason:</b> No open position\n"
                msg += f"<b>Time:</b> {datetime.now().strftime('%H:%M:%S')}\n"
                
                send_telegram(msg)
                logger.info(f"SELL signal ignored for {symbol} - no open position")
                return jsonify({"status": "SELL IGNORED - No open position"}), 200
        
        try:
            tick = client.fetch_ticker(symbol)
            current_price = tick['last']
            qty = round(amount / current_price, 4)
            
            logger.info(f"Price: ${current_price} | Qty: {qty}")
            
            if signal == "buy":
                order = client.create_market_buy_order(symbol, qty)
                stats["last_buy_price"] = current_price
                stats["total_trades"] += 1
                
                # إضافة الصفقة للصفقات المفتوحة
                open_positions[symbol] = {
                    "entry_price": current_price,
                    "quantity": qty,
                    "amount": amount,
                    "entry_time": datetime.now().strftime('%H:%M:%S')
                }
                
                msg = f"<b>🟢 BUY EXECUTED (LIVE)</b>\n\n"
                msg += f"<b>Pair:</b> {symbol}\n"
                msg += f"<b>Entry Price:</b> ${current_price:.8f}\n"
                msg += f"<b>Amount:</b> ${amount:.2f}\n"
                msg += f"<b>Qty:</b> {qty}\n"
                msg += f"<b>Time:</b> {datetime.now().strftime('%H:%M:%S')}\n\n"
                msg += f"<b>Stats:</b>\n"
                msg += f"Total Trades: {stats['total_trades']}\n"
                msg += f"<b>⚠️ LIVE TRADING ⚠️</b>\n"
                
                send_telegram(msg)
                logger.info("BUY executed OK")
                return jsonify({"status": "BUY OK", "symbol": symbol}), 200
            
            elif signal == "sell":
                order = client.create_market_sell_order(symbol, qty)
                stats["total_trades"] += 1
                
                # حساب الربح/الخسارة
                entry_price = open_positions[symbol]["entry_price"]
                profit = (current_price - entry_price) * qty
                
                msg = f"<b>🔴 SELL EXECUTED (LIVE)</b>\n\n"
                msg += f"<b>Pair:</b> {symbol}\n"
                msg += f"<b>Entry Price:</b> ${entry_price:.8f}\n"
                msg += f"<b>Exit Price:</b> ${current_price:.8f}\n"
                msg += f"<b>Qty:</b> {qty}\n"
                msg += f"<b>Profit/Loss:</b> ${profit:.2f}\n"
                msg += f"<b>Time:</b> {datetime.now().strftime('%H:%M:%S')}\n\n"
                msg += f"<b>Stats:</b>\n"
                msg += f"Total Trades: {stats['total_trades']}\n"
                msg += f"<b>⚠️ LIVE TRADING ⚠️</b>\n"
                
                send_telegram(msg)
                logger.info("SELL executed OK")
                
                # حذف الصفقة من الصفقات المفتوحة
                del open_positions[symbol]
                
                return jsonify({"status": "SELL OK", "symbol": symbol, "profit": profit}), 200
        
        except Exception as e:
            logger.error(f"Error: {e}")
            send_telegram(f"<b>❌ LIVE TRADING ERROR:</b> {str(e)}")
            return jsonify({"error": str(e)}), 500
    
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
