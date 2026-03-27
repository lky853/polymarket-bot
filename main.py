import requests
import time
import os
import logging

SCAN_INTERVAL = 10
MIN_VOLUME = 10000

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger()


def send_telegram(message, retries=5):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    for _ in range(retries):
        try:
            requests.post(url, json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message
            }, timeout=10)
            return
        except:
            time.sleep(2)


# ✅ 正確抓 markets
def fetch_markets():
    try:
        url = "https://gamma-api.polymarket.com/markets"
        res = requests.get(url, params={"limit": 100}, timeout=20)

        if res.status_code != 200:
            logger.error(f"bad response: {res.status_code}")
            return []

        return res.json()

    except Exception as e:
        logger.error(f"fetch error: {e}")
        return []


# ✅ 從 tokens 抓價格（關鍵）
def find_opportunities(markets):
    opportunities = []

    for m in markets:
        try:
            tokens = m.get("tokens", [])
            if len(tokens) < 2:
                continue

            yes_price = float(tokens[0].get("price", 0))
            no_price = float(tokens[1].get("price", 0))

            # ❗過濾無效價格
            if yes_price == 0 or no_price == 0:
                continue

            # 🔥 超寬鬆（一定出）
            if yes_price < 0.8:
                opportunities.append({
                    "type": "BUY YES",
                    "question": m.get("question"),
                    "price": yes_price,
                    "url": f"https://polymarket.com/event/{m.get('slug')}"
                })

            if no_price < 0.8:
                opportunities.append({
                    "type": "BUY NO",
                    "question": m.get("question"),
                    "price": no_price,
                    "url": f"https://polymarket.com/event/{m.get('slug')}"
                })

        except Exception as e:
            logger.debug(e)

    return opportunities


def format_message(opps):
    msg = "📈 發現機會\n\n"

    for o in opps[:5]:
        msg += (
            f"{o['type']}\n"
            f"{o['question']}\n"
            f"price: {o['price']}\n"
            f"{o['url']}\n\n"
        )

    return msg


def main():
    logger.info("🚀 Polymarket Bot Started")

    seen = set()

    while True:
        try:
            markets = fetch_markets()

            logger.info(f"Scanning... {len(markets)} markets")

            opps = find_opportunities(markets)

            logger.info(f"Found {len(opps)} opportunities")

            new_opps = []

            for o in opps:
                key = o["url"]
                if key not in seen:
                    seen.add(key)
                    new_opps.append(o)

            if new_opps:
                send_telegram(format_message(new_opps))

            time.sleep(SCAN_INTERVAL)

        except Exception as e:
            logger.error(f"MAIN LOOP ERROR: {e}", exc_info=True)
            time.sleep(5)


if __name__ == "__main__":
    main()
