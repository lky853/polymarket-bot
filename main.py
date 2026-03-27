import requests
import time
import os
import logging

# =========================
# CONFIG
# =========================
SCAN_INTERVAL = 10
MIN_VOLUME = 10000
PRICE_THRESHOLD = 0.6  # 測試用（一定會出訊號）

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
# TELEGRAM（含 retry）
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
# FETCH TICKERS（🔥正確資料源）
# =========================
def fetch_tickers():
    url = "https://gamma-api.polymarket.com/tickers"

    for i in range(3):
        try:
            res = requests.get(url, timeout=20)

            if res.status_code != 200:
                logger.error(f"bad response: {res.status_code}")
                continue

            data = res.json()

            if isinstance(data, list):
                return data

        except Exception as e:
            logger.error(f"fetch error: {e}")

        time.sleep(2)

    return []

# =========================
# STRATEGY（測試版）
# =========================
def find_opportunities(tickers):
    opportunities = []

    for t in tickers:
        try:
            price = float(t.get("price", 0))
            volume = float(t.get("volume", 0))

            if volume < MIN_VOLUME:
                continue

            # 🔥 測試策略（一定會有）
            if price < PRICE_THRESHOLD:
                opportunities.append({
                    "question": t.get("question"),
                    "price": price,
                    "volume": volume,
                    "url": f"https://polymarket.com/event/{t.get('market_slug')}"
                })

        except Exception as e:
            logger.debug(f"parse error: {e}")

    return opportunities

# =========================
# FORMAT MESSAGE
# =========================
def format_message(opps):
    msg = "📈 發現機會\n\n"

    for o in opps[:5]:
        msg += (
            f"{o['question']}\n"
            f"price: {o['price']}\n"
            f"vol: {o['volume']}\n"
            f"{o['url']}\n\n"
        )

    return msg

# =========================
# MAIN LOOP
# =========================
def main():
    logger.info("🚀 Polymarket Strategy Bot Started")

    seen = set()

    while True:
        try:
            tickers = fetch_tickers()

            logger.info(f"Scanning... {len(tickers)} tickers")

            opps = find_opportunities(tickers)

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
