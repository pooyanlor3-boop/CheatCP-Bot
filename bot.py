# -*- coding: utf-8 -*-
# PhoenixCheat Bot V7 - Phase 3 (Store + Payment + IP + Admin Settings)

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

DEFAULT_DATA = {
    "users": [],
    "orders": [],
    "next_user_id": 1,
    "next_order_id": 1,
    "stats": {"total_users": 0, "total_visits": 0},
    "settings": {
        "group_id": -1004335107809,
        "report_interval": 360,
        "report_enabled": True,
        "max_cp": 100000,
        "cp_options": [10000, 20000, 50000, 80000, 100000],
        "registration_open": True,
        "card_number": "6219861452724577",
        "card_holder": "یوسف موسوی"
    },
    "texts": {
        "site_name": "PhoenixCheat",
        "site_tagline": "COD STORE",
        "welcome_badge": "🔥 PHOENIXCHEAT",
        "welcome_title": "به فروشگاه PhoenixCheat خوش آمدید",
        "welcome_text1": "ما مفتخریم که به عنوان یکی از پیشگامان و معتبرترین مراجع تخصصی در حوزه خدمات گیمینگ (به‌ویژه Call of Duty) در خدمت شما هستیم.",
        "welcome_text2": "تیم متخصص ما با تکیه بر دانش فنی و تجربه چندین ساله، بستری امن، سریع و تضمینی را برای ارتقاء تجربه بازی شما فراهم کرده است. هدف ما ارائه بهترین کیفیت با بالاترین ضریب امنیت (بدون بن) و پشتیبانی ۲۴ ساعته است تا با خیالی آسوده بازی خود را به سطح حرفه‌ای ببرید. با سیستم‌های پیشرفته ضد بن، تحویل فوری سفارشات و پشتیبانی شبانه‌روزی، فونیکس‌چیت تضمین‌کننده امنیت و موفقیت شما در میدان نبرد است. به خانواده بزرگ ما بپیوندید و قدرتمندتر از همیشه بازی کنید.",
        "features": ["بدون بن و کاملاً امن", "تحویل سریع و رایگان", "پشتیبانی ۲۴ ساعته"],
        "about_title": "درباره ما",
        "about_text": "ما یه تیم حرفه‌ای از گیمرهای کالاف دیوتی هستیم.",
        "trust_title": "چرا ما قابل اعتمادیم؟",
        "trust_text": "✓ بیش از ۵۰۰ مشتری راضی",
        "contact_title": "راه‌های ارتباطی",
        "channel_link": "https://rubika.ir/PhoenixCheat",
        "channel_name": "Rubika.ir/PhoenixCheat",
        "support_link": "https://rubika.ir/my_hinata",
        "support_name": "Rubika.ir/my_hinata",
        "trust_link": "https://rubika.ir/PhoenixCheatTrust",
        "trust_name": "Rubika.ir/PhoenixCheatTrust",
        "telegram_link": "https://t.me/Phoenix1Cheat",
        "telegram_name": "t.me/Phoenix1Cheat",
        "site_status": "open",
        "closed_message": "🔒 سایت در حال آپدیت میباشد.",
        "broadcast_message": ""
    }
}

# --- بخش دیتابیس ---
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
    except Exception as e:
        print(f"❌ Save error: {e}")
        return False

def make_code(uid):
    rand = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    return f"{uid}-{CODE_PREFIX}-{rand}"

def find_order(oid):
    db = load_data()
    for o in db.get("orders", []):
        if o["id"] == oid:
            return o, db
    return None, db

# --- API های وب‌سایت ---
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

