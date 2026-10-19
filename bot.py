# -*- coding: utf-8 -*-
# PhoenixCheat Bot V14 - Full Features + Stable Send

import json
import os
import random
import string
import threading
from datetime import datetime

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from telegram.request import HTTPXRequest

# --- تنظیمات ---
BOT_TOKEN = "8699196899:AAGaY7pFzU2OzBxwcF8_E-LqUbQZk4UUDgo"
ADMIN_ID = 8113206201
GROUP_ID = -1004335107809

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data.json")
app_web = Flask(__name__, static_folder=BASE_DIR)
CORS(app_web)
bot_app = None
USER_STATES = {}

# --- دیتابیس ---
DEFAULT_DATA = {
    "orders": [],
    "next_order_id": 1,
    "stats": {"total_orders": 0, "total_visits": 0},
    "settings": {
        "card_number": "6219861452724577",
        "card_holder": "یوسف موسوی",
        "price_per_1000": 25000,
        "price_antiban": 50000,
        "price_fast": 20000,
        "registration_open": True
    },
    "coupons": [],
    "texts": {
        "site_name": "PhoenixCheat",
        "welcome_title": "به فروشگاه PhoenixCheat خوش آمدید",
        "welcome_text1": "ما مفتخریم که به عنوان یکی از پیشگامان و معتبرترین مراجع تخصصی در حوزه خدمات گیمینگ (به‌ویژه Call of Duty) در خدمت شما هستیم.",
        "welcome_text2": "تیم متخصص ما با تکیه بر دانش فنی و تجربه چندین ساله، بستری امن، سریع و تضمینی را برای ارتقاء تجربه بازی شما فراهم کرده است. هدف ما ارائه بهترین کیفیت با بالاترین ضریب امنیت (بدون بن) و پشتیبانی ۲۴ ساعته است تا با خیالی آسوده بازی خود را به سطح حرفه‌ای ببرید.",
        "features": ["بدون بن و کاملاً امن", "تحویل سریع و رایگان", "پشتیبانی ۲۴ ساعته"],
        "about_text": "ما یه تیم حرفه‌ای از گیمرهای کالاف دیوتی هستیم.",
        "trust_text": "✓ بیش از ۵۰۰ مشتری راضی\n✓ چنل اعتماد فعال\n✓ پشتیبانی ۲۴/۷",
        "channel_link": "https://rubika.ir/PhoenixCheat",
        "support_link": "https://rubika.ir/my_hinata",
        "telegram_link": "https://t.me/Phoenix1Cheat",
        "site_status": "open"
    }
}

