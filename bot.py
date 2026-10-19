# -*- coding: utf-8 -*-
# PhoenixCheat Bot V13 - DB Fix

import json
import os
import random
import string
import threading
from datetime import datetime

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler

BOT_TOKEN = "8699196899:AAGaY7pFzU2OzBxwcF8_E-LqUbQZk4UUDgo"
ADMIN_ID = 8113206201
GROUP_ID = -1004335107809

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data.json")
app_web = Flask(__name__, static_folder=BASE_DIR)
CORS(app_web)
bot_app = None

# ================= دیتابیس استاندارد =================
DEFAULT_DATA = {
    "orders": [],
    "next_order_id": 1,
    "settings": {
        "card_number": "6219861452724577",
        "card_holder": "یوسف موسوی",
        "price_per_1000": 25000,
        "price_antiban": 50000,
        "price_fast": 20000
    },
    "coupons": [],
    "texts": {
        "site_name": "PhoenixCheat",
        "welcome_title": "به فروشگاه PhoenixCheat خوش آمدید",
        "welcome_text1": "ما مفتخریم که به عنوان یکی از پیشگامان و معتبرترین مراجع تخصصی در حوزه خدمات گیمینگ (به‌ویژه Call of Duty) در خدمت شما هستیم.",
        "welcome_text2": "تیم متخصص ما با تکیه بر دانش فنی و تجربه چندین ساله، بستری امن، سریع و تضمینی را برای ارتقاء تجربه بازی شما فراهم کرده است.",
        "about_text": "ما یه تیم حرفه‌ای از گیمرهای کالاف دیوتی هستیم.",
        "trust_text": "✓ بیش از ۵۰۰ مشتری راضی\n✓ چنل اعتماد فعال\n✓ پشتیبانی ۲۴/۷"
    }
}

def load_data():
    try:
        with open(DB_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            # چک کردن سالم بودن دیتابیس (دیباگ)
            if "orders" not in data or "settings" not in data:
                raise ValueError("Old DB Format")
            return data
    except:
        print("⚠️ [DEBUG] Old or broken DB detected. Creating new one.")
        save_data(DEFAULT_DATA)
        return DEFAULT_DATA

def save_data(data):
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def make_code():
    return f"ORD-{''.join(random.choices(string.ascii_uppercase + string.digits, k=6))}"

# ================= API سایت =================
@app_web.route("/")
def index(): return send_from_directory(BASE_DIR, "index.html")

@app_web.route("/api/settings", methods=["GET"])
def get_settings():
    db = load_data()
    return jsonify({"texts": db.get("texts", {}), "settings": db.get("settings", {})})

@app_web.route("/api/check_coupon", methods=["POST"])
def check_coupon():
    code = request.get_json().get("code", "").upper()
    for c in load_data().get("coupons", []):
        if c["code"] == code and c["active"]:
            return jsonify({"success": True, "discount": c["discount"]})
    return jsonify({"success": False, "message": "کد نامعتبر"}), 400

@app_web.route("/register", methods=["POST"])
def register():
    try:
        data = request.get_json()
        db = load_data()
        oid = db.get("next_order_id", 1)
        
        order = {
            "id": oid, "code": make_code(),
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "email": data.get("email", ""), "pass": data.get("pass", ""),
            "rubika": data.get("rubika", ""), "desc": data.get("desc", ""),
            "cp": int(data.get("cp", 0)), "antiban": data.get("antiban", False),
            "speed": data.get("speed", "normal"), "total_price": int(data.get("totalPrice", 0)),
            "sender_card": data.get("senderCard", ""), "sent_amount": data.get("sentAmount", ""),
            "sent_time": data.get("sentTime", ""), "status": "pending"
        }
        
        db["orders"].append(order)
        db["next_order_id"] = oid + 1
        save_data(db)
        
        threading.Thread(target=send_to_telegram, args=(order,), daemon=True).start()
        return jsonify({"success": True, "code": order["code"]})
    except Exception as e:
        print(f"❌ [DEBUG] Register error: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

# ================= ارسال به تلگرام =================
def send_to_telegram(order):
    if not bot_app: return
    try:
        import asyncio
        speed_text = "فوری" if order['speed'] == 'fast' else "زمان‌بر"
        antiban_text = "✅ دارد" if order['antiban'] else "❌ ندارد"
        
        text = (
            f"🛒 **سفارش جدید!**\n\n"
            f"🔢 کد: `{order['code']}`\n"
            f"📅 {order['date']}\n\n"
            f"👤 **اکانت:**\n"
            f"📧 `{order['email']}`\n"
            f"🔑 `{order['pass']}`\n"
            f"💬 {order['rubika']}\n"
            f"📝 {order['desc'] or 'ندارد'}\n\n"
            f"💎 **سفارش:**\n"
            f"🔹 {order['cp']:,} CP\n"
            f"🛡️ {antiban_text} | ⚡ {speed_text}\n"
            f"💰 {order['total_price']:,} تومان\n\n"
            f"💳 **واریز:**\n"
            f"🔢 `{order['sender_card']}`\n"
            f"💵 {order['sent_amount']} تومان\n"
            f"⏰ {order['sent_time']}"
        )
        
        keyboard = [[
            InlineKeyboardButton("✅ تأیید", callback_data=f"ok_{order['id']}"),
            InlineKeyboardButton("❌ رد", callback_data=f"no_{order['id']}")
        ]]
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(bot_app.bot.send_message(
            chat_id=GROUP_ID, text=text, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        ))
        loop.close()
    except Exception as e:
        print(f"❌ [DEBUG] Telegram error: {e}")

# ================= ربات =================
async def start(update: Update, ctx):
    if update.effective_user.id != ADMIN_ID: return
    await update.message.reply_text("🎮 ربات متصل است.")

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app_web.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

def main():
    global bot_app
    bot_app = Application.builder().token(BOT_TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    
    threading.Thread(target=run_flask, daemon=True).start()
    bot_app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()