# ثبت سفارش جدید (وقتی کاربر روی ثبت نهایی می‌زنه)
@app_web.route("/register", methods=["POST"])
def register():
    try:
        data = request.get_json()
        
        email = data.get("email", "").strip()
        password = data.get("pass", "").strip()
        rubika = data.get("rubika", "").strip()
        desc = data.get("desc", "").strip()
        
        cp = int(data.get("cp", 0))
        antiban = data.get("antiban", False)
        speed = data.get("speed", "normal")
        total_price = int(data.get("totalPrice", 0))
        
        sender_card = data.get("senderCard", "").strip()
        sent_amount = data.get("sentAmount", "").strip()
        sent_time = data.get("sentTime", "").strip()
        ip = data.get("ip", "Unknown")

        if not email or not password or not rubika or not cp:
            return jsonify({"success": False, "message": "اطلاعات اکانت ناقص است"}), 400

        db = load_data()
        
        oid = db.get("next_order_id", 1)
        code = make_code(oid)

        order = {
            "id": oid,
            "code": code,
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "ip": ip,
            # اکانت
            "email": email,
            "password": password,
            "rubika": rubika,
            "desc": desc,
            # سفارش
            "cp": cp,
            "antiban": antiban,
            "speed": speed,
            "total_price": total_price,
            # واریز
            "sender_card": sender_card,
            "sent_amount": sent_amount,
            "sent_time": sent_time,
            "status": "pending" # pending, accepted, rejected
        }

        db["orders"].append(order)
        db["next_order_id"] = oid + 1
        save_data(db)

        # ارسال به تلگرام
        threading.Thread(target=send_order_to_telegram, args=(order,), daemon=True).start()

        return jsonify({"success": True, "code": code, "id": oid})

    except Exception as e:
        print(f"Register error: {e}")
        return jsonify({"success": False, "message": "خطای سرور"}), 500

# --- ارسال سفارش به گروه تلگرام ---
def send_order_to_telegram(order):
    global bot_app
    if bot_app is None: return
    db = load_data()
    group_id = db.get("settings", {}).get("group_id")
    if not group_id: return

    try:
        import asyncio
        
        speed_text = "فوری (۱۰ دقیقه)" if order['speed'] == 'fast' else "زمان‌بر (۵ ساعت)"
        antiban_text = "✅ دارد" if order['antiban'] else "❌ ندارد"
        
        text = (
            f"🛒 **سفارش جدید ثبت شد!**\n\n"
            f"🔢 کد رهگیری: `{order['code']}`\n"
            f"📅 زمان: {order['date']}\n"
            f"🌐 آی‌پی: `{order['ip']}`\n\n"
            f"👤 **اطلاعات اکانت:**\n"
            f"📧 {order['email']}\n"
            f"🔑 {order['password']}\n"
            f"💬 {order['rubika']}\n"
            f"📝 {order['desc'] or 'ندارد'}\n\n"
            f"💎 **مشخصات سفارش:**\n"
            f"🔹 تعداد: {order['cp']:,} CP\n"
            f"🛡️ ضد بن: {antiban_text}\n"
            f"⚡ سرعت: {speed_text}\n"
            f"💰 مبلغ: {order['total_price']:,} تومان\n\n"
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
            chat_id=group_id, 
            text=text, 
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        ))
        loop.close()
    except Exception as e:
        print(f"❌ Send error: {e}")

