# -*- coding: utf-8 -*-
# PhoenixCheat Bot V11 - Debugging & Telegram Fix

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

# ⚠️ تنظیمات مستقیم برای دیباگ (طبق درخواست شما)
BOT_TOKEN = "8699196899:AAGaY7pFzU2OzBxwcF8_E-LqUbQZk4UUDgo"
ADMIN_ID = 8113206201
GROUP_ID = -1004335107809

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data.json")
app_web = Flask(__name__, static_folder=BASE_DIR)
CORS(app_web)
bot_app = None
USER_STATES = {}

DEFAULT_DATA = {
    "users": [],
    "orders": [],
    "next_user_id": 1,
    "next_order_id": 1,
    "stats": {"total_users": 0, "total_visits": 0, "total_orders": 0},
    "settings": {
        "group_id": GROUP_ID,
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
        "welcome_title": "به فروشگاه PhoenixCheat خوش آمدید",
        "welcome_text1": "ما مفتخریم که به عنوان یکی از پیشگامان و معتبرترین مراجع تخصصی در حوزه خدمات گیمینگ (به‌ویژه Call of Duty) در خدمت شما هستیم.",
        "welcome_text2": "تیم متخصص ما با تکیه بر دانش فنی و تجربه چندین ساله، بستری امن، سریع و تضمینی را برای ارتقاء تجربه بازی شما فراهم کرده است.",
        "about_text": "ما یه تیم حرفه‌ای از گیمرهای کالاف دیوتی هستیم.",
        "trust_text": "✓ بیش از ۵۰۰ مشتری راضی\n✓ چنل اعتماد فعال\n✓ پشتیبانی ۲۴/۷",
        "channel_link": "https://rubika.ir/PhoenixCheat",
        "support_link": "https://rubika.ir/my_hinata",
        "site_status": "open"
    }
}

def load_data():
    try:
        with open(DB_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        save_data(DEFAULT_DATA)
        return DEFAULT_DATA

def save_data(data):
    try:
        with open(DB_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except: return False

def make_code(prefix="ORD"):
    rand = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"{prefix}-{rand}"

@app_web.route("/")
def index():
    return send_from_directory(BASE_DIR, "index.html")

@app_web.route("/api/settings", methods=["GET"])
def get_settings():
    db = load_data()
    return jsonify({"texts": db.get("texts", {}), "settings": db.get("settings", {})})

@app_web.route("/api/check_coupon", methods=["POST"])
def check_coupon():
    data = request.get_json()
    code = data.get("code", "").strip().upper()
    db = load_data()
    for c in db.get("coupons", []):
        if c["code"] == code and c["active"]:
            return jsonify({"success": True, "discount": c["discount"]})
    return jsonify({"success": False, "message": "کد نامعتبر است"}), 400

# ================= بخش ثبت سفارش و دیباگ =================
@app_web.route("/register", methods=["POST"])
def register():
    try:
        data = request.get_json()
        print(f"\n📥 [DEBUG] New Request: {data}\n")
        
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
        db["stats"]["total_orders"] = db.get("stats", {}).get("total_orders", 0) + 1
        
        if save_data(db):
            print(f"✅ [DEBUG] Order {oid} saved to DB.")
            # ارسال به تلگرام
            try:
                send_order_to_telegram(order)
                return jsonify({"success": True, "code": order["code"]})
            except Exception as e:
                print(f"❌ [DEBUG] Telegram Error: {e}")
                return jsonify({"success": False, "message": f"خطای تلگرام: {str(e)}"}), 500
        else:
            print("❌ [DEBUG] Failed to save DB.")
            return jsonify({"success": False, "message": "خطا در ذخیره دیتابیس"}), 500
            
    except Exception as e:
        print(f"❌ [DEBUG] Global Error: {e}")
        return jsonify({"success": False, "message": f"خطای سرور: {str(e)}"}), 500

# ================= ارسال به تلگرام (قوی‌شده) =================
def send_order_to_telegram(order):
    global bot_app
    if not bot_app:
        print("❌ [DEBUG] Bot App is None.")
        return

    db = load_data()
    group_id = db.get("settings", {}).get("group_id", GROUP_ID)
    
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
    
    # ارسال امن با ایونت لوپ مجزا
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(bot_app.bot.send_message(
            chat_id=group_id, 
            text=text, 
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        ))
        print(f"✅ [DEBUG] Message sent to group {group_id}")
    except Exception as e:
        print(f"❌ [DEBUG] SendMessage Failed: {e}")
        raise e
    finally:
        loop.close()

# ================= پنل ادمین =================
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    keyboard = [
        [InlineKeyboardButton("📦 سفارشات", callback_data="list_orders")],
        [InlineKeyboardButton("📊 آمار", callback_data="stats")],
        [InlineKeyboardButton("🔍 جستجو", callback_data="search_user")],
        [InlineKeyboardButton("🎟️ کدهای تخفیف", callback_data="coupons_menu")],
        [InlineKeyboardButton("💳 تنظیم کارت", callback_data="set_card_info")],
        [InlineKeyboardButton("💰 تنظیم قیمت", callback_data="set_prices")],
    ]
    await update.message.reply_text("🎮 PhoenixCheat Admin", reply_markup=InlineKeyboardMarkup(keyboard))

async def button_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    db = load_data()

    if data == "list_orders":
        orders = db.get("orders", [])
        text = f"📦 **سفارشات ({len(orders)}):**\n\n"
        for o in orders[-5:]:
            text += f"⏳ `{o['code']}` | {o['email'][:10]} | {o['total_price']:,}\n"
        keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="back")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "back":
        keyboard = [
            [InlineKeyboardButton("📦 سفارشات", callback_data="list_orders")],
            [InlineKeyboardButton("📊 آمار", callback_data="stats")],
            [InlineKeyboardButton("🔍 جستجو", callback_data="search_user")],
            [InlineKeyboardButton("🎟️ کدهای تخفیف", callback_data="coupons_menu")],
            [InlineKeyboardButton("💳 تنظیم کارت", callback_data="set_card_info")],
            [InlineKeyboardButton("💰 تنظیم قیمت", callback_data="set_prices")],
        ]
        await query.edit_message_text("🎮 PhoenixCheat Admin", reply_markup=InlineKeyboardMarkup(keyboard))
    # سایر دکمه‌ها مطابق قبل...

# ================= اجرا =================
def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app_web.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

def main():
    global bot_app
    print("🚀 Starting Bot V11...")
    
    # اتصال مستقیم بدون پروکسی
    bot_app = Application.builder().token(BOT_TOKEN).build()

    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CallbackQueryHandler(button_handler))
    # ... (بقیه هندلرها)

    threading.Thread(target=run_flask, daemon=True).start()
    bot_app.run_polling()

if __name__ == "__main__":
    main()