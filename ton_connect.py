# ton_connect.py
import qrcode
from tonsdk.utils import Address
from tonconnect import TonConnect
from tonconnect.exception import TonConnectError
from config import TON_CONNECT_MANIFEST_URL

class TONConnectHandler:
    def __init__(self):
        self.connector = TonConnect(manifest_url=TON_CONNECT_MANIFEST_URL)

    def generate_connect_link(self, chat_id: int, wallet_name: str) -> tuple[str, str, TonConnect]:
        try:
            wallets_list = self.connector.get_wallets()
            selected_wallet = next(
                (wallet for wallet in wallets_list if wallet['name'] == wallet_name), None
            )
            if not selected_wallet:
                raise ValueError(f"Кошелёк {wallet_name} не найден.")
            universal_link = self.connector.generate_universal_link(
                wallet_app_id=selected_wallet['app_id'],
                redirect_url=f"https://t.me/NullBot?start=connect_{chat_id}"
            )
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(universal_link)
            qr.make(fit=True)
            qr_path = f"qr_{chat_id}.png"
            qr.make_image(fill_color="black", back_color="white").save(qr_path)
            return qr_path, universal_link, self.connector
        except TonConnectError as e:
            raise Exception(f"Ошибка TON Connect: {str(e)}")
        except Exception as e:
            raise Exception(f"Ошибка генерации: {str(e)}")

    async def check_connection(self, connector: TonConnect) -> bool:
        try:
            return await connector.connected()
        except TonConnectError as e:
            raise Exception(f"Ошибка проверки: {str(e)}")

    def get_wallet_address(self, connector: TonConnect) -> str:
        if connector.account and connector.account.address:
            return Address(connector.account.address).to_string(is_user_friendly=True)
        raise Exception("Кошелёк не подключён.")
