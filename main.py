from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler, CallbackQueryHandler
import config
import api_handlers
import ton_connect
import asyncio
import os
import httpx

# Проверка версии библиотеки (только вывод)
import telegram
print(f"Using python-telegram-bot version: {telegram.__version__}")

# Состояния разговора
WALLET_CONNECT, TOKEN_ADDRESS, TON_AMOUNT, DEV_WALLET, CONFIRM_BUY, CONFIRM_SELL = range(6)

# Глобальный словарь для TON Connect
connectors = {}

# Команда /start
async def start(update: Update, context):
    await update.message.reply_text(
        "Привет! Это бот для торговли на TON (mainnet).\n"
        "Сначала подключи кошелёк: /connect\n"
        "Команды:\n"
        "1. /buy - Купить токен за TON\n"
        "2. /track - Отслеживать кошелёк разработчика"
    )
    return ConversationHandler.END

# Подключение кошелька
async def connect(update: Update, context):
    wallets = ton_connect.get_wallet_options(update.message.chat_id)
    keyboard = [
        [InlineKeyboardButton(wallet["name"], callback_data=f"wallet_{wallet_name}")]
        for wallet_name, wallet in wallets.items()
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выберите кошелёк для подключения:", reply_markup=reply_markup)
    return WALLET_CONNECT

# Обработчик выбора кошелька
async def handle_wallet_selection(update: Update, context):
    query = update.callback_query
    await query.answer()

    wallet_name = query.data.replace("wallet_", "")
    wallets = ton_connect.get_wallet_options(query.message.chat_id)
    selected_wallet = wallets.get(wallet_name)

    if selected_wallet:
        await query.message.reply_photo(
            photo=selected_wallet["qr_code"],
            caption=f"Сканируйте QR-код или перейдите по ссылке для подключения кошелька {selected_wallet['name']}:\n{selected_wallet['deeplink']}"
        )
    else:
        await query.message.reply_text("Ошибка: кошелёк не найден.")

    return ConversationHandler.END

# Начало покупки
async def buy(update: Update, context):
    if "wallet_address" not in context.user_data:
        await update.message.reply_text("Подключи кошелёк через /connect")
        return ConversationHandler.END
    await update.message.reply_text("Введи адрес токена, который хочешь купить за TON (EQ...):")
    return TOKEN_ADDRESS

# Получение адреса токена
async def get_token_address(update: Update, context):
    context.user_data["token_address"] = update.message.text
    await update.message.reply_text("Сколько TON ты хочешь потратить?")
    return TON_AMOUNT

# Получение суммы TON
async def get_ton_amount(update: Update, context):
    try:
        ton_amount = float(update.message.text)
        if ton_amount <= 0:
            raise ValueError
        context.user_data["ton_amount"] = ton_amount
    except ValueError:
        await update.message.reply_text("Введи корректное число больше 0!")
        return TON_AMOUNT
    keyboard = [
        [InlineKeyboardButton("GasPump", callback_data="gaspump"),
         InlineKeyboardButton("Ston.fi", callback_data="stonfi"),
         InlineKeyboardButton("DeDust", callback_data="dedust")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выбери платформу:", reply_markup=reply_markup)
    return CONFIRM_BUY

# Подтверждение покупки
async def confirm_buy(update: Update, context):
    query = update.callback_query
    await query.answer()
    platform = query.data
    token_address = context.user_data["token_address"]
    ton_amount = context.user_data["ton_amount"]
    wallet_address = context.user_data["wallet_address"]

    if platform == "gaspump":
        result = api_handlers.buy_token_gaspump(token_address, ton_amount, wallet_address)
    elif platform == "stonfi":
        result = api_handlers.buy_token_stonfi(token_address, ton_amount, wallet_address)
    else:  # dedust
        result = api_handlers.buy_token_dedust(token_address, ton_amount, wallet_address)

    await query.edit_message_text(result)
    return ConversationHandler.END

# Начало отслеживания
async def track(update: Update, context):
    if "wallet_address" not in context.user_data:
        await update.message.reply_text("Подключи кошелёк через /connect")
        return ConversationHandler.END
    await update.message.reply_text("Введи адрес кошелька разработчика (EQ...):")
    return DEV_WALLET

# Получение адреса разработчика
async def get_dev_wallet(update: Update, context):
    context.user_data["dev_wallet"] = update.message.text
    await update.message.reply_text("Введи адрес токена, который хочешь продать за TON (EQ...):")
    return CONFIRM_SELL

# Отслеживание и продажа
async def confirm_sell(update: Update, context):
    context.user_data["token_address"] = update.message.text
    dev_wallet = context.user_data["dev_wallet"]
    token_address = context.user_data["token_address"]
    wallet_address = context.user_data["wallet_address"]
    
    await update.message.reply_text("Отслеживаю кошелёк разработчика...")

    async def monitor_and_sell():
        while True:
            if await api_handlers.check_dev_wallet(dev_wallet):
                result = api_handlers.sell_token_stonfi(token_address, 100, wallet_address)
                await context.bot.send_message(chat_id=update.message.chat_id, text=result)
                break
            await asyncio.sleep(10)

    asyncio.create_task(monitor_and_sell())
    return ConversationHandler.END

# Отмена
async def cancel(update: Update, context):
    await update.message.reply_text("Отменено.")
    return ConversationHandler.END

# Главная функция
def main():
    # Настройка HTTP-клиента с увеличенным тайм-аутом и прокси (если нужно)
    http_client = httpx.AsyncClient(
        timeout=60.0,  # Увеличиваем тайм-аут до 60 секунд
        # proxies=config.PROXY_URL  # Раскомментируй, если нужен прокси
    )
    
    # Создание приложения с кастомным HTTP-клиентом
    application = Application.builder().token(config.BOT_TOKEN).build()

    # Обработчики
    conv_handler_buy = ConversationHandler(
        entry_points=[CommandHandler("buy", buy)],
        states={
            TOKEN_ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_token_address)],
            TON_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_ton_amount)],
            CONFIRM_BUY: [CallbackQueryHandler(confirm_buy)]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    conv_handler_track = ConversationHandler(
        entry_points=[CommandHandler("track", track)],
        states={
            DEV_WALLET: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_dev_wallet)],
            CONFIRM_SELL: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_sell)]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    conv_handler_connect = ConversationHandler(
        entry_points=[CommandHandler("connect", connect)],
        states={
            WALLET_CONNECT: [CallbackQueryHandler(handle_wallet_selection, pattern="^wallet_")]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(conv_handler_connect)
    application.add_handler(conv_handler_buy)
    application.add_handler(conv_handler_track)

    application.run_polling()

if __name__ == "__main__":
    main()