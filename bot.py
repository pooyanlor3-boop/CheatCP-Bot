# -*- coding: utf-8 -*-
# PhoenixCheat Bot V10 - Final Stable (No IP, Full Debug)

import json
import os
import random
import string
import threading
from datetime import datetime

from dotenv import load_dotenv
load_dotenv()

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)
from telegram.request import HTTPXRequest

from config import (
    BOT_TOKEN, ADMIN_ID,
    USE_PROXY, PROXY_TYPE, PROXY_HOST, PROXY_PORT,
    CODE_PREFIX, SUPPORT_ID
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data.json")
app_web = Flask(__name__, static_folder=BASE_DIR)
CORS(app_web)
bot_app = None
USER_STATES = {}

# ================= دیتابیس پیش‌فرض =================
DEFAULT_DATA = {
    "users": [],
    "orders": [],
    "next_user_id": 1,
    "next_order_id": 1,
    "stats": {"total_users": 0, "total_visits": 0, "total_orders": 0},
    "settings": {
        "group_id": -1004335107809,
        "registration_open": True,
        "card_number": "6219861452724577",
        "card_holder": "یوسف موسوی",
        "price_per_1000": 25000,
        "price_antiban": 50000,
        "price_fast": 20000
    },
    "coupons": [],
    "texts": {
        "site_name": "PhoenixCheat",
        "site_tagline": "COD STORE",
        "welcome_title": "به فروشگاه PhoenixCheat خوش آمدید",
        "welcome_text1": "ما مفتخریم که به عنوان یکی از پیشگامان و معتبرترین مراجع تخصصی در حوزه خدمات گیمینگ (به‌ویژه Call of Duty) در خدمت شما هستیم.",
        "welcome_text2": "تیم متخصص ما با تکیه بر دانش فنی و تجربه چندین ساله، بستری امن، سریع و تضمینی را برای ارتقاء تجربه بازی شما فراهم کرده است. هدف ما ارائه بهترین کیفیت با بالاترین ضریب امنیت (بدون بن) و پشتیبانی ۲۴ ساعته است تا با خیالی آسوده بازی خود را به سطح حرفه‌ای ببرید. با سیستم‌های پیشرفته ضد بن، تحویل فوری سفارشات و پشتیبانی شبانه‌روزی، فونیکس‌چیت تضمین‌کننده امنیت و موفقیت شما در میدان نبرد است. به خانواده بزرگ ما بپیوندید و قدرتمندتر از همیشه بازی کنید.",
        "features": ["بدون بن و کاملاً امن", "تحویل سریع و رایگان", "پشتیبانی ۲۴ ساعته"],
        "about_text": "ما یه تیم حرفه‌ای از گیمرهای کالاف دیوتی هستیم.",
        "trust_text": "✓ بیش از ۵۰۰ مشتری راضی\n✓ چنل اعتماد فعال\n✓ پشتیبانی ۲۴/۷",
        "channel_link": "https://rubika.ir/PhoenixCheat",
        "support_link": "https://rubika.ir/my_hinata",
        "telegram_link": "https://t.me/Phoenix1Cheat",
        "site_status": "open"
    }
}

# ================= توابع دیتابیس =================
def load_data():
    try:
        with open(DB_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️ DB Load Error: {e} - Creating default.")
        save_data(DEFAULT_DATA)
        return DEFAULT_DATA

def save_data(data):
    try:
        with open(DB_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"❌ DB Save Error: {e}")
        return False

def make_code(prefix="ORD"):
    rand = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"{prefix}-{rand}"

# ================= API های وب‌سایت =================
@app_web.route("/")
def index():
    return send_from_directory(BASE_DIR, "index.html")

@app_web.route("/api/settings", methods=["GET"])
def get_settings():
    db = load_data()
    return jsonify({
        "texts": db.get("texts", {}),
        "settings": db.get("settings", {})
    })

@app_web.route("/api/check_coupon", methods=["POST"])
def check_coupon():
    data = request.get_json()
    code = data.get("code", "").strip().upper()
    db = load_data()
    for c in db.get("coupons", []):
        if c["code"] == code and c["active"]:
            return jsonify({"success": True, "discount": c["discount"]})
    return jsonify({"success": False, "message": "کد نامعتبر است"}), 400

# ثبت سفارش جدید
@app_web.route("/register", methods=["POST"])
def register():
    try:
        data = request.get_json()
        print(f"📥 [DEBUG] New Order Request: {data}") # لاگ برای دیباگ
        
        db = load_data()
        
        # بررسی کد تخفیف
        discount = 0
        coupon_code = data.get("coupon", "").upper()
        if coupon_code:
            for c in db.get("coupons", []):
                if c["code"] == coupon_code and c["active"]:
                    discount = c["discount"]
                    break

        oid = db.get("next_order_id", 1)
        order = {
            "id": oid,
            "code": make_code("ORD"),
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "email": data.get("email", ""),
            "pass": data.get("pass", ""),
            "rubika": data.get("rubika", ""),
            "desc": data.get("desc", ""),
            "cp": int(data.get("cp", 0)),
            "antiban": data.get("antiban", False),
            "speed": data.get("speed", "normal"),
            "total_price": int(data.get("totalPrice", 0)),
            "sender_card": data.get("senderCard", ""),
            "sent_amount": data.get("sentAmount", ""),
            "sent_time": data.get("sentTime", ""),
            "discount": discount,
            "status": "pending"
        }

        db["orders"].append(order)
        db["next_order_id"] = oid + 1
        db["stats"]["total_orders"] = db["stats"].get("total_orders", 0) + 1
        
        if save_data(db):
            print(f"✅ [DEBUG] Order {oid} saved to DB.")
            threading.Thread(target=send_order_to_telegram, args=(order,), daemon=True).start()
            return jsonify({"success": True, "code": order["code"]})
        else:
            print("❌ [DEBUG] Failed to save order to DB.")
            return jsonify({"success": False, "message": "خطا در ذخیره‌سازی"}), 500
            
    except Exception as e:
        print(f"❌ [DEBUG] Register error: {e}")
        return jsonify({"success": False, "message": "خطای داخلی سرور"}), 500

# ================= ارسال به تلگرام =================
def send_order_to_telegram(order):
    global bot_app
    if bot_app is None: return
    db = load_data()
    group_id = db.get("settings", {}).get("group_id")
    if not group_id: 
        print("❌ [DEBUG] Group ID not set.")
        return

    try:
        import asyncio
        speed_text = "فوری (۱۰ دقیقه)" if order['speed'] == 'fast' else "زمان‌بر (۵ ساعت)"
        antiban_text = "✅ دارد" if order['antiban'] else "❌ ندارد"
        
        text = (
            f"🛒 **سفارش جدید ثبت شد!**\n\n"
            f"🔢 کد رهگیری: `{order['code']}`\n"
            f"📅 زمان: {order['date']}\n\n"
            f"👤 **اطلاعات اکانت:**\n"
            f"📧 ایمیل: {order['email']}\n"
            f"🔑 رمز: {order['pass']}\n"
            f"💬 روبیکا: {order['rubika']}\n"
            f"📝 توضیحات: {order['desc'] or 'ندارد'}\n\n"
            f"💎 **مشخصات سفارش:**\n"
            f"🔹 تعداد: {order['cp']:,} CP\n"
            f"🛡️ ضد بن: {antiban_text}\n"
            f"⚡ سرعت: {speed_text}\n"
            f"💰 مبلغ کل: {order['total_price']:,} تومان\n"
            f"🎟️ تخفیف: {order['discount']}%\n\n"
            f"💳 **اطلاعات واریز:**\n"
            f"🔢 کارت مبدا: `{order['sender_card']}`\n"
            f"💵 مبلغ واریزی: {order['sent_amount']} تومان\n"
            f"⏰ ساعت واریز: {order['sent_time']}\n\n"
            f"@Admin"
        )
        
        keyboard = [[
            InlineKeyboardButton("✅ تأیید", callback_data=f"accept_{order['id']}"),
            InlineKeyboardButton("❌ رد", callback_data=f"reject_{order['id']}")
        ]]
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(bot_app.bot.send_message(
            chat_id=group_id, text=text, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        ))
        loop.close()
        print("✅ [DEBUG] Order sent to Telegram successfully.")
    except Exception as e:
        print(f"❌ [DEBUG] Telegram Send error: {e}")

# ================= پنل ادمین =================
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    keyboard = [
        [InlineKeyboardButton("📦 سفارشات", callback_data="list_orders")],
        [InlineKeyboardButton("📊 آمار کامل", callback_data="stats")],
        [InlineKeyboardButton("🔍 جستجوی مشتری", callback_data="search_user")],
        [InlineKeyboardButton("🎟️ کدهای تخفیف", callback_data="coupons_menu")],
        [InlineKeyboardButton("💳 تنظیمات کارت", callback_data="set_card_info")],
        [InlineKeyboardButton("💰 تنظیم نرخ قیمت", callback_data="set_prices")],
        [InlineKeyboardButton("🔧 وضعیت", callback_data="status")],
    ]
    await update.message.reply_text(
        "🎮 PhoenixCheat Admin Panel\n\nیک گزینه را انتخاب کن:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ================= مدیریت دکمه‌ها =================
async def button_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    db = load_data()

    if data == "list_orders":
        orders = db.get("orders", [])
        text = f"📦 **سفارشات اخیر ({len(orders)} کل):**\n\n"
        for o in orders[-5:]:
            status = "⏳" if o['status'] == 'pending' else ("✅" if o['status'] == 'accepted' else "❌")
            text += f"{status} `{o['code']}` | {o['email']} | {o['total_price']:,} ت\n"
        keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="back")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "stats":
        users = len(db.get("users", []))
        orders = len(db.get("orders", []))
        visits = db.get("stats", {}).get("total_visits", 0)
        text = (
            f"📊 **آمار کامل سیستم**\n\n"
            f"👥 کاربران: {users}\n"
            f"📦 سفارشات: {orders}\n"
            f"👁️ بازدید: {visits}\n"
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
        text = "🎟️ **مدیریت کدهای تخفیف**\n\nکد فعال: "
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
            [InlineKeyboardButton("🔧 وضعیت", callback_data="status")],
        ]
        await query.edit_message_text("🎮 PhoenixCheat Admin Panel", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("accept_"):
        oid = int(data.replace("accept_", ""))
        for o in db["orders"]:
            if o["id"] == oid:
                o["status"] = "accepted"
                save_data(db)
                await query.edit_message_text(f"✅ سفارش `{o['code']}` تایید شد.", parse_mode="Markdown")
                break

    elif data.startswith("reject_"):
        oid = int(data.replace("reject_", ""))
        for o in db["orders"]:
            if o["id"] == oid:
                o["status"] = "rejected"
                save_data(db)
                await query.edit_message_text(f"❌ سفارش `{o['code']}` رد شد.", parse_mode="Markdown")
                break

# ================= دستورات =================
async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    state = USER_STATES.get(ADMIN_ID, {}).get("state")
    text = update.message.text.strip()
    
    if state == "waiting_search":
        db = load_data()
        found = [o for o in db["orders"] if text.lower() in o["email"].lower() or text.upper() in o["code"]]
        if found:
            msg = "🔍 نتایج جستجو:\n\n"
            for o in found:
                msg += f"`{o['code']}` | {o['email']} | {o['total_price']:,} ت\n"
            await update.message.reply_text(msg, parse_mode="Markdown")
        else:
            await update.message.reply_text("❌ چیزی پیدا نشد.")
        USER_STATES.pop(ADMIN_ID, None)

async def set_card(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    try:
        txt = update.message.text.replace("/setcard ", "").split("-")
        db = load_data()
        db["settings"]["card_number"] = txt[0].strip()
        db["settings"]["card_holder"] = txt[1].strip()
        save_data(db)
        await update.message.reply_text("✅ کارت تغییر کرد.")
    except: await update.message.reply_text("❌ فرمت: /setcard 6219... - نام")

async def set_price(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
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
    if update.effective_user.id != ADMIN_ID: return
    try:
        parts = update.message.text.replace("/addcoupon ", "").split()
        code, percent = parts[0].upper(), int(parts[1])
        db = load_data()
        if "coupons" not in db: db["coupons"] = []
        db["coupons"].append({"code": code, "discount": percent, "active": True})
        save_data(db)
        await update.message.reply_text(f"✅ کد {code} با {percent}% تخفیف ساخته شد.")
    except: await update.message.reply_text("❌ فرمت: /addcoupon CODE 10")

# ================= اجرای سرور =================
def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app_web.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

def main():
    global bot_app
    if not BOT_TOKEN: return
    if USE_PROXY:
        request = HTTPXRequest(proxy=f"{PROXY_TYPE}://{PROXY_HOST}:{PROXY_PORT}")
        bot_app = Application.builder().token(BOT_TOKEN).request(request).build()
    else:
        bot_app = Application.builder().token(BOT_TOKEN).build()

    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CommandHandler("setcard", set_card))
    bot_app.add_handler(CommandHandler("setprice", set_price))
    bot_app.add_handler(CommandHandler("addcoupon", add_coupon))
    bot_app.add_handler(CallbackQueryHandler(button_handler))
    bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    threading.Thread(target=run_flask, daemon=True).start()
    bot_app.run_polling()

if __name__ == "__main__":
    main()