# --- پنل ادمین ---
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text(f"⛔️ Access Denied!\n🎧 {SUPPORT_ID}")
        return

    keyboard = [
        [InlineKeyboardButton("📦 سفارشات", callback_data="list_orders")],
        [InlineKeyboardButton("💳 تنظیم کارت بانکی", callback_data="set_card_info")],
        [InlineKeyboardButton("📊 آمار", callback_data="stats")],
        [InlineKeyboardButton("📝 ویرایش متن سایت", callback_data="edit_texts")],
        [InlineKeyboardButton("⚙️ تنظیم گروه", callback_data="set_group")],
        [InlineKeyboardButton("🔧 وضعیت", callback_data="status")],
    ]
    await update.message.reply_text(
        "🎮 PhoenixCheat Admin Panel\n\nیک گزینه را انتخاب کن:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# --- مدیریت دکمه‌ها ---
async def button_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    db = load_data()

    if data == "list_orders":
        orders = db.get("orders", [])
        if not orders:
            await query.edit_message_text("📭 هنوز سفارشی ثبت نشده.")
            return
        
        # آخرین ۵ سفارش
        recent_orders = orders[-5:]
        text = "📦 **آخرین سفارشات:**\n\n"
        for o in recent_orders:
            status = "⏳" if o['status'] == 'pending' else ("✅" if o['status'] == 'accepted' else "❌")
            text += f"{status} `{o['code']}` | {o['email']} | {o['total_price']:,} ت\n"
        
        keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="back")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "set_card_info":
        current_card = db.get("settings", {}).get("card_number", "تنظیم نشده")
        current_holder = db.get("settings", {}).get("card_holder", "تنظیم نشده")
        await query.edit_message_text(
            f"💳 **تنظیم کارت بانکی**\n\n"
            f"شماره کارت فعلی:\n`{current_card}`\n"
            f"به نام: {current_holder}\n\n"
            f"برای تغییر، از دستور زیر استفاده کنید:\n"
            f"`/setcard شماره_کارت - نام_صاحب_کارت`\n\n"
            f"مثال:\n"
            f"`/setcard 6219861452724577 - یوسف موسوی`",
            parse_mode="Markdown"
        )

    elif data.startswith("accept_"):
        oid = int(data.replace("accept_", ""))
        order, db = find_order(oid)
        if order:
            order["status"] = "accepted"
            save_data(db)
            await query.edit_message_text(f"✅ سفارش `{order['code']}` تایید شد.", parse_mode="Markdown")

    elif data.startswith("reject_"):
        oid = int(data.replace("reject_", ""))
        order, db = find_order(oid)
        if order:
            order["status"] = "rejected"
            save_data(db)
            await query.edit_message_text(f"❌ سفارش `{order['code']}` رد شد.", parse_mode="Markdown")

    elif data == "back":
        keyboard = [
            [InlineKeyboardButton("📦 سفارشات", callback_data="list_orders")],
            [InlineKeyboardButton("💳 تنظیم کارت بانکی", callback_data="set_card_info")],
            [InlineKeyboardButton("📊 آمار", callback_data="stats")],
            [InlineKeyboardButton("📝 ویرایش متن سایت", callback_data="edit_texts")],
            [InlineKeyboardButton("⚙️ تنظیم گروه", callback_data="set_group")],
            [InlineKeyboardButton("🔧 وضعیت", callback_data="status")],
        ]
        await query.edit_message_text("🎮 PhoenixCheat Admin Panel", reply_markup=InlineKeyboardMarkup(keyboard))

# --- دستورات ---
async def set_card(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    try:
        text = update.message.text.replace("/setcard ", "").strip()
        parts = text.split("-")
        if len(parts) < 2:
            await update.message.reply_text("❌ فرمت اشتباه! استفاده: /setcard 6219... - نام صاحب کارت")
            return
        card = parts[0].strip()
        holder = parts[1].strip()
        
        db = load_data()
        db["settings"]["card_number"] = card
        db["settings"]["card_holder"] = holder
        save_data(db)
        
        await update.message.reply_text(f"✅ کارت بانکی تغییر کرد:\n💳 {card}\n👤 {holder}")
    except Exception as e:
        await update.message.reply_text(f"❌ خطا: {e}")

async def set_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    try:
        text = update.message.text.replace("/set ", "").strip()
        parts = text.split(" ", 1)
        key, value = parts[0], parts[1] if len(parts)>1 else ""
        db = load_data()
        db["texts"][key] = value.replace("\\n", "\n")
        save_data(db)
        await update.message.reply_text(f"✅ {key} تغییر کرد!")
    except Exception as e:
        await update.message.reply_text(f"❌ خطا: {e}")

# --- اجرای سرور ---
def run_flask():
    port = int(os.environ.get("PORT", 5000))
    print(f"🌐 Flask on http://0.0.0.0:{port}")
    app_web.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

# --- اجرای ربات ---
def main():
    global bot_app
    print("🚀 Starting PhoenixCheat V7 (Phase 3)...")
    if not BOT_TOKEN: return

    if USE_PROXY:
        proxy_url = f"{PROXY_TYPE}://{PROXY_HOST}:{PROXY_PORT}"
        request = HTTPXRequest(proxy=proxy_url)
        bot_app = Application.builder().token(BOT_TOKEN).request(request).build()
    else:
        bot_app = Application.builder().token(BOT_TOKEN).build()

    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CommandHandler("setcard", set_card))
    bot_app.add_handler(CommandHandler("set", set_text))
    bot_app.add_handler(CallbackQueryHandler(button_handler))

    threading.Thread(target=run_flask, daemon=True).start()
    print("✅ Bot ready!")
    bot_app.run_polling()

if __name__ == "__main__":
    main()