def load_data():
    try:
        with open(DB_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            if "orders" not in data or "settings" not in data:
                raise ValueError("Old DB")
            return data
    except:
        save_data(DEFAULT_DATA)
        return DEFAULT_DATA

def save_data(data):
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def make_code():
    return f"ORD-{''.join(random.choices(string.ascii_uppercase + string.digits, k=6))}"

# ================= API های سایت =================
@app_web.route("/")
def index(): return send_from_directory(BASE_DIR, "index.html")

@app_web.route("/api/settings", methods=["GET"])
def get_settings():
    db = load_data()
    return jsonify({"texts": db.get("texts", {}), "settings": db.get("settings", {})})

@app_web.route("/api/check_coupon", methods=["POST"])
def check_coupon():
    code = request.get_json().get("code", "").strip().upper()
    for c in load_data().get("coupons", []):
        if c["code"] == code and c["active"]:
            return jsonify({"success": True, "discount": c["discount"]})
    return jsonify({"success": False, "message": "کد نامعتبر"}), 400

@app_web.route("/register", methods=["POST"])
def register():
    try:
        data = request.get_json()
        db = load_data()
        
        discount = 0
        coupon_code = data.get("coupon", "").upper()
        if coupon_code:
            for c in db.get("coupons", []):
                if c["code"] == coupon_code and c["active"]:
                    discount = c["discount"]
                    break

        oid = db.get("next_order_id", 1)
        order = {
            "id": oid, "code": make_code(),
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "email": data.get("email", ""), "pass": data.get("pass", ""),
            "rubika": data.get("rubika", ""), "desc": data.get("desc", ""),
            "cp": int(data.get("cp", 0)), "antiban": data.get("antiban", False),
            "speed": data.get("speed", "normal"), "total_price": int(data.get("totalPrice", 0)),
            "sender_card": data.get("senderCard", ""), "sent_amount": data.get("sentAmount", ""),
            "sent_time": data.get("sentTime", ""), "discount": discount, "status": "pending"
        }
        
        db["orders"].append(order)
        db["next_order_id"] = oid + 1
        db["stats"]["total_orders"] = db["stats"].get("total_orders", 0) + 1
        save_data(db)
        
        threading.Thread(target=send_order_to_telegram, args=(order,), daemon=True).start()
        return jsonify({"success": True, "code": order["code"]})
    except Exception as e:
        print(f"❌ [DEBUG] Register error: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

# ================= ارسال پایدار =================
def send_order_to_telegram(order):
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
            f"💰 {order['total_price']:,} تومان\n"
            f"🎟️ تخفیف: {order['discount']}%\n\n"
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

# ================= پنل ادمین (همه گزینه‌ها) =================
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    keyboard = [
        [InlineKeyboardButton("📦 سفارشات", callback_data="list_orders")],
        [InlineKeyboardButton("📊 آمار کامل", callback_data="stats")],
        [InlineKeyboardButton("🔍 جستجوی مشتری", callback_data="search_user")],
        [InlineKeyboardButton("🎟️ کدهای تخفیف", callback_data="coupons_menu")],
        [InlineKeyboardButton("💳 تنظیمات کارت", callback_data="set_card_info")],
        [InlineKeyboardButton("💰 تنظیم نرخ قیمت", callback_data="set_prices")],
        [InlineKeyboardButton("🔐 باز/بسته ثبت‌نام", callback_data="toggle_reg")],
        [InlineKeyboardButton("🔧 وضعیت", callback_data="status")],
    ]
    await update.message.reply_text(
        "🎮 PhoenixCheat Admin Panel\n\nیک گزینه را انتخاب کن:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def button_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    db = load_data()

    if data == "list_orders":
        orders = db.get("orders", [])
        text = f"📦 **آخرین سفارشات ({len(orders)} کل):**\n\n"
        for o in orders[-5:]:
            status = "⏳" if o['status'] == 'pending' else ("✅" if o['status'] == 'accepted' else "❌")
            text += f"{status} `{o['code']}` | {o['email'][:15]} | {o['total_price']:,} ت\n"
        keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="back")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "stats":
        users = len(db.get("orders", []))
        text = (
            f"📊 **آمار کامل سیستم**\n\n"
            f"📦 کل سفارشات: {users}\n"
            f"👁️ بازدید سایت: {db.get('stats', {}).get('total_visits', 0)}\n"
            f"🎟️ کدهای فعال: {len([c for c in db.get('coupons', []) if c['active']])}\n"
        )
        keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="back")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "search_user":
        USER_STATES[ADMIN_ID] = {"state": "waiting_search"}
        await query.edit_message_text("🔍 ایمیل یا کد سفارش کاربر را وارد کنید:")

    elif data == "coupons_menu":
        keyboard = [
            [InlineKeyboardButton("➕ ساخت کد جدید", callback_data="add_coupon_info")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="back")]
        ]
        text = "🎟️ **مدیریت کدهای تخفیف**\n\nکدهای فعال: "
        text += ", ".join([c['code'] for c in db.get("coupons", []) if c['active']]) or "ندارد"
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "add_coupon_info":
        await query.edit_message_text("برای ساخت کد تخفیف دستور زیر را بفرستید:\n\n`/addcoupon CODE PERCENT`\n\nمثال: `/addcoupon CHEAT10 10`", parse_mode="Markdown")

    elif data == "set_card_info":
        card = db["settings"].get("card_number", "")
        holder = db["settings"].get("card_holder", "")
        await query.edit_message_text(
            f"💳 **تنظیم کارت**\n\nفعلی: `{card}`\nبه نام: {holder}\n\n"
            f"برای تغییر:\n`/setcard 6219... - نام صاحب کارت`", parse_mode="Markdown"
        )

    elif data == "set_prices":
        s = db["settings"]
        text = (
            f"💰 **تنظیم نرخ قیمت**\n\n"
            f"هر ۱۰۰۰ سی‌پی: {s.get('price_per_1000', 25000):,} ت\n"
            f"انتی بن: {s.get('price_antiban', 50000):,} ت\n"
            f"فوری: {s.get('price_fast', 20000):,} ت\n\n"
            f"برای تغییر:\n"
            f"`/setprice per_1000 25000`\n"
            f"`/setprice antiban 50000`\n"
            f"`/setprice fast 20000`"
        )
        keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="back")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "toggle_reg":
        status = db["settings"].get("registration_open", True)
        db["settings"]["registration_open"] = not status
        save_data(db)
        emoji = "🟢" if not status else "🔴"
        await query.edit_message_text(f"{emoji} ثبت‌نام سایت: {'باز' if not status else 'بسته'} شد.")
    
    elif data == "status":
        text = "🔧 سیستم آنلاین است."
        keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="back")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "back":
        keyboard = [
            [InlineKeyboardButton("📦 سفارشات", callback_data="list_orders")],
            [InlineKeyboardButton("📊 آمار کامل", callback_data="stats")],
            [InlineKeyboardButton("🔍 جستجوی مشتری", callback_data="search_user")],
            [InlineKeyboardButton("🎟️ کدهای تخفیف", callback_data="coupons_menu")],
            [InlineKeyboardButton("💳 تنظیمات کارت", callback_data="set_card_info")],
            [InlineKeyboardButton("💰 تنظیم نرخ قیمت", callback_data="set_prices")],
            [InlineKeyboardButton("🔐 باز/بسته ثبت‌نام", callback_data="toggle_reg")],
            [InlineKeyboardButton("🔧 وضعیت", callback_data="status")],
        ]
        await query.edit_message_text("🎮 PhoenixCheat Admin Panel", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("ok_"):
        await query.edit_message_text(f"✅ سفارش تایید شد.")
    elif data.startswith("no_"):
        await query.edit_message_text(f"❌ سفارش رد شد.")

# ================= دستورات متنی =================
async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    state = USER_STATES.get(ADMIN_ID, {}).get("state")
    text = update.message.text.strip()
    
    if state == "waiting_search":
        db = load_data()
        found = [o for o in db["orders"] if text.lower() in o["email"].lower() or text.upper() in o["code"]]
        if found:
            msg = "🔍 نتایج:\n\n"
            for o in found:
                msg += f"`{o['code']}` | {o['email']}\n"
            await update.message.reply_text(msg, parse_mode="Markdown")
        else:
            await update.message.reply_text("❌ پیدا نشد.")
        USER_STATES.pop(ADMIN_ID, None)

async def set_card(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        txt = update.message.text.replace("/setcard ", "").split("-")
        db = load_data()
        db["settings"]["card_number"] = txt[0].strip()
        db["settings"]["card_holder"] = txt[1].strip()
        save_data(db)
        await update.message.reply_text("✅ کارت تغییر کرد.")
    except: await update.message.reply_text("❌ فرمت: /setcard 6219... - نام")

async def set_price(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        parts = update.message.text.replace("/setprice ", "").split()
        key, val = parts[0], int(parts[1])
        db = load_data()
        if key == "per_1000": db["settings"]["price_per_1000"] = val
        elif key == "antiban": db["settings"]["price_antiban"] = val
        elif key == "fast": db["settings"]["price_fast"] = val
        save_data(db)
        await update.message.reply_text("✅ قیمت تغییر کرد.")
    except: await update.message.reply_text("❌ فرمت: /setprice per_1000 25000")

async def add_coupon(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        parts = update.message.text.replace("/addcoupon ", "").split()
        code, percent = parts[0].upper(), int(parts[1])
        db = load_data()
        if "coupons" not in db: db["coupons"] = []
        db["coupons"].append({"code": code, "discount": percent, "active": True})
        save_data(db)
        await update.message.reply_text(f"✅ کد {code} ساخته شد.")
    except: await update.message.reply_text("❌ فرمت: /addcoupon CODE 10")

# ================= اجرا =================
def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app_web.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

def main():
    global bot_app
    bot_app = Application.builder().token(BOT_TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CommandHandler("setcard", set_card))
    bot_app.add_handler(CommandHandler("setprice", set_price))
    bot_app.add_handler(CommandHandler("addcoupon", add_coupon))
    bot_app.add_handler(CallbackQueryHandler(button_handler))
    bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    threading.Thread(target=run_flask, daemon=True).start()
    bot_app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()