import logging
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    KeyboardButton, ReplyKeyboardMarkup
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from places import search_places, format_place, build_map_links
from config import TELEGRAM_TOKEN

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def geocode_address(address: str):
    import requests
    from config import GOOGLE_API_KEY
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {"address": address, "key": GOOGLE_API_KEY}
    resp = requests.get(url, params=params).json()
    if resp.get("results"):
        loc = resp["results"][0]["geometry"]["location"]
        return loc["lat"], loc["lng"]
    return None


def category_filter_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🌳 Outdoors", callback_data="cat:outdoors"),
        InlineKeyboardButton("🏠 Indoors", callback_data="cat:indoors"),
    ]])


def refilter_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🔄 Change Filter", callback_data="refilter"),
        InlineKeyboardButton("📍 Change Location", callback_data="change_location"),
    ]])


def map_links_keyboard(place: dict) -> InlineKeyboardMarkup:
    links = build_map_links(place)
    buttons = [InlineKeyboardButton(label, url=url) for label, url in links]
    return InlineKeyboardMarkup([buttons])


# ── Handlers ──────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    keyboard = [
        [KeyboardButton("📍 Share My Location", request_location=True)],
        [KeyboardButton("🔍 Enter Location Manually")],
    ]
    await update.message.reply_text(
        "👶 *Welcome to the Toddler Places Bot!*\n\n"
        "I'll help you find toddler-friendly spots nearby.\n"
        "Share your location or type an address to get started!",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
    )


async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    loc = update.message.location
    context.user_data["lat"] = loc.latitude
    context.user_data["lng"] = loc.longitude
    context.user_data["awaiting_manual_location"] = False
    await update.message.reply_text(
        "📍 Location received! Are you looking for *outdoor* or *indoor* places?",
        parse_mode="Markdown",
        reply_markup=category_filter_keyboard(),
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "🔍 Enter Location Manually":
        context.user_data["awaiting_manual_location"] = True
        await update.message.reply_text(
            "Please type your address or area name\n(e.g. *Tampines, Singapore*) :",
            parse_mode="Markdown",
        )
        return

    if context.user_data.get("awaiting_manual_location"):
        context.user_data["awaiting_manual_location"] = False
        await update.message.reply_text("🔎 Looking up your location...")
        coords = geocode_address(text)
        if not coords:
            await update.message.reply_text(
                "❌ Couldn't find that location. Please try a more specific address."
            )
            context.user_data["awaiting_manual_location"] = True
            return
        context.user_data["lat"], context.user_data["lng"] = coords
        await update.message.reply_text(
            "✅ Got it! Are you looking for *outdoor* or *indoor* places?",
            parse_mode="Markdown",
            reply_markup=category_filter_keyboard(),
        )


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    chat_id = query.message.chat_id

    if data == "refilter":
        await context.bot.send_message(
            chat_id=chat_id,
            text="🔄 Switch filter — are you looking for *outdoor* or *indoor* places?",
            parse_mode="Markdown",
            reply_markup=category_filter_keyboard(),
        )
        return

    if data == "change_location":
        context.user_data.clear()
        keyboard = [
            [KeyboardButton("📍 Share My Location", request_location=True)],
            [KeyboardButton("🔍 Enter Location Manually")],
        ]
        await context.bot.send_message(
            chat_id=chat_id,
            text="📍 Sure! Please share your new location:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
        )
        return

    if data.startswith("cat:"):
        category = data.split(":")[1]
        lat = context.user_data.get("lat")
        lng = context.user_data.get("lng")

        if not lat or not lng:
            await context.bot.send_message(
                chat_id=chat_id,
                text="❌ No location found. Please tap /start to begin again."
            )
            return

        emoji = "🌳" if category == "outdoors" else "🏠"
        label = "outdoor" if category == "outdoors" else "indoor"

        await query.edit_message_text(
            f"{emoji} Searching for *{label}* toddler-friendly places near you...",
            parse_mode="Markdown",
        )

        places = search_places(lat, lng, category)

        if not places:
            await context.bot.send_message(
                chat_id=chat_id,
                text="😕 No places found nearby.\nTry switching the filter or a different location.",
                reply_markup=refilter_keyboard(),
            )
            return

        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                f"{emoji} *Top {len(places)} {label} places nearby*\n"
                f"_Sorted by distance, closest first:_"
            ),
            parse_mode="Markdown",
        )

        for i, place in enumerate(places, start=1):
            await context.bot.send_message(
                chat_id=chat_id,
                text=format_place(place, i),
                parse_mode="Markdown",
                reply_markup=map_links_keyboard(place),
            )

        await context.bot.send_message(
            chat_id=chat_id,
            text="Want to explore more?",
            reply_markup=refilter_keyboard(),
        )


# ── Register handlers ─────────────────────────────────────────────────────────

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.LOCATION, handle_location))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(handle_callback))

    logger.info("Bot started in polling mode...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
