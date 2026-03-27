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
        res = requests.get(
            "https://gamma-api.polymarket.com/markets",
            params={"limit": 200},
            timeout=15
        )

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

        # 優先用 ask（買價）
        if book["asks"]:
            return float(book["asks"][0]["price"])

        # 🔥 fallback 用 bid（賣價）
        if book["bids"]:
            return float(book["bids"][0]["price"])

        return None

    except Exception as e:
        logger.debug(f"price error: {e}")
        return None
        
# =========================
# MAIN
# =========================
def main():
    logger.info("🚀 CLOB BOT START")

    while True:
        try:
            markets = fetch_markets()
            logger.info(f"Scanning {len(markets)} markets")

            for m in markets:
                try:
                    tokens = m.get("clobTokenIds", [])

                    # DEBUG
                    logger.info(f"TOKENS RAW: {tokens}")

                    # 只要 YES/NO 市場
                    if not tokens or len(tokens) != 2:
                        continue

                    # 只抓 active
                    if not m.get("active"):
                        continue

                    # 流動性過濾
                    if float(m.get("volume", 0)) < 5000:
                        continue

                    yes_token, no_token = tokens

                    logger.info(f"DEBUG tokens: {yes_token} / {no_token}")

                    yes_price = get_price(yes_token)
                    no_price = get_price(no_token)

                    logger.info(f"RAW prices: {yes_price} / {no_price}")

                    if yes_price is None or no_price is None:
                        continue

                    logger.info(f"{yes_price:.3f} / {no_price:.3f}")

                    # ===== SIGNAL =====
                    if yes_price < 0.5:
                        msg = (
                            f"📈 BUY YES\n\n"
                            f"{m.get('question')}\n\n"
                            f"price: {yes_price}"
                        )
                        logger.info(msg)
                        send_tg(msg)

                    if no_price < 0.5:
                        msg = (
                            f"📈 BUY NO\n\n"
                            f"{m.get('question')}\n\n"
                            f"price: {no_price}"
                        )
                        logger.info(msg)
                        send_tg(msg)

                except Exception as e:
                    logger.debug(f"market error: {e}")

            time.sleep(SCAN_INTERVAL)

        except Exception as e:
            logger.error(f"MAIN ERROR: {e}", exc_info=True)
            time.sleep(5)

# =========================
if __name__ == "__main__":
    main()
