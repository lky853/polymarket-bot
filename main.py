import os
import time
import logging
import requests

from py_clob_client.client import ClobClient

HOST = "https://clob.polymarket.com"
CHAIN_ID = 137
SCAN_INTERVAL = 10

PRIVATE_KEY = os.getenv("PRIVATE_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger()

def send_tg(msg):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return

    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": msg},
            timeout=10
        )
    except:
        pass

client = ClobClient(
    host=HOST,
    chain_id=CHAIN_ID,
    key=PRIVATE_KEY,
)

client.set_api_creds(client.create_or_derive_api_creds())

def fetch_markets():
    try:
        res = requests.get(
            "https://gamma-api.polymarket.com/markets",
            params={"limit": 200},
            timeout=15
        )
        return res.json()
    except:
        return []

def get_price(token_id):
    try:
        book = client.get_order_book(token_id)

        if not book["asks"]:
            return None

        return float(book["asks"][0]["price"])
    except:
        return None

def main():
    logger.info("🚀 BOT START")

    while True:
        try:
            markets = fetch_markets()
            logger.info(f"Scanning {len(markets)} markets")

            for m in markets:
                try:
                    tokens = m.get("clobTokenIds", [])

                    logger.info(f"TOKENS RAW: {tokens}")

                    if not tokens or len(tokens) != 2:
                        continue

                    yes_token, no_token = tokens

                    logger.info(f"DEBUG tokens: {yes_token} / {no_token}")

                    yes_price = get_price(yes_token)
                    no_price = get_price(no_token)

                    logger.info(f"RAW prices: {yes_price} / {no_price}")

                    if yes_price is None or no_price is None:
                        continue

                    logger.info(f"{yes_price:.3f} / {no_price:.3f}")

                    if yes_price < 0.5:
                        msg = f"BUY YES\n{m.get('question')}\n{yes_price}"
                        logger.info(msg)
                        send_tg(msg)

                    if no_price < 0.5:
                        msg = f"BUY NO\n{m.get('question')}\n{no_price}"
                        logger.info(msg)
                        send_tg(msg)

                except Exception as e:
                    logger.debug(e)

            time.sleep(SCAN_INTERVAL)

        except Exception as e:
            logger.error(e)
            time.sleep(5)

if __name__ == "__main__":
    main()
