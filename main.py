import os
import time
import logging
import requests

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType

# =========================
# CONFIG
# =========================
GAMMA_API = "https://gamma-api.polymarket.com/markets"
HOST = "https://clob.polymarket.com"
CHAIN_ID = 137

PRIVATE_KEY = os.getenv("PRIVATE_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

SCAN_INTERVAL = 5
MIN_VOLUME = 20000

MAX_USDC = 1  # 每次只用 $1（安全）

YES_BUY_THRESHOLD = 0.45
NO_BUY_THRESHOLD = 0.45

# =========================
# LOGGING
# =========================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger()

# =========================
# TELEGRAM
# =========================
def tg(msg):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": msg,
                "disable_web_page_preview": True
            },
            timeout=5
        )
    except Exception as e:
        logger.error(f"TG error: {e}")

# =========================
# INIT CLIENT
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
        r = requests.get(GAMMA_API, timeout=8)
        if r.status_code != 200:
            logger.error(f"API error {r.status_code}")
            return []
        return r.json()
    except Exception as e:
        logger.error(f"fetch error: {e}")
        return []

# =========================
# ORDERBOOK
# =========================
def get_orderbook(token_id):
    try:
        return client.get_order_book(token_id)
    except Exception as e:
        logger.warning(f"orderbook error: {e}")
        return None

# =========================
# BUY FUNCTION（單邊）
# =========================
def buy(token_id, price, side_name, question):
    try:
        size = MAX_USDC / price

        order = OrderArgs(
            price=price,
            size=size,
            side="BUY",
            token_id=token_id,
        )

        resp = client.post_order(
            client.create_order(order),
            OrderType.IOC
        )

        logger.info(f"BUY {side_name} @ {price}")
        tg(f"📈 買入 {side_name}\n{question}\nprice={price}")

    except Exception as e:
        logger.error(f"trade error: {e}")
        tg(f"❌ 下單失敗 {e}")

# =========================
# MAIN
# =========================
def main():
    logger.info("🚀 STRATEGY BOT START")

    cooldown = {}

    while True:
        try:
            markets = fetch_markets()
            print(f"Scanning... {len(markets)} markets")
            
            for m in markets:
                try:
                    if not m.get("active"):
                        continue

                    volume = float(m.get("volume", 0))
                    if volume < MIN_VOLUME:
                        continue

                    tokens = m.get("clobTokenIds", [])
                    if len(tokens) != 2:
                        continue

                    yes_token, no_token = tokens

                    yes_book = get_orderbook(yes_token)
                    no_book = get_orderbook(no_token)

                    if not yes_book or not no_book:
                        continue

                    if not yes_book.get("asks") or not no_book.get("asks"):
                        continue

                    yes_price = float(yes_book["asks"][0]["price"])
                    no_price = float(no_book["asks"][0]["price"])

                    question = m.get("question", "N/A")

                    now = time.time()
                    if question in cooldown and now - cooldown[question] < 300:
                        continue

                    # 🟢 買 YES（低估）
                    if yes_price < YES_BUY_THRESHOLD and no_price > 0.55:
                        logger.info(f"BUY YES signal {yes_price}")
                        buy(yes_token, yes_price, "YES", question)
                        cooldown[question] = now

                    # 🔴 買 NO（低估）
                    elif no_price < NO_BUY_THRESHOLD and yes_price > 0.55:
                        logger.info(f"BUY NO signal {no_price}")
                        buy(no_token, no_price, "NO", question)
                        cooldown[question] = now

                except Exception as e:
                    logger.warning(f"market error: {e}")
                    continue

            time.sleep(SCAN_INTERVAL)

        except Exception as e:
            logger.error(f"MAIN ERROR: {e}")
            time.sleep(5)

# =========================
if __name__ == "__main__":
    main()
