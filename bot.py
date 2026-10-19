# -*- coding: utf-8 -*-
# PhoenixCheat Bot V19 - Control Special Discount Text

import json
import os
import random
import string
import threading
import asyncio
from datetime import datetime

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

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
    "coupons": [
        {"code": "WELCOME10", "discount": 10, "active": True}
    ],
    "texts": {
        "site_name": "فونیکس چیت",
        "welcome_title": "به فروشگاه فونیکس چیت خوش آمدید",
        "welcome_text1": "ما مفتخریم که به عنوان یکی از پیشگامان و معتبرترین مراجع تخصصی در حوزه خدمات گیمینگ (به‌ویژه Call of Duty) در خدمت شما هستیم.",
        "welcome_text2": "تیم متخصص ما با تکیه بر دانش فنی و تجربه چندین ساله، بستری امن، سریع و تضمینی را برای ارتقاء تجربه بازی شما فراهم کرده است. هدف ما ارائه بهترین کیفیت با بالاترین ضریب امنیت (بدون بن) و پشتیبانی ۲۴ ساعته است تا با خیالی آسوده بازی خود را به سطح حرفه‌ای ببرید.",
        "about_text": "ما یه تیم حرفه‌ای از گیمرهای کالاف دیوتی هستیم.",
        "trust_text": "✓ بیش از ۵۰۰ مشتری راضی\n✓ چنل اعتماد فعال\n✓ پشتیبانی ۲۴/۷",
        "channel_link": "https://rubika.ir/PhoenixCheat",
        "support_link": "https://rubika.ir/my_hinata",
        "telegram_link": "https://t.me/Phoenix1Cheat",
        "site_status": "open",
        "special_discount_text": "🎁 تخفیف ویژه"
    }
}

def load_data():
    try:
        with open(DB_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            
            # چک میکنیم اگر کلیدهای اصلی توی دیتابیس نبود، یعنی دیتابیس قدیمیه
            if "orders" not in data or "settings" not in data:
                print("⚠️ Old or broken DB detected. Creating new one.")
                save_data(DEFAULT_DATA)
                return DEFAULT_DATA
                
            if "texts" not in data: data["texts"] = {}
            if "special_discount_text" not in data["texts"]:
                data["texts"]["special_discount_text"] = "🎁 تخفیف ویژه"
            return data
    except Exception as e:
        print(f"⚠️ Error loading DB: {e}. Creating default.")
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
        "special_coupon": next((c["code"] for c in db.get("coupons", []) if c.get("active")), "")
    })

@app_web.route("/api/check_coupon", methods=["POST"])
def check_coupon():
    code = request.get_json().get("code", "").strip().upper()
    for c in load_data().get("coupons", []):
        if c["code"] == code and c["active"]:
            return jsonify({"success": True, "discount": c["discount"]})
    return jsonify({"success": False, "message": "کد نامعتبر است"}), 400

@app_web.route("/api/track", methods=["POST"])
def track_order():
    try:
        code = request.get_json().get("code", "").upper()
        db = load_data()
        for o in db.get("orders", []):
            if o["code"] == code:
                status_fa = "⏳ در انتظار تایید" if o["status"] == "pending" else ("✅ تایید شده" if o["status"] == "accepted" else "❌ رد شده")
                return jsonify({"success": True, "status": status_fa})
        return jsonify({"success": False, "message": "کد سفارش یافت نشد."}), 404
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

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
        db["stats"]["total_orders"] = db["stats"].get("total_orders", 0) + 1
        save_data(db)
        
        threading.Thread(target=send_order_to_telegram, args=(order,), daemon=True).start()
        return jsonify({"success": True, "code": order["code"]})
    except Exception as e:
        print(f"❌ [DEBUG] Register error: {e}")
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
        print(f"❌ [DEBUG] Telegram error: {e}")

