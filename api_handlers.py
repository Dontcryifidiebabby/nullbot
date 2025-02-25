# api_handlers.py
import requests
import aiohttp
import config

def buy_token_gaspump(token_address, ton_amount, wallet_address):
    url = f"{config.GASPUMP_API_URL}/pools/{token_address}/buy"
    payload = {
        "amount": ton_amount,
        "wallet": wallet_address
    }
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        return "Токен куплен через GasPump!"
    else:
        return f"Ошибка GasPump: {response.text}"

def buy_token_stonfi(token_address, ton_amount, wallet_address):
    url = f"{config.STONFI_API_URL}/swap"
    payload = {
        "offer_address": config.TON_ADDRESS,
        "ask_address": token_address,
        "units": int(ton_amount * 10**9),
        "wallet": wallet_address
    }
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        return "Токен куплен через Ston.fi!"
    else:
        return f"Ошибка Ston.fi: {response.text}"

def buy_token_dedust(token_address, ton_amount, wallet_address):
    url = f"{config.DEDUST_API_URL}/pools/{token_address}/swap"
    payload = {
        "amount": int(ton_amount * 10**9),
        "from": config.TON_ADDRESS,
        "to": token_address,
        "wallet": wallet_address
    }
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        return "Токен куплен через DeDust!"
    else:
        return f"Ошибка DeDust: {response.text}"

async def check_dev_wallet(dev_wallet):
    async with aiohttp.ClientSession() as session:
        url = f"{config.TON_API_URL}/accounts/{dev_wallet}/events"
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                for event in data.get("events", []):
                    if "actions" in event and event["actions"][0]["type"] == "TonTransfer":
                        return True
            return False

def sell_token_stonfi(token_address, amount, wallet_address):
    url = f"{config.STONFI_API_URL}/swap"
    total_units = int(amount * 10**9)
    commission_units = int(total_units * config.COMMISSION_RATE)
    sell_units = total_units - commission_units
    
    payload_sell = {
        "offer_address": token_address,
        "ask_address": config.TON_ADDRESS,
        "units": sell_units,
        "wallet": wallet_address
    }
    response_sell = requests.post(url, json=payload_sell)
    
    payload_commission = {
        "offer_address": token_address,
        "ask_address": config.TON_ADDRESS,
        "units": commission_units,
        "wallet": config.COMMISSION_WALLET
    }
    response_commission = requests.post(url, json=payload_commission)
    
    if response_sell.status_code == 200 and response_commission.status_code == 200:
        return f"Токен продан! Комиссия 1% ({commission_units / 10**9} TON) отправлена."
    else:
        return f"Ошибка: {response_sell.text} | Комиссия: {response_commission.text}"