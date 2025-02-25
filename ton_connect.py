from pytonconnect import TonConnect
from pytonconnect.exceptions import TonConnectError
import asyncio
import qrcode
import os
import config

def init_ton_connect():
    """
    Инициализирует TonConnect.
    """
    connector = TonConnect(
        manifest_url=config.TON_CONNECT_MANIFEST_URL,
    )
    return connector

async def generate_connect_link(chat_id, wallet_name):
    """
    Генерирует ссылку и QR-код для подключения кошелька.
    """
    connector = init_ton_connect()
    if connector.connected:
        await connector.disconnect()
    
    wallets_list = connector.get_wallets()
    wallet = next((w for w in wallets_list if w['name'] == wallet_name), None)
    
    if not wallet:
        raise TonConnectError(f"Кошелёк {wallet_name} не найден.")
    
    connect_request = await connector.connect(wallet)
    
    qr = qrcode.QRCode()
    qr.add_data(connect_request)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")
    qr_path = f"qr_{chat_id}.png"
    qr_img.save(qr_path)
    
    return qr_path, connect_request

async def get_wallet_address(connector):
    """
    Получает адрес кошелька после подключения.
    """
    timeout = 300
    elapsed = 0
    while not connector.connected and elapsed < timeout:
        await asyncio.sleep(1)
        elapsed += 1
    
    if connector.connected:
        wallet_info = connector.account
        return wallet_info.address
    else:
        raise TonConnectError("Кошелёк не подключён в течение 5 минут")

async def disconnect_wallet(connector):
    """
    Отключает кошелёк.
    """
    if connector.connected:
        await connector.disconnect()

def get_wallet_options(chat_id):
    """
    Возвращает список кошельков и их ссылки для подключения.
    """
    wallets = {
        "Tonkeeper": {
            "name": "Tonkeeper",
            "deeplink": f"https://tonkeeper.com/ton-connect?chat_id={chat_id}",
            "qr_code": f"https://api.qrserver.com/v1/create-qr-code/?data=https://tonkeeper.com/ton-connect?chat_id={chat_id}"
        },
        "MyTonWallet": {
            "name": "MyTonWallet",
            "deeplink": f"https://connect.mytonwallet.org/?chat_id={chat_id}",
            "qr_code": f"https://api.qrserver.com/v1/create-qr-code/?data=https://connect.mytonwallet.org/?chat_id={chat_id}"
        },
        
    }
    return wallets
