# -*- coding: utf-8 -*-
# PhoenixCheat Bot V22 - Dual Pricing (Variable + Fixed Packages)

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
    "settings": {
        "card_number": "6219861452724577",
        "card_holder": "یوسف موسوی",
        "price_per_1000": 25000,  # نرخ متغیر
        "price_antiban": 50000,
        "price_fast": 20000,
        "registration_open": True,
        "special_discount_text": "🎁 تخفیف ویژه",
        "special_coupon_code": "",
        "special_coupon_end_time": "",
        "custom_packages": [
            {"cp": 10000, "price": 250000},
            {"cp": 20000, "price": 450000},
            {"cp": 50000, "price": 1000000}
        ]
    },
    "coupons": [], 
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
            if "settings" not in data: data["settings"] = DEFAULT_DATA["settings"]
            s = data["settings"]
            if "price_per_1000" not in s: s["price_per_1000"] = 25000
            if "custom_packages" not in s: s["custom_packages"] = DEFAULT_DATA["settings"]["custom_packages"]
            if "special_coupon_code" not in s: s["special_coupon_code"] = ""
            if "special_coupon_end_time" not in s: s["special_coupon_end_time"] = ""
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
            return jsonify({"success": True, "type": c["type"], "amount": c["amount"]})
    return jsonify({"success": False, "message": "کد نامعتبر است"}), 400

@app_web.route("/register", methods=["POST"])
def register():
    try:
        data = request.get_json()
        db = load_data()
        
        discount_amount = 0
        coupon_code = data.get("coupon", "").upper()
        if coupon_code:
            for c in db.get("coupons", []):
                if c["code"] == coupon_code and c["active"]:
                    if c["type"] == "percent":
                        discount_amount = (int(data.get("totalPrice", 0)) * c["amount"]) // 100
                    elif c["type"] == "fixed":
                        discount_amount = c["amount"]
                    break
        
        final_price = int(data.get("totalPrice", 0)) - discount_amount
        if final_price < 0: final_price = 0

        oid = db.get("next_order_id", 1)
        order = {
            "id": oid, "code": make_code(), "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "email": data.get("email", ""), "pass": data.get("pass", ""), "rubika": data.get("rubika", ""), "desc": data.get("desc", ""),
            "cp": int(data.get("cp", 0)), "antiban": data.get("antiban", False), "speed": data.get("speed", "normal"),
            "base_price": int(data.get("totalPrice", 0)), "discount_amount": discount_amount, "final_price": final_price,
            "sender_card": data.get("senderCard", ""), "sent_amount": data.get("sentAmount", ""), "sent_time": data.get("sentTime", ""), 
            "status": "pending"
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
        speed_text = "فوری" if order['speed'] == 'fast' else "زمان‌بر"
        antiban_text = "✅" if order['antiban'] else "❌"
        
        text = (
            f"🛒 **سفارش جدید!**\n\n"
            f"🔢 کد: `{order['code']}`\n"
            f"👤 **اکانت:**\n📧 `{order['email']}`\n🔑 `{order['pass']}`\n💬 {order['rubika']}\n\n"
            f"💎 {order['cp']:,} CP | 🛡️ {antiban_text} | ⚡ {speed_text}\n"
            f"💰 مبلغ کل: {order['base_price']:,} ت\n"
            f"🎟️ تخفیف: {order['discount_amount']:,} ت\n"
            f"💳 مبلغ نهایی: **{order['final_price']:,} ت**\n\n"
            f"💳 **واریز:**\n`{order['sender_card']}` | {order['sent_time']}"
        )
        
        keyboard = [[InlineKeyboardButton("✅ تأیید", callback_data=f"ok_{order['id']}"), InlineKeyboardButton("❌ رد", callback_data=f"no_{order['id']}")]]
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(bot_app.bot.send_message(
            chat_id=GROUP_ID, text=text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
        ))
        loop.close()
    except Exception as e: print(f"TG Error: {e}")

# ================= کیبوردها =================
def get_main_menu():
    return [
        [InlineKeyboardButton("📦 مدیریت سفارشات", callback_data="menu_orders")],
        [InlineKeyboardButton("💰 تنظیم قیمت‌ها", callback_data="menu_prices"), InlineKeyboardButton("🎟️ کدهای تخفیف", callback_data="menu_coupons")],
        [InlineKeyboardButton("🎁 تخفیف ویژه سایت", callback_data="menu_special_discount")],
        [InlineKeyboardButton("💳 تنظیم کارت بانکی", callback_data="menu_card")],
        [InlineKeyboardButton("📝 ویرایش متن سایت", callback_data="menu_texts")],
        [InlineKeyboardButton("🔐 باز/بسته ثبت‌نام", callback_data="menu_toggle_reg")],
    ]

async def show_main_menu(update, text="🎮 **پنل مدیریت PhoenixCheat**\n\nیک گزینه را انتخاب کنید:"):
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(get_main_menu()), parse_mode="Markdown")
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(get_main_menu()), parse_mode="Markdown")

