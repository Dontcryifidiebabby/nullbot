# main.py
import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from ton_connect import TONConnectHandler
from api_handlers import (
    buy_token_gaspump,
    buy_token_stonfi,
    buy_token_dedust,
    check_dev_wallet,
    sell_token_stonfi,
)
from config import BOT_TOKEN

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

WALLET_SELECTION, CONNECT_WALLET, MONITOR_WALLET, BUY_TOKEN, SET_TOKEN = range(5)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    keyboard = [
        [InlineKeyboardButton("Tonkeeper", callback_data="Tonkeeper")],
        [InlineKeyboardButton("TON Wallet", callback_data="TON Wallet")],
        [InlineKeyboardButton("MyTonWallet", callback_data="MyTonWallet")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выбери кошелёк:", reply_markup=reply_markup)
    return WALLET_SELECTION

async def handle_wallet_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    wallet_name = query.data
    chat_id = query.message.chat_id

    try:
        ton_handler = TONConnectHandler()
        qr_path, deeplink, connector = ton_handler.generate_connect_link(chat_id, wallet_name)
        context.user_data["ton_handler"] = ton_handler
        context.user_data["connector"] = connector

        with open(qr_path, "rb") as qr_file:
            await query.message.reply_photo(photo=qr_file, caption="Отсканируй QR-код.")
        await query.message.reply_text(f"Ссылка: {deeplink}")
        return CONNECT_WALLET
    except Exception as e:
        await query.message.reply_text(f"Ошибка: {str(e)}")
        return ConversationHandler.END

async def check_wallet_connection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    connector = context.user_data.get("connector")
    ton_handler = context.user_data.get("ton_handler")

    if not connector or not ton_handler:
        await query.message.reply_text("Сессия утеряна. Начни заново с /start.")
        return ConversationHandler.END

    try:
        is_connected = await ton_handler.check_connection(connector)
        if is_connected:
            wallet_address = ton_handler.get_wallet_address(connector)
            context.user_data["wallet_address"] = wallet_address
            await query.message.reply_text(f"Кошелёк подключён: {wallet_address}\nУкажи адрес разработчика:")
            return MONITOR_WALLET
        else:
            await query.message.reply_text("Кошелёк не подключён.")
            return ConversationHandler.END
    except Exception as e:
        await query.message.reply_text(f"Ошибка: {str(e)}")
        return ConversationHandler.END

async def set_dev_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    dev_address = update.message.text
    context.user_data["dev_address"] = dev_address
    await update.message.reply_text(
        f"Кошелёк разработчика: {dev_address}\n"
        "Укажи токен для автопродажи (например, EQ...) или отправь покупку: <платформа> <адрес_токена> <сумма_TON>"
    )
    return SET_TOKEN

async def set_token_to_sell(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    token_address = update.message.text
    context.user_data["token_to_sell"] = token_address
    await update.message.reply_text(
        f"Токен для автопродажи: {token_address}\n"
        "Отправь покупку: <платформа> <адрес_токена> <сумма_TON> (например, stonfi EQ... 1.5)"
    )
    asyncio.create_task(monitor_dev_wallet(update, context))
    return BUY_TOKEN

async def buy_token(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        platform, token_address, amount_ton = update.message.text.split()
        amount_ton = float(amount_ton)
        wallet_address = context.user_data["wallet_address"]

        if platform.lower() == "gaspump":
            result = await buy_token_gaspump(token_address, amount_ton, wallet_address)
        elif platform.lower() == "stonfi":
            result = await buy_token_stonfi(token_address, amount_ton, wallet_address)
        elif platform.lower() == "dedust":
            result = await buy_token_dedust(token_address, amount_ton, wallet_address)
        else:
            result = "Неизвестная платформа. Используй: gaspump, stonfi, dedust."

        await update.message.reply_text(result)
        return BUY_TOKEN
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {str(e)}")
        return BUY_TOKEN

async def monitor_dev_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    dev_address = context.user_data.get("dev_address")
    wallet_address = context.user_data["wallet_address"]
    token_to_sell = context.user_data.get("token_to_sell", "EQ...default")  # Дефолтный токен, если не указан
    while True:
        try:
            if await check_dev_wallet(dev_address, token_to_sell):
                result = await sell_token_stonfi(token_to_sell, 1.0, wallet_address)
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=f"Обнаружено пополнение!\n{result}"
                )
            await asyncio.sleep(60)  # Проверка каждые 60 секунд
        except Exception as e:
            logger.error(f"Ошибка мониторинга: {str(e)}")
            await asyncio.sleep(60)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Процесс отменён.")
    return ConversationHandler.END

def main() -> None:
    application = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            WALLET_SELECTION: [CallbackQueryHandler(handle_wallet_selection)],
            CONNECT_WALLET: [CallbackQueryHandler(check_wallet_connection)],
            MONITOR_WALLET: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_dev_wallet)],
            SET_TOKEN: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_token_to_sell)],
            BUY_TOKEN: [MessageHandler(filters.TEXT & ~filters.COMMAND, buy_token)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=True,
    )

    application.add_handler(conv_handler)
    application.add_error_handler(lambda update, context: logger.error(f"Ошибка: {context.error}"))

    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