# ================= پنل ادمین =================
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    keyboard = [
        [InlineKeyboardButton("📦 لیست سفارشات", callback_data="list_orders_0")],
        [InlineKeyboardButton("🔍 جستجوی سریع", callback_data="search_order")],
        [InlineKeyboardButton("📊 آمار کامل", callback_data="stats")],
        [InlineKeyboardButton("🎟️ کد تخفیف", callback_data="coupons_menu")],
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

    if data.startswith("list_orders_"):
        page = int(data.split("_")[2])
        orders = db.get("orders", [])
        if not orders:
            await query.edit_message_text("📭 هیچ سفارشی ثبت نشده.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="back")]]))
            return
        per_page = 5
        total_pages = (len(orders) + per_page - 1) // per_page
        page = max(0, min(page, total_pages - 1))
        start_idx = page * per_page
        end_idx = start_idx + per_page
        page_orders = orders[::-1][start_idx:end_idx]
        text = f"📦 **سفارشات (صفحه {page+1} از {total_pages})**\n\n"
        keyboard = []
        for o in page_orders:
            status = "⏳" if o['status'] == 'pending' else ("✅" if o['status'] == 'accepted' else "❌")
            keyboard.append([InlineKeyboardButton(f"{status} {o['code']} | {o['email'][:15]}", callback_data=f"view_{o['id']}")])
        nav = []
        if page > 0: nav.append(InlineKeyboardButton("◀️ قبلی", callback_data=f"list_orders_{page-1}"))
        if page < total_pages - 1: nav.append(InlineKeyboardButton("بعدی ▶️", callback_data=f"list_orders_{page+1}"))
        if nav: keyboard.append(nav)
        keyboard.append([InlineKeyboardButton("🔙 بازگشت به منو", callback_data="back")])
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data.startswith("view_"):
        oid = int(data.split("_")[1])
        order = next((o for o in db["orders"] if o["id"] == oid), None)
        if not order: return
        speed_text = "فوری" if order['speed'] == 'fast' else "زمان‌بر"
        antiban_text = "✅ دارد" if order['antiban'] else "❌ ندارد"
        status_fa = "⏳ در انتظار" if order['status'] == 'pending' else ("✅ تایید شده" if order['status'] == 'accepted' else "❌ رد شده")
        text = (
            f"👁️ **مشاهده جزئیات سفارش**\n\n"
            f"🔢 کد: `{order['code']}`\n"
            f"📅 زمان ثبت: {order['date']}\n"
            f"📌 وضعیت: {status_fa}\n\n"
            f"👤 **اطلاعات اکانت:**\n"
            f"📧 ایمیل: `{order['email']}`\n"
            f"🔑 رمز: `{order['pass']}`\n"
            f"💬 روبیکا: {order['rubika']}\n"
            f"📝 توضیحات: {order['desc'] or 'ندارد'}\n\n"
            f"💎 **مشخصات خرید:**\n"
            f"🔹 تعداد: {order['cp']:,} CP\n"
            f"🛡️ ضد بن: {antiban_text}\n"
            f"⚡ سرعت: {speed_text}\n"
            f"💰 مبلغ کل: {order['total_price']:,} تومان\n"
            f"🎟️ تخفیف: {order['discount']}%\n\n"
            f"💳 **اطلاعات واریز:**\n"
            f"🔢 کارت مبدا: `{order['sender_card']}`\n"
            f"💵 مبلغ واریزی: {order['sent_amount']} تومان\n"
            f"⏰ ساعت: {order['sent_time']}"
        )
        keyboard = [
            [InlineKeyboardButton("✅ تایید سفارش", callback_data=f"ok_{oid}"), InlineKeyboardButton("❌ رد سفارش", callback_data=f"no_{oid}")],
            [InlineKeyboardButton("🔙 بازگشت به لیست", callback_data="list_orders_0")]
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "search_order":
        USER_STATES[ADMIN_ID] = {"state": "waiting_search_order"}
        await query.edit_message_text("🔍 کد رهگیری سفارش را وارد کنید:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="back")]]))

    elif data == "stats":
        orders = db.get("orders", [])
        pending = len([o for o in orders if o['status'] == 'pending'])
        accepted = len([o for o in orders if o['status'] == 'accepted'])
        text = f"📊 **آمار**\n\n📦 کل: {len(orders)}\n⏳ در انتظار: {pending}\n✅ تایید شده: {accepted}\n👁️ بازدید: {db.get('stats', {}).get('total_visits', 0)}\n🎟️ کدهای فعال: {len([c for c in db.get('coupons', []) if c['active']])}"
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="back")]]), parse_mode="Markdown")

    elif data == "coupons_menu":
        text = "🎟️ **مدیریت کدهای تخفیف**\n\nکدهای فعال: " + (", ".join([c['code'] for c in db.get("coupons", []) if c['active']]) or "ندارد")
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("➕ ساخت کد جدید", callback_data="add_coupon_info")], [InlineKeyboardButton("🔙 بازگشت", callback_data="back")]]))

    elif data == "add_coupon_info":
        await query.edit_message_text("برای ساخت کد تخفیف دستور زیر را بفرستید:\n\n`/addcoupon CODE PERCENT`\n\nمثال: `/addcoupon CHEAT10 10`", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="coupons_menu")]]), parse_mode="Markdown")

    elif data == "set_card_info":
        card = db["settings"].get("card_number", "")
        holder = db["settings"].get("card_holder", "")
        await query.edit_message_text(f"💳 **تنظیم کارت**\n\nفعلی: `{card}`\nبه نام: {holder}\n\nبرای تغییر:\n`/setcard 6219... - نام صاحب کارت`", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="back")]]), parse_mode="Markdown")

    elif data == "set_prices":
        s = db["settings"]
        text = f"💰 **تنظیم نرخ قیمت**\n\nهر ۱۰۰۰ سی‌پی: {s.get('price_per_1000', 25000):,} ت\nانتی بن: {s.get('price_antiban', 50000):,} ت\nفوری: {s.get('price_fast', 20000):,} ت\n\n`/setprice per_1000 25000`\n`/setprice antiban 50000`\n`/setprice fast 20000`"
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="back")]]), parse_mode="Markdown")

    elif data == "edit_texts":
        await query.edit_message_text("📝 برای تغییر متن‌های سایت از دستور زیر استفاده کنید:\n\n`/set key value`\n\nمثلاً:\n`/set welcome_title سلام به فونیکس چیت`\n`/set special_discount_text تخفیف ویژه عیدانه`\n\n*برای حذف بخش تخفیف، مقدار آن را خالی بفرستید:*\n`/set special_discount_text`", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="back")]]), parse_mode="Markdown")

    elif data == "toggle_reg":
        status = db["settings"].get("registration_open", True)
        db["settings"]["registration_open"] = not status
        save_data(db)
        emoji = "🟢" if not status else "🔴"
        await query.edit_message_text(f"{emoji} ثبت‌نام: {'باز' if not status else 'بسته'} شد.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="back")]]))

    elif data.startswith("ok_"):
        oid = int(data.split("_")[1])
        for o in db["orders"]:
            if o["id"] == oid: o["status"] = "accepted"; save_data(db); break
        await query.edit_message_text(f"✅ سفارش تایید شد.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت به لیست", callback_data="list_orders_0")]]))
    elif data.startswith("no_"):
        oid = int(data.split("_")[1])
        for o in db["orders"]:
            if o["id"] == oid: o["status"] = "rejected"; save_data(db); break
        await query.edit_message_text(f"❌ سفارش رد شد.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت به لیست", callback_data="list_orders_0")]]))

    elif data == "back":
        USER_STATES.pop(ADMIN_ID, None)
        keyboard = [
            [InlineKeyboardButton("📦 لیست سفارشات", callback_data="list_orders_0")],
            [InlineKeyboardButton("🔍 جستجوی سریع سفارش", callback_data="search_order")],
            [InlineKeyboardButton("📊 آمار کامل", callback_data="stats")],
            [InlineKeyboardButton("🎟️ کد تخفیف", callback_data="coupons_menu")],
            [InlineKeyboardButton("💳 تنظیمات کارت", callback_data="set_card_info")],
            [InlineKeyboardButton("💰 تنظیم نرخ قیمت", callback_data="set_prices")],
            [InlineKeyboardButton("📝 متن سایت", callback_data="edit_texts")],
            [InlineKeyboardButton("🔐 باز/بسته ثبت‌نام", callback_data="toggle_reg")],
        ]
        await query.edit_message_text("🎮 PhoenixCheat Admin Panel", reply_markup=InlineKeyboardMarkup(keyboard))

# ================= دستورات متنی =================
async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    state = USER_STATES.get(ADMIN_ID, {}).get("state")
    text = update.message.text.strip()
    
    if state == "waiting_search_order":
        db = load_data()
        order = next((o for o in db["orders"] if o["code"].upper() == text.upper()), None)
        if order:
            speed_text = "فوری" if order['speed'] == 'fast' else "زمان‌بر"
            antiban_text = "✅ دارد" if order['antiban'] else "❌ ندارد"
            msg = f"🔍 **یافت شد!**\n\n🔢 `{order['code']}`\n📧 `{order['email']}`\n🔑 `{order['pass']}`\n\n🔹 {order['cp']:,} CP | {antiban_text} | {speed_text}\n💳 `{order['sender_card']}`"
            await update.message.reply_text(msg, parse_mode="Markdown")
        else:
            await update.message.reply_text("❌ پیدا نشد.")
        USER_STATES.pop(ADMIN_ID, None)

async def set_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    try:
        full_text = update.message.text.replace("/set ", "").strip()
        parts = full_text.split(" ", 1)
        key = parts[0].strip()
        value = parts[1].strip() if len(parts) > 1 else ""
        value = value.replace("\\n", "\n")
        
        db = load_data()
        if "texts" not in db: db["texts"] = {}
        db["texts"][key] = value
        save_data(db)
        
        if value == "":
            await update.message.reply_text(f"✅ متن '{key}' پاک شد (از سایت حذف می‌شود).")
        else:
            await update.message.reply_text(f"✅ متن '{key}' با موفقیت تغییر کرد.\n\nمتن جدید:\n{value}")
    except Exception as e:
        await update.message.reply_text(f"❌ خطا: {e}\nفرمت: /set key value")

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

# ================= اجرای سرور و ربات =================
def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app_web.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

def run_bot():
    global bot_app
    bot_app = Application.builder().token(BOT_TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CommandHandler("setcard", set_card))
    bot_app.add_handler(CommandHandler("setprice", set_price))
    bot_app.add_handler(CommandHandler("addcoupon", add_coupon))
    bot_app.add_handler(CommandHandler("set", set_text))
    bot_app.add_handler(CallbackQueryHandler(button_handler))
    bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    print("🚀 Bot is polling...")
    try:
        bot_app.run_polling(drop_pending_updates=True)
    except Exception as e:
        print(f"⚠️ Bot crashed: {e}")

if __name__ == "__main__":
    print("🌐 Starting Web Server...")
    threading.Thread(target=run_flask, daemon=True).start()
    import time
    time.sleep(2) 
    print("🤖 Starting Bot...")
    run_bot()