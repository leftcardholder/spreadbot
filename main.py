import asyncio
import ccxt
from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession
from datetime import datetime, timedelta

# --- НАСТРОЙКИ ---
API_TOKEN = '8607275112:AAH72m8L6fgymoo9eotz_udcZJ-B4tFE6-o'
CHAT_ID = 8331349617
MIN_SPREAD = 0.05
COOLDOWN_MIN = 10
PAUSE_BETWEEN_COINS = 0.3
PAUSE_BETWEEN_ROUNDS = 10

PROXY = "socks5://45.32.39.135:1080"  # твой прокси

SYMBOLS = [
    'BTC/USDT', 'ETH/USDT', 'TON/USDT', 'SOL/USDT', 'ARB/USDT',
    'TIA/USDT', 'SUI/USDT', 'OP/USDT', 'APT/USDT', 'AVAX/USDT',
    'DOT/USDT', 'MATIC/USDT', 'LINK/USDT', 'LTC/USDT', 'XRP/USDT',
    'ADA/USDT', 'NEAR/USDT', 'STX/USDT', 'INJ/USDT', 'RNDR/USDT',
    'ORDI/USDT', 'SEI/USDT', 'FET/USDT', 'GALA/USDT', 'PEPE/USDT'
]

EXCHANGES = {
    'Binance': ccxt.binance({'enableRateLimit': True}),
    'Bybit':   ccxt.bybit({'enableRateLimit': True}),
    'OKX':     ccxt.okx({'enableRateLimit': True}),
    'KuCoin':  ccxt.kucoin({'enableRateLimit': True}),
    'BingX':   ccxt.bingx({'enableRateLimit': True}),
}

last_alert: dict[str, datetime] = {}


def escape_md(text: str) -> str:
    """Экранирует спецсимволы для MarkdownV2"""
    special = r'_*[]()~`>#+-=|{}.!'
    return ''.join(f'\\{c}' if c in special else c for c in str(text))


async def fetch_price(name: str, ex, symbol: str):
    try:
        ticker = await asyncio.to_thread(ex.fetch_ticker, symbol)
        price = ticker.get('last')
        if price and price > 0:
            return name, price
    except Exception:
        pass
    return name, None


async def check_prices():
    session = AiohttpSession(proxy=PROXY)
    bot = Bot(token=API_TOKEN, session=session)

    print(f"Сканер запущен с прокси: {PROXY}")
    print(f"Монет: {len(SYMBOLS)} | Бирж: {len(EXCHANGES)}")
    print(f"Мин. спред: {MIN_SPREAD}% | Кулдаун: {COOLDOWN_MIN} мин\n")

    try:
        me = await bot.get_me()
        print(f"Telegram подключён! Бот: @{me.username}")
        await bot.send_message(
            CHAT_ID,
            f"✅ Сканер запущен\nМонет: {len(SYMBOLS)} | Бирж: {len(EXCHANGES)}\nМин. спред: {MIN_SPREAD}%"
        )
    except Exception as e:
        print(f"Не удалось подключиться к Telegram: {e}")
        input("Нажми Enter для закрытия...")
        return

    while True:
        round_start = datetime.now()
        alerts_in_round = 0

        for symbol in SYMBOLS:
            tasks = [fetch_price(name, ex, symbol) for name, ex in EXCHANGES.items()]
            results = await asyncio.gather(*tasks)
            prices = {name: price for name, price in results if price is not None}

            if len(prices) >= 2:
                min_ex = min(prices, key=prices.get)
                max_ex = max(prices, key=prices.get)
                p_min = prices[min_ex]
                p_max = prices[max_ex]
                spread = ((p_max - p_min) / p_min) * 100

                if spread >= MIN_SPREAD:
                    now = datetime.now()
                    last = last_alert.get(symbol)
                    if last and (now - last) < timedelta(minutes=COOLDOWN_MIN):
                        print(f"Кулдаун: {symbol} {spread:.2f}%")
                    else:
                        fire = "🔥🔥🔥" if spread >= 2.0 else ("🔥🔥" if spread >= 1.0 else "🔥")

                        # Все переменные экранируем через escape_md
                        msg = (
                            f"{fire} *Связка: {escape_md(symbol)}*\n\n"
                            f"📥 Купить на *{escape_md(min_ex)}*: `{escape_md(p_min)}`\n"
                            f"📤 Продать на *{escape_md(max_ex)}*: `{escape_md(p_max)}`\n"
                            f"📈 Спред: *{escape_md(f'{spread:.2f}')}%*\n\n"
                            f"⚠️ Проверь комиссии и статус вывода\!\n"
                            f"🕐 {escape_md(now.strftime('%H:%M:%S'))}"
                        )

                        try:
                            await bot.send_message(CHAT_ID, msg, parse_mode="MarkdownV2")
                            last_alert[symbol] = now
                            alerts_in_round += 1
                            print(f"Алерт: {symbol} | {min_ex} -> {max_ex} | {spread:.2f}%")
                        except Exception as e:
                            print(f"Ошибка TG ({symbol}): {e}")

            await asyncio.sleep(PAUSE_BETWEEN_COINS)

        elapsed = (datetime.now() - round_start).seconds
        print(f"--- Круг завершён за {elapsed}с | Алертов: {alerts_in_round} ---")
        await asyncio.sleep(PAUSE_BETWEEN_ROUNDS)


if __name__ == '__main__':
    try:
        asyncio.run(check_prices())
    except KeyboardInterrupt:
        print("\nСканер остановлен.")
    except Exception as e:
        print(f"\nОШИБКА: {e}")
    finally:
        input("\nНажми Enter для закрытия...")