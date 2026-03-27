import requests
import time
import os
import logging

# =========================
# CONFIG
# =========================
SCAN_INTERVAL = 10
MIN_VOLUME = 20000
ARBITRAGE_THRESHOLD = 0.99  # YES + NO < 1 才算套利

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
# TELEGRAM（帶 retry）
# =========================
def send_telegram(message, retries=5):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram not configured")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    for i in range(retries):
        try:
            res = requests.post(url, json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message
            }, timeout=10)

            if res.status_code == 200:
                logger.info("Telegram sent")
                return
            else:
                logger.error(f"Telegram failed: {res.text}")

        except Exception as e:
            logger.error(f"Telegram error: {e}")

        time.sleep(2)

    logger.error("Telegram failed after retries")

# =========================
# FETCH MARKETS（分頁版🔥）
# =========================
def fetch_markets():
    try:
        url = "https://gamma-api.polymarket.com/markets"
        params = {
            "limit": 100
        }

        res = requests.get(url, params=params, timeout=20)

        if res.status_code != 200:
            logger.error(f"bad response: {res.status_code}")
            return []

        data = res.json()

        if isinstance(data, list):
            return data

        return data.get("markets", [])

    except Exception as e:
        logger.error(f"fetch error: {e}")
        return []

# =========================
# FIND ARBITRAGE
# =========================
def find_arbitrage(markets):
    opportunities = []

    for m in markets:
        try:
            if not m.get("outcomes") or len(m["outcomes"]) != 2:
                continue

            volume = float(m.get("volume", 0))
            if volume < MIN_VOLUME:
                continue

            yes_price = float(m["outcomes"][0]["price"])
            no_price = float(m["outcomes"][1]["price"])

            # 🔥 新策略（偏差）
            if yes_price < 0.45:
                opportunities.append({
                    "type": "BUY YES",
                    "question": m.get("question"),
                    "price": yes_price,
                    "url": f"https://polymarket.com/event/{m.get('slug')}"
                })

            if no_price < 0.45:
                opportunities.append({
                    "type": "BUY NO",
                    "question": m.get("question"),
                    "price": no_price,
                    "url": f"https://polymarket.com/event/{m.get('slug')}"
                })

        except Exception as e:
            logger.debug(e)

    return opportunities

# =========================
# FORMAT MESSAGE
# =========================
def format_message(opps):
    msg = "🚀 套利機會\n\n"

    for o in opps[:5]:
        msg += (
            f"{o['question']}\n"
            f"YES: {o['yes']} | NO: {o['no']}\n"
            f"SUM: {o['sum']}\n"
            f"{o['url']}\n\n"
        )

    return msg

# =========================
# MAIN LOOP
# =========================
def main():
    logger.info("🚀 Polymarket Arbitrage Bot Started")

    seen = set()

    while True:
        try:
            markets = fetch_markets()

            logger.info(f"Scanning... {len(markets)} markets")

            opps = find_arbitrage(markets)

            logger.info(f"Found {len(opps)} opportunities")

            new_opps = []

            for o in opps:
                key = o["url"]
                if key not in seen:
                    seen.add(key)
                    new_opps.append(o)

            if new_opps:
                msg = format_message(new_opps)
                send_telegram(msg)

            time.sleep(SCAN_INTERVAL)

        except Exception as e:
            logger.error(f"MAIN LOOP ERROR: {e}", exc_info=True)
            time.sleep(5)

# =========================
# ENTRY
# =========================
if __name__ == "__main__":
    main()
