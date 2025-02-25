# api_handlers.py
import aiohttp
import config

async def buy_token_gaspump(token_address: str, ton_amount: float, wallet_address: str) -> str:
    url = f"{config.GASPUMP_API_URL}/pools/{token_address}/buy"
    payload = {"amount": ton_amount, "wallet": wallet_address}
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as response:
            if response.status == 200:
                return "Токен куплен через GasPump!"
            else:
                return f"Ошибка GasPump: {await response.text()}"

async def buy_token_stonfi(token_address: str, ton_amount: float, wallet_address: str) -> str:
    url = f"{config.STONFI_API_URL}/swap"
    payload = {
        "offer_address": config.TON_ADDRESS,
        "ask_address": token_address,
        "units": int(ton_amount * 10**9),
        "wallet": wallet_address
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as response:
            if response.status == 200:
                return "Токен куплен через Ston.fi!"
            else:
                return f"Ошибка Ston.fi: {await response.text()}"

async def buy_token_dedust(token_address: str, ton_amount: float, wallet_address: str) -> str:
    url = f"{config.DEDUST_API_URL}/pools/{token_address}/swap"
    payload = {
        "amount": int(ton_amount * 10**9),
        "from": config.TON_ADDRESS,
        "to": token_address,
        "wallet": wallet_address
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as response:
            if response.status == 200:
                return "Токен куплен через DeDust!"
            else:
                return f"Ошибка DeDust: {await response.text()}"

async def check_dev_wallet(dev_wallet: str, token_address: str = None) -> bool:
    async with aiohttp.ClientSession() as session:
        url = f"{config.TON_API_URL}/accounts/{dev_wallet}/events"
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                for event in data.get("events", []):
                    if "actions" in event and event["actions"][0]["type"] == "TonTransfer":
                        # Здесь можно добавить проверку токена, если нужен конкретный
                        return True
            return False

async def sell_token_stonfi(token_address: str, amount: float, wallet_address: str) -> str:
    url = f"{config.STONFI_API_URL}/swap"
    total_units = int(amount * 10**9)
    commission_units = int(total_units * config.COMMISSION_RATE)
    sell_units = total_units - commission_units

    async with aiohttp.ClientSession() as session:
        # Продажа основной части
        payload_sell = {
            "offer_address": token_address,
            "ask_address": config.TON_ADDRESS,
            "units": sell_units,
            "wallet": wallet_address
        }
        async with session.post(url, json=payload_sell) as response_sell:
            sell_result = await response_sell.text() if response_sell.status != 200 else "OK"

        # Отправка комиссии
        payload_commission = {
            "offer_address": token_address,
            "ask_address": config.TON_ADDRESS,
            "units": commission_units,
            "wallet": config.COMMISSION_WALLET
        }
        async with session.post(url, json=payload_commission) as response_commission:
            commission_result = await response_commission.text() if response_commission.status != 200 else "OK"

        if sell_result == "OK" and commission_result == "OK":
            return f"Токен продан! Комиссия 1% ({commission_units / 10**9} TON) отправлена."
        else:
            return f"Ошибка: {sell_result} | Комиссия: {commission_result}"
