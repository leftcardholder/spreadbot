import asyncio
import ccxt
from aiogram import Bot
from datetime import datetime, timedelta

# --- НАСТРОЙКИ ---
API_TOKEN = '8607275112:AAH72m8L6fgymoo9eotz_udcZJ-B4tFE6-o'
CHAT_ID = 8331349617
MIN_SPREAD_NET = 0.3   # Минимальный ЧИСТЫЙ спред после всех комиссий
COOLDOWN_MIN = 3
PAUSE_BETWEEN_COINS = 0.3
PAUSE_BETWEEN_ROUNDS = 10

# Комиссии бирж в % (taker-комиссия — та что платится при рыночном ордере)
# Также учитывается комиссия за вывод (withdrawal) — примерная средняя
FEES = {
    'Binance': {'taker': 0.1,  'withdraw': 0.1},
    'Bybit':   {'taker': 0.1,  'withdraw': 0.1},
    'OKX':     {'taker': 0.1,  'withdraw': 0.1},
    'KuCoin':  {'taker': 0.1,  'withdraw': 0.15},
    'BingX':   {'taker': 0.1,  'withdraw': 0.15},
}

SYMBOLS = [
    'BTC/USDT', 'ETH/USDT', 'TON/USDT', 'SOL/USDT', 'ARB/USDT',
    'TIA/USDT', 'SUI/USDT', 'OP/USDT', 'APT/USDT', 'AVAX/USDT',
    'DOT/USDT', 'MATIC/USDT', 'LINK/USDT', 'LTC/USDT', 'XRP/USDT',
    'ADA/USDT', 'NEAR/USDT', 'STX/USDT', 'INJ/USDT', 'RNDR/USDT',
    'ORDI/USDT', 'SEI/USDT', 'FET/USDT', 'GALA/USDT', 'PEPE/USDT'
    'DOGE/USDT', 'SHIB/USDT', 'TRX/USDT', 'ATOM/USDT', 'UNI/USDT',
'FIL/USDT', 'LDO/USDT', 'SAND/USDT', 'MANA/USDT', 'AXS/USDT',
'ALGO/USDT', 'EOS/USDT', 'FLOW/USDT', 'CHZ/USDT', 'ENS/USDT',
'ZIL/USDT', 'ONE/USDT', 'HOT/USDT', 'ROSE/USDT', 'CFX/USDT'
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
    special = r'_*[]()~`>#+-=|{}.!'
    return ''.join(f'\\{c}' if c in special else c for c in str(text))


def calc_net_spread(gross_spread: float, buy_ex: str, sell_ex: str) -> tuple[float, float]:
    """
    Считает чистый спред после комиссий.
    Формула: спред - комиссия покупки - комиссия продажи - комиссия вывода
    Возвращает (чистый_спред, сумма_комиссий)
    """
    buy_fee  = FEES[buy_ex]['taker']      # комиссия за покупку
    sell_fee = FEES[sell_ex]['taker']     # комиссия за продажу
    withdraw = FEES[buy_ex]['withdraw']   # вывод с биржи покупки

    total_fees = buy_fee + sell_fee + withdraw
    net_spread = gross_spread - total_fees
    return net_spread, total_fees


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
    bot = Bot(token=API_TOKEN)

    print("Сканер запущен!")
    print(f"Монет: {len(SYMBOLS)} | Бирж: {len(EXCHANGES)}")
    print(f"Мин. чистый спред: {MIN_SPREAD_NET}% | Кулдаун: {COOLDOWN_MIN} мин")

    try:
        me = await bot.get_me()
        print(f"Telegram подключён! Бот: @{me.username}")
        await bot.send_message(
            CHAT_ID,
            f"Сканер запущен\n"
            f"Монет: {len(SYMBOLS)} | Бирж: {len(EXCHANGES)}\n"
            f"Мин. чистый спред: {MIN_SPREAD_NET}%\n"
            f"(учитываются комиссии taker + вывод)"
        )
    except Exception as e:
        print(f"Ошибка подключения к Telegram: {e}")
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

                gross_spread = ((p_max - p_min) / p_min) * 100
                net_spread, total_fees = calc_net_spread(gross_spread, min_ex, max_ex)

                if net_spread >= MIN_SPREAD_NET:
                    now = datetime.now()
                    last = last_alert.get(symbol)
                    if last and (now - last) < timedelta(minutes=COOLDOWN_MIN):
                        print(f"Кулдаун: {symbol} чистый={net_spread:.2f}%")
                    else:
                        fire = "🔥🔥🔥" if net_spread >= 1.5 else ("🔥🔥" if net_spread >= 0.7 else "🔥")

                        msg = (
                            f"{fire} *Связка: {escape_md(symbol)}*\n\n"
                            f"📥 Купить на *{escape_md(min_ex)}*: `{escape_md(p_min)}`\n"
                            f"📤 Продать на *{escape_md(max_ex)}*: `{escape_md(p_max)}`\n\n"
                            f"📊 Спред брутто: *{escape_md(f'{gross_spread:.2f}')}%*\n"
                            f"💸 Комиссии: *{escape_md(f'{total_fees:.2f}')}%*\n"
                            f"✅ Чистый спред: *{escape_md(f'{net_spread:.2f}')}%*\n\n"
                            f"🕐 {escape_md(now.strftime('%H:%M:%S'))}"
                        )
                        try:
                            await bot.send_message(CHAT_ID, msg, parse_mode="MarkdownV2")
                            last_alert[symbol] = now
                            alerts_in_round += 1
                            print(f"Алерт: {symbol} | брутто={gross_spread:.2f}% | "
                                  f"комиссии={total_fees:.2f}% | чистый={net_spread:.2f}%")
                        except Exception as e:
                            print(f"Ошибка TG ({symbol}): {e}")

            await asyncio.sleep(PAUSE_BETWEEN_COINS)

        elapsed = (datetime.now() - round_start).seconds
        print(f"--- Круг завершён за {elapsed}с | Алертов: {alerts_in_round} ---")
        await asyncio.sleep(PAUSE_BETWEEN_ROUNDS)


if __name__ == '__main__':
    asyncio.run(check_prices())
