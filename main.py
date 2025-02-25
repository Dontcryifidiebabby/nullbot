import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
)
from ton_connect import TONConnectHandler

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния разговора
WALLET_SELECTION, CONNECT_WALLET = range(2)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Запускает бота и предлагает выбрать кошелёк."""
    keyboard = [
        [InlineKeyboardButton("Tonkeeper", callback_data="Tonkeeper")],
        [InlineKeyboardButton("TON Wallet", callback_data="TON Wallet")],
        [InlineKeyboardButton("MyTonWallet", callback_data="MyTonWallet")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Привет! Выбери кошелёк для подключения:", reply_markup=reply_markup
    )
    return WALLET_SELECTION

async def handle_wallet_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает выбор кошелька и отправляет QR-код."""
    query = update.callback_query
    await query.answer()

    wallet_name = query.data
    chat_id = query.message.chat_id

    try:
        ton_handler = TONConnectHandler()
        qr_path, deeplink, connector = ton_handler.generate_connect_link(chat_id, wallet_name)

        # Сохраняем connector в context для дальнейшего использования
        context.user_data["connector"] = connector

        # Отправляем QR-код и deeplink
        with open(qr_path, "rb") as qr_file:
            await query.message.reply_photo(photo=qr_file, caption="Отсканируй QR-код для подключения кошелька.")
        await query.message.reply_text(f"Или используй ссылку: {deeplink}")

        return CONNECT_WALLET

    except Exception as e:
        await query.message.reply_text(f"Ошибка: {str(e)}")
        return ConversationHandler.END

async def check_wallet_connection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Проверяет подключение кошелька."""
    query = update.callback_query
    await query.answer()

    connector = context.user_data.get("connector")
    if not connector:
        await query.message.reply_text("Ошибка: сессия подключения утеряна. Начни заново с /start.")
        return ConversationHandler.END

    try:
        ton_handler = TONConnectHandler()
        is_connected = await ton_handler.check_connection(connector)
        if is_connected:
            wallet_address = ton_handler.get_wallet_address(connector)
            await query.message.reply_text(f"Кошелёк подключён! Адрес: {wallet_address}")
        else:
            await query.message.reply_text("Кошелёк ещё не подключён. Попробуй снова.")
        return ConversationHandler.END

    except Exception as e:
        await query.message.reply_text(f"Ошибка проверки: {str(e)}")
        return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отменяет процесс подключения."""
    await update.message.reply_text("Процесс подключения отменён.")
    return ConversationHandler.END

def main() -> None:
    """Запускает бота."""
    # Замени 'YOUR_TOKEN' на токен твоего бота
    application = Application.builder().token("8094518471:AAGbq7pF75_LXMrO8DL7vbOg9F3czNImUPM").build()

    # Настройка ConversationHandler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            WALLET_SELECTION: [CallbackQueryHandler(handle_wallet_selection)],
            CONNECT_WALLET: [CallbackQueryHandler(check_wallet_connection)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=True,  # Устраняем предупреждение PTBUserWarning
    )

    application.add_handler(conv_handler)

    # Обработка ошибок
    application.add_error_handler(lambda update, context: logger.error(f"Ошибка: {context.error}"))

    # Запуск бота
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