# ================= هندلر اصلی =================
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    USER_STATES.pop(ADMIN_ID, None)
    await show_main_menu(update)

async def button_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    db = load_data()
    s = db["settings"]

    if data == "back":
        USER_STATES.pop(ADMIN_ID, None)
        await show_main_menu(update)

    # --- بخش قیمت ها (تفکیک شده) ---
    elif data == "menu_prices":
        keyboard = [
            [InlineKeyboardButton(f"⚙️ نرخ متغیر (فعلی: {s.get('price_per_1000', 25000):,} ت)", callback_data="price_var")],
            [InlineKeyboardButton("📦 مدیریت پکیج‌ها", callback_data="price_pkgs")],
            [InlineKeyboardButton("💰 تنظیم انتی بن و فوری", callback_data="edit_extras")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="back")]
        ]
        await query.edit_message_text("💰 **بخش تنظیم قیمت‌ها**\n\nلطفاً یکی از بخش‌ها را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "price_var":
        USER_STATES[ADMIN_ID] = {"state": "waiting_price_var"}
        await query.edit_message_text(f"نرخ فعلی برای هر ۱۰۰۰ سی‌پی: **{s.get('price_per_1000', 25000):,} تومان**\n\nنرخ جدید را به تومان بنویسید:\n(مثلاً 30000)", parse_mode="Markdown")

    elif data == "price_pkgs":
        text = "📦 **مدیریت پکیج‌ها**\n\nبرای تغییر قیمت هر پکیج، روی آن بزنید:\n"
        keyboard = []
        for i, pkg in enumerate(s.get("custom_packages", [])):
            text += f"🔹 {pkg['cp']:,} CP = {pkg['price']:,} ت\n"
            keyboard.append([InlineKeyboardButton(f"✏️ {pkg['cp']:,} CP", callback_data=f"edit_pkg_{i}")])
        
        keyboard.append([InlineKeyboardButton("➕ افزودن پکیج جدید", callback_data="add_pkg")])
        keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data="menu_prices")])
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data.startswith("edit_pkg_"):
        idx = int(data.split("_")[2])
        pkg = s["custom_packages"][idx]
        USER_STATES[ADMIN_ID] = {"state": "waiting_pkg_price", "idx": idx}
        await query.edit_message_text(f"قیمت جدید برای **{pkg['cp']:,} CP** را بنویسید:")

    elif data == "add_pkg":
        USER_STATES[ADMIN_ID] = {"state": "waiting_pkg_cp"}
        await query.edit_message_text("تعداد CP پکیج جدید را بنویسید (مثلاً 30000):")

    elif data == "edit_extras":
        USER_STATES[ADMIN_ID] = {"state": "waiting_extra_antiban"}
        await query.edit_message_text(f"قیمت فعلی انتی بن: {s['price_antiban']:,} ت\n\nقیمت جدید انتی بن را بنویسید:")

    # --- کدهای تخفیف ---
    elif data == "menu_coupons":
        text = "🎟️ **مدیریت کدهای تخفیف**\n\n"
        keyboard = []
        for c in db.get("coupons", []):
            type_str = f"{c['amount']}%" if c['type'] == 'percent' else f"{c['amount']:,} ت"
            status = "🟢" if c['active'] else "🔴"
            text += f"{status} `{c['code']}` | {type_str}\n"
            keyboard.append([InlineKeyboardButton(f"🗑️ حذف {c['code']}", callback_data=f"del_coupon_{c['code']}")])
        
        keyboard.append([InlineKeyboardButton("➕ ساخت کد تخفیف جدید", callback_data="add_coupon")])
        keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data="back")])
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "add_coupon":
        USER_STATES[ADMIN_ID] = {"state": "waiting_coupon_code"}
        await query.edit_message_text("کد تخفیف را وارد کنید (فقط حروف انگلیسی و عدد):\n(مثلاً CHEAT10)")

    elif data.startswith("del_coupon_"):
        code = data.split("_")[2]
        db["coupons"] = [c for c in db["coupons"] if c["code"] != code]
        save_data(db)
        await query.answer("کد حذف شد!", show_alert=True)
        await button_handler(update, ctx)

    # --- تخفیف ویژه ---
    elif data == "menu_special_discount":
        code = s.get("special_coupon_code", "تنظیم نشده")
        end_time = s.get("special_coupon_end_time", "")
        time_str = "تنظیم نشده"
        if end_time:
            end_dt = datetime.fromtimestamp(int(end_time))
            time_left = end_dt - datetime.now()
            if time_left.total_seconds() > 0:
                time_str = f"{time_left.days} روز و {time_left.seconds // 3600} ساعت"
            else:
                time_str = "پایان یافته"
                
        text = f"🎁 **تنظیمات تخفیف ویژه**\n\n🎟️ کد: `{code}`\n⏳ زمان: {time_str}\n\n"
        keyboard = [
            [InlineKeyboardButton("✏️ تغییر کد تخفیف", callback_data="sd_code")],
            [InlineKeyboardButton("⏳ تنظیم تایمر (ساعت)", callback_data="sd_time")],
            [InlineKeyboardButton("❌ حذف از سایت", callback_data="sd_clear")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="back")]
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "sd_code":
        USER_STATES[ADMIN_ID] = {"state": "waiting_sd_code"}
        await query.edit_message_text("کد تخفیف ویژه جدید را بنویسید (باید از قبل ساخته شده باشد):")
    elif data == "sd_time":
        USER_STATES[ADMIN_ID] = {"state": "waiting_sd_time"}
        await query.edit_message_text("چند ساعت روی سایت بماند؟ (مثلاً 48)")
    elif data == "sd_clear":
        db["settings"]["special_coupon_code"] = ""
        db["settings"]["special_coupon_end_time"] = ""
        save_data(db)
        await query.answer("حذف شد.", show_alert=True)
        await button_handler(update, ctx)

    # --- کارت، متن، ثبت نام ---
    elif data == "menu_card":
        USER_STATES[ADMIN_ID] = {"state": "waiting_card"}
        await query.edit_message_text(f"شماره کارت فعلی: `{s['card_number']}`\n\nفرمت: `6219861452724577 - یوسف موسوی`", parse_mode="Markdown")

    elif data == "menu_texts":
        keyboard = [
            [InlineKeyboardButton("متن ۱", callback_data="set_txt_welcome_text1")],
            [InlineKeyboardButton("متن ۲", callback_data="set_txt_welcome_text2")],
            [InlineKeyboardButton("درباره ما", callback_data="set_txt_about_text")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="back")]
        ]
        await query.edit_message_text("📝 کدوم متن رو میخوای عوض کنی؟", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("set_txt_"):
        key = data.replace("set_txt_", "")
        USER_STATES[ADMIN_ID] = {"state": f"waiting_text_{key}"}
        await query.edit_message_text(f"متن جدید برای `{key}` را بفرستید:", parse_mode="Markdown")

    elif data == "menu_toggle_reg":
        s["registration_open"] = not s.get("registration_open", True)
        save_data(db)
        await query.answer(f"ثبت‌نام {'باز' if s['registration_open'] else 'بسته'} شد.", show_alert=True)

    # --- سفارشات ---
    elif data == "menu_orders":
        orders = db.get("orders", [])
        keyboard = []
        for o in orders[-5:][::-1]:
            status = "⏳" if o['status'] == 'pending' else ("✅" if o['status'] == 'accepted' else "❌")
            keyboard.append([InlineKeyboardButton(f"{status} {o['code']} | {o['final_price']:,} ت", callback_data=f"view_{o['id']}")])
        keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data="back")])
        await query.edit_message_text(f"📦 **سفارشات ({len(orders)}):**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data.startswith("view_"):
        oid = int(data.split("_")[1])
        order = next((o for o in db["orders"] if o["id"] == oid), None)
        if not order: return
        text = f"👁️ **سفارش {order['code']}**\n\n📧 {order['email']}\n🔑 {order['pass']}\n💳 {order['sender_card']}\n💰 مبلغ: {order['final_price']:,} ت"
        keyboard = [[InlineKeyboardButton("✅ تایید", callback_data=f"ok_{oid}"), InlineKeyboardButton("❌ رد", callback_data=f"no_{oid}")], [InlineKeyboardButton("🔙 بازگشت", callback_data="menu_orders")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data.startswith("ok_") or data.startswith("no_"):
        oid = int(data.split("_")[1])
        status = "accepted" if data.startswith("ok_") else "rejected"
        for o in db["orders"]:
            if o["id"] == oid: o["status"] = status; save_data(db); break
        await query.answer("وضعیت تغییر کرد.")
        await button_handler(update, ctx)

# ================= هندلر متنی =================
async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    state_data = USER_STATES.get(ADMIN_ID)
    if not state_data: return

    state = state_data.get("state")
    text = update.message.text.strip()
    db = load_data()
    s = db["settings"]

    try:
        if state == "waiting_price_var":
            s["price_per_1000"] = int(text)
            save_data(db)
            USER_STATES.pop(ADMIN_ID)
            await update.message.reply_text(f"✅ نرخ متغیر تغییر کرد به {int(text):,} تومان.")
            await show_main_menu(update)

        elif state == "waiting_pkg_price":
            idx = state_data["idx"]
            s["custom_packages"][idx]["price"] = int(text)
            save_data(db)
            USER_STATES.pop(ADMIN_ID)
            await update.message.reply_text(f"✅ قیمت پکیج تغییر کرد به {int(text):,} تومان.")

        elif state == "waiting_pkg_cp":
            cp = int(text)
            s["custom_packages"].append({"cp": cp, "price": 0})
            save_data(db)
            USER_STATES.pop(ADMIN_ID)
            await update.message.reply_text(f"✅ پکیج {cp:,} CP اضافه شد. حالا قیمتش رو تنظیم کن.")

        elif state == "waiting_extra_antiban":
            s["price_antiban"] = int(text)
            save_data(db)
            USER_STATES.pop(ADMIN_ID)
            await update.message.reply_text("✅ قیمت انتی بن تغییر کرد.")

        elif state == "waiting_coupon_code":
            code = text.upper()
            USER_STATES[ADMIN_ID] = {"state": "waiting_coupon_type", "code": code}
            await update.message.reply_text("نوع تخفیف؟", reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("درصدی (%)", callback_data="coup_type_percent")],
                [InlineKeyboardButton("مبلغی (تومان)", callback_data="coup_type_fixed")]
            ]))

        elif state == "waiting_coupon_amount_percent":
            db["coupons"].append({"code": state_data["code"], "type": "percent", "amount": int(text), "active": True})
            save_data(db)
            USER_STATES.pop(ADMIN_ID)
            await update.message.reply_text(f"✅ کد {state_data['code']} ساخته شد.")

        elif state == "waiting_coupon_amount_fixed":
            db["coupons"].append({"code": state_data["code"], "type": "fixed", "amount": int(text), "active": True})
            save_data(db)
            USER_STATES.pop(ADMIN_ID)
            await update.message.reply_text(f"✅ کد {state_data['code']} ساخته شد.")

        elif state == "waiting_sd_code":
            s["special_coupon_code"] = text.upper()
            save_data(db)
            USER_STATES.pop(ADMIN_ID)
            await update.message.reply_text(f"✅ کد ویژه تغییر کرد.")

        elif state == "waiting_sd_time":
            end_time = (datetime.now() + timedelta(hours=int(text))).timestamp()
            s["special_coupon_end_time"] = str(int(end_time))
            save_data(db)
            USER_STATES.pop(ADMIN_ID)
            await update.message.reply_text(f"✅ تایمر روی {int(text)} ساعت تنظیم شد.")

        elif state == "waiting_card":
            parts = text.split("-")
            s["card_number"] = parts[0].strip()
            if len(parts) > 1: s["card_holder"] = parts[1].strip()
            save_data(db)
            USER_STATES.pop(ADMIN_ID)
            await update.message.reply_text("✅ کارت تغییر کرد.")

        elif state.startswith("waiting_text_"):
            key = state.replace("waiting_text_", "")
            db["texts"][key] = text
            save_data(db)
            USER_STATES.pop(ADMIN_ID)
            await update.message.reply_text(f"✅ متن تغییر کرد.")

    except ValueError:
        await update.message.reply_text("❌ لطفا فقط عدد وارد کنید.")

async def coupon_type_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    state_data = USER_STATES.get(ADMIN_ID, {})
    
    if data == "coup_type_percent":
        USER_STATES[ADMIN_ID] = {"state": "waiting_coupon_amount_percent", "code": state_data.get("code")}
        await query.edit_message_text("چند درصد تخفیف؟")
    elif data == "coup_type_fixed":
        USER_STATES[ADMIN_ID] = {"state": "waiting_coupon_amount_fixed", "code": state_data.get("code")}
        await query.edit_message_text("چند تومان تخفیف؟")

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app_web.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

def run_bot():
    global bot_app
    bot_app = Application.builder().token(BOT_TOKEN).build()
    
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CallbackQueryHandler(coupon_type_handler, pattern="^coup_type_"))
    bot_app.add_handler(CallbackQueryHandler(button_handler))
    bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    bot_app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    run_bot()