# -*- coding: utf-8 -*-
# PhoenixCheat Bot V20 - Control Special Discount Timer & Code

import json
import os
import random
import string
import threading
import asyncio
from datetime import datetime, timedelta

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

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
    "orders": [],
    "next_order_id": 1,
    "stats": {"total_orders": 0, "total_visits": 0},
    "settings": {
        "card_number": "6219861452724577",
        "card_holder": "یوسف موسوی",
        "price_per_1000": 25000,
        "price_antiban": 50000,
        "price_fast": 20000,
        "registration_open": True,
        "special_discount_text": "🎁 تخفیف ویژه",
        "special_coupon_code": "WELCOME10",
        "special_coupon_end_time": "" # زمان پایان به فرمت timestamp
    },
    "coupons": [
        {"code": "WELCOME10", "discount": 10, "active": True}
    ],
    "texts": {
        "site_name": "فونیکس چیت",
        "welcome_title": "به فروشگاه فونیکس چیت خوش آمدید",
        "welcome_text1": "ما مفتخریم که به عنوان یکی از پیشگامان و معتبرترین مراجع تخصصی در حوزه خدمات گیمینگ (به‌ویژه Call of Duty) در خدمت شما هستیم.",
        "welcome_text2": "تیم متخصص ما با تکیه بر دانش فنی و تجربه چندین ساله، بستری امن، سریع و تضمینی را برای ارتقاء تجربه بازی شما فراهم کرده است.",
        "about_text": "ما یه تیم حرفه‌ای از گیمرهای کالاف دیوتی هستیم.",
        "trust_text": "✓ بیش از ۵۰۰ مشتری راضی\n✓ چنل اعتماد فعال\n✓ پشتیبانی ۲۴/۷",
    }
}

def load_data():
    try:
        with open(DB_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            if "orders" not in data or "settings" not in data:
                save_data(DEFAULT_DATA)
                return DEFAULT_DATA
            # اضافه کردن کلیدهای جدید به دیتابیس‌های قدیمی
            if "special_coupon_code" not in data["settings"]: data["settings"]["special_coupon_code"] = "WELCOME10"
            if "special_coupon_end_time" not in data["settings"]: data["settings"]["special_coupon_end_time"] = ""
            if "special_discount_text" not in data["settings"]: data["settings"]["special_discount_text"] = "🎁 تخفیف ویژه"
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
    return jsonify({
        "texts": db.get("texts", {}),
        "settings": db.get("settings", {}),
        "special_coupon": db["settings"].get("special_coupon_code", "")
    })

@app_web.route("/api/check_coupon", methods=["POST"])
def check_coupon():
    code = request.get_json().get("code", "").strip().upper()
    for c in load_data().get("coupons", []):
        if c["code"] == code and c["active"]:
            return jsonify({"success": True, "discount": c["discount"]})
    return jsonify({"success": False, "message": "کد نامعتبر است"}), 400

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
            "discount": discount,
            "sender_card": data.get("senderCard", ""), "sent_amount": data.get("sentAmount", ""),
            "sent_time": data.get("sentTime", ""), "status": "pending"
        }
        
        db["orders"].append(order)
        db["next_order_id"] = oid + 1
        save_data(db)
        
        threading.Thread(target=send_order_to_telegram, args=(order,), daemon=True).start()
        return jsonify({"success": True, "code": order["code"]})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

# ================= ارسال به تلگرام =================
def send_order_to_telegram(order):
    global bot_app
    if not bot_app: return
    try:
        speed_text = "فوری (۱۰ دقیقه)" if order['speed'] == 'fast' else "زمان‌بر (۵ ساعت)"
        antiban_text = "✅ دارد" if order['antiban'] else "❌ ندارد"
        
        text = (
            f"🛒 **سفارش جدید ثبت شد!**\n\n"
            f"🔢 کد رهگیری: `{order['code']}`\n"
            f"📅 زمان: {order['date']}\n\n"
            f"👤 **اطلاعات اکانت:**\n"
            f"📧 ایمیل: `{order['email']}`\n"
            f"🔑 رمز: `{order['pass']}`\n"
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
            f"⏰ ساعت واریز: {order['sent_time']}"
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
        print(f"❌ Telegram error: {e}")

# ================= پنل ادمین =================
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    keyboard = [
        [InlineKeyboardButton("📦 سفارشات", callback_data="list_orders_0"), InlineKeyboardButton("📊 آمار", callback_data="stats")],
        [InlineKeyboardButton("🎁 تنظیمات تخفیف ویژه", callback_data="discount_settings")],
        [InlineKeyboardButton("🎟️ کدهای تخفیف", callback_data="coupons_menu")],
        [InlineKeyboardButton("💳 تنظیمات کارت", callback_data="set_card_info")],
        [InlineKeyboardButton("💰 تنظیم نرخ قیمت", callback_data="set_prices")],
        [InlineKeyboardButton("📝 متن سایت", callback_data="edit_texts")],
        [InlineKeyboardButton("🔐 باز/بسته ثبت‌نام", callback_data="toggle_reg")],
    ]
    await update.message.reply_text("🎮 PhoenixCheat Admin Panel", reply_markup=InlineKeyboardMarkup(keyboard))

async def button_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    db = load_data()

    if data == "discount_settings":
        s = db["settings"]
        code = s.get("special_coupon_code", "تنظیم نشده")
        end_time = s.get("special_coupon_end_time", "")
        
        if end_time:
            # تبدیل timestamp به زمان خوانا
            end_dt = datetime.fromtimestamp(int(end_time))
            time_left = end_dt - datetime.now()
            if time_left.total_seconds() > 0:
                days = time_left.days
                hours, remainder = divmod(time_left.seconds, 3600)
                time_str = f"{days} روز و {hours} ساعت"
            else:
                time_str = "پایان یافته"
        else:
            time_str = "تنظیم نشده"

        text = (
            f"🎁 **تنظیمات تخفیف ویژه**\n\n"
            f"🎟️ کد فعلی: `{code}`\n"
            f"⏳ زمان باقیمانده: {time_str}\n\n"
            f"برای تغییر کد:\n`/setdiscount code CHEAT20`\n\n"
            f"برای تنظیم زمان (به ساعت):\n`/setdiscount time 48`\n\n"
            f"برای حذف کامل تخفیف:\n`/setdiscount clear`"
        )
        keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="back")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data.startswith("list_orders_"):
        page = int(data.split("_")[2])
        orders = db.get("orders", [])
        if not orders:
            await query.edit_message_text("📭 سفارشی نیست.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="back")]]))
            return
        per_page = 5
        total_pages = (len(orders) + per_page - 1) // per_page
        page = max(0, min(page, total_pages - 1))
        page_orders = orders[::-1][page*per_page:(page+1)*per_page]
        
        text = f"📦 **سفارشات ({page+1}/{total_pages})**\n\n"
        keyboard = []
        for o in page_orders:
            status = "⏳" if o['status'] == 'pending' else ("✅" if o['status'] == 'accepted' else "❌")
            keyboard.append([InlineKeyboardButton(f"{status} {o['code']} | {o['email'][:15]}", callback_data=f"view_{o['id']}")])
        nav = []
        if page > 0: nav.append(InlineKeyboardButton("◀️", callback_data=f"list_orders_{page-1}"))
        if page < total_pages - 1: nav.append(InlineKeyboardButton("▶️", callback_data=f"list_orders_{page+1}"))
        if nav: keyboard.append(nav)
        keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data="back")])
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data.startswith("view_"):
        oid = int(data.split("_")[1])
        order = next((o for o in db["orders"] if o["id"] == oid), None)
        if not order: return
        text = f"👁️ **سفارش {order['code']}**\n\n📧 {order['email']}\n🔑 {order['pass']}\n💳 {order['sender_card']}\n💰 {order['total_price']:,} ت"
        keyboard = [[InlineKeyboardButton("✅ تایید", callback_data=f"ok_{oid}"), InlineKeyboardButton("❌ رد", callback_data=f"no_{oid}")], [InlineKeyboardButton("🔙 بازگشت", callback_data="list_orders_0")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "stats":
        text = f"📊 **آمار**\n\n📦 سفارشات: {len(db.get('orders', []))}\n🎟️ کد فعال: {len([c for c in db.get('coupons', []) if c['active']])}"
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="back")]]), parse_mode="Markdown")

    elif data == "coupons_menu":
        text = "🎟️ **کدهای تخفیف**\n\n" + (", ".join([c['code'] for c in db.get("coupons", []) if c['active']]) or "ندارد")
        keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="back")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "set_card_info":
        await query.edit_message_text(f"💳 کارت فعلی: `{db['settings'].get('card_number')}`\n\n`/setcard 6219... - نام`", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="back")]]), parse_mode="Markdown")

    elif data == "set_prices":
        s = db["settings"]
        text = f"💰 هر ۱۰۰۰: {s.get('price_per_1000'):,}\nانتی بن: {s.get('price_antiban'):,}\nفوری: {s.get('price_fast'):,}\n\n`/setprice per_1000 25000`"
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="back")]]), parse_mode="Markdown")

    elif data == "edit_texts":
        await query.edit_message_text("📝 `/set key value`", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="back")]]), parse_mode="Markdown")

    elif data == "toggle_reg":
        db["settings"]["registration_open"] = not db["settings"].get("registration_open", True)
        save_data(db)
        await query.edit_message_text("✅ وضعیت ثبت‌نام تغییر کرد.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="back")]]))

    elif data.startswith("ok_") or data.startswith("no_"):
        oid = int(data.split("_")[1])
        status = "accepted" if data.startswith("ok_") else "rejected"
        for o in db["orders"]:
            if o["id"] == oid: o["status"] = status; save_data(db); break
        await query.edit_message_text(f"✅ وضعیت سفارش تغییر کرد.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="list_orders_0")]]))

    elif data == "back":
        keyboard = [
            [InlineKeyboardButton("📦 سفارشات", callback_data="list_orders_0"), InlineKeyboardButton("📊 آمار", callback_data="stats")],
            [InlineKeyboardButton("🎁 تنظیمات تخفیف ویژه", callback_data="discount_settings")],
            [InlineKeyboardButton("🎟️ کدهای تخفیف", callback_data="coupons_menu")],
            [InlineKeyboardButton("💳 تنظیمات کارت", callback_data="set_card_info")],
            [InlineKeyboardButton("💰 تنظیم نرخ قیمت", callback_data="set_prices")],
            [InlineKeyboardButton("📝 متن سایت", callback_data="edit_texts")],
            [InlineKeyboardButton("🔐 باز/بسته ثبت‌نام", callback_data="toggle_reg")],
        ]
        await query.edit_message_text("🎮 PhoenixCheat Admin Panel", reply_markup=InlineKeyboardMarkup(keyboard))

# ================= دستورات =================
async def set_discount(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    try:
        parts = update.message.text.replace("/setdiscount ", "").split()
        action = parts[0].lower()
        db = load_data()

        if action == "code":
            new_code = parts[1].upper()
            db["settings"]["special_coupon_code"] = new_code
            save_data(db)
            await update.message.reply_text(f"✅ کد تخفیف به `{new_code}` تغییر کرد.")
        
        elif action == "time":
            hours = int(parts[1])
            end_time = (datetime.now() + timedelta(hours=hours)).timestamp()
            db["settings"]["special_coupon_end_time"] = str(int(end_time))
            save_data(db)
            await update.message.reply_text(f"✅ تایمر روی {hours} ساعت تنظیم شد.")
        
        elif action == "clear":
            db["settings"]["special_coupon_end_time"] = ""
            save_data(db)
            await update.message.reply_text("✅ بخش تخفیف ویژه از سایت حذف شد.")
    except:
        await update.message.reply_text("❌ فرمت اشتباه!\n`/setdiscount code NEWCODE`\n`/setdiscount time 48`\n`/setdiscount clear`")

async def set_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    try:
        text = update.message.text.replace("/set ", "").split(" ", 1)
        key, value = text[0], text[1] if len(text)>1 else ""
        db = load_data()
        db["texts"][key] = value.replace("\\n", "\n")
        save_data(db)
        await update.message.reply_text(f"✅ {key} تغییر کرد.")
    except: await update.message.reply_text("❌ خطا")

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
        db["settings"][f"price_{key}"] = val
        save_data(db)
        await update.message.reply_text("✅ قیمت تغییر کرد.")
    except: await update.message.reply_text("❌ فرمت: /setprice per_1000 25000")

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app_web.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

def run_bot():
    global bot_app
    bot_app = Application.builder().token(BOT_TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CommandHandler("setcard", set_card))
    bot_app.add_handler(CommandHandler("setprice", set_price))
    bot_app.add_handler(CommandHandler("setdiscount", set_discount))
    bot_app.add_handler(CommandHandler("set", set_text))
    bot_app.add_handler(CallbackQueryHandler(button_handler))
    bot_app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    run_bot()