import os
import time
import logging
import requests

from py_clob_client.client import ClobClient

# =========================
# CONFIG
# =========================
HOST = "https://clob.polymarket.com"
CHAIN_ID = 137

SCAN_INTERVAL = 10

PRIVATE_KEY = os.getenv("PRIVATE_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# =========================
# LOG
# =========================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger()

# =========================
# TELEGRAM（retry）
# =========================
def send_tg(msg, retries=5):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    for _ in range(retries):
        try:
            requests.post(url, json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": msg
            }, timeout=10)
            return
        except:
            time.sleep(2)

# =========================
# INIT CLOB
# =========================
client = ClobClient(
    host=HOST,
    chain_id=CHAIN_ID,
    key=PRIVATE_KEY,
)

client.set_api_creds(client.create_or_derive_api_creds())

# =========================
# FETCH MARKETS
# =========================
def fetch_markets():
    try:
        url = "https://gamma-api.polymarket.com/markets"
        res = requests.get(url, params={"limit": 50}, timeout=15)

        if res.status_code != 200:
            logger.error(f"bad response: {res.status_code}")
            return []

        return res.json()

    except Exception as e:
        logger.error(f"fetch error: {e}")
        return []

# =========================
# GET PRICE（CLOB）
# =========================
def get_price(token_id):
    try:
        book = client.get_order_book(token_id)

        if not book["asks"]:
            return None

        return float(book["asks"][0]["price"])

    except Exception as e:
        logger.debug(f"price error: {e}")
        return None

# =========================
# STRATEGY（測試版）
# =========================
def check_opportunity(yes_price, no_price):
    signals = []

    # 🔥 測試策略（一定會出）
    if yes_price < 0.5:
        signals.append("BUY YES")

    if no_price < 0.5:
        signals.append("BUY NO")

    return signals

# =========================
# MAIN
# =========================
def main():
    logger.info("🚀 CLOB STRATEGY BOT START")

    seen = set()

    while True:
        try:
            markets = fetch_markets()
            logger.info(f"Scanning {len(markets)} markets")

            for m in markets:
                try:
                    tokens = m.get("clobTokenIds", [])
                    if len(tokens) != 2:
                        continue

                    yes_token, no_token = tokens

                    yes_price = get_price(yes_token)
                    no_price = get_price(no_token)
logger.info(f"DEBUG tokens: {yes_token} / {no_token}")
logger.info(f"RAW prices: {yes_price} / {no_price}")

                    if yes_price is None or no_price is None:
                        continue

                    logger.info(f"{yes_price:.3f} / {no_price:.3f}")

                    signals = check_opportunity(yes_price, no_price)

                    if signals:
                        key = m.get("slug")

                        if key in seen:
                            continue

                        seen.add(key)

                        msg = (
                            f"📈 SIGNAL\n"
                            f"{m.get('question')}\n\n"
                            f"YES: {yes_price}\n"
                            f"NO: {no_price}\n"
                            f"{signals}"
                        )

                        logger.info(msg)
                        send_tg(msg)

                except Exception as e:
                    logger.debug(e)

            time.sleep(SCAN_INTERVAL)

        except Exception as e:
            logger.error(f"MAIN ERROR: {e}", exc_info=True)
            time.sleep(5)

# =========================
if __name__ == "__main__":
    main()
