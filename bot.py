# -*- coding: utf-8 -*-
# PhoenixCheat Bot V27 - Complete & Bug-Free

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

# ==========================================
# 🔐 تنظیمات
# ==========================================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8699196899:AAGaY7pFzU2OzBxwcF8_E-LqUbQZk4UUDgo")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "8113206201"))
GROUP_ID = int(os.environ.get("GROUP_ID", "-1004335107809"))

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
        "price_per_1000": 25000,
        "price_antiban": 50000,
        "price_fast": 20000,
        "registration_open": True,
        "special_discount_text": "🎁 تخفیف ویژه",
        "special_coupon_code": "",
        "special_coupon_end_time": "",
        "custom_packages": [
            {"cp": 10000, "price": 250000},
            {"cp": 20000, "price": 470000}
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

# ================= دیتابیس =================
def load_data():
    try:
        with open(DB_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            if "orders" not in data or "settings" not in data:
                save_data(DEFAULT_DATA)
                return DEFAULT_DATA
            return data
    except Exception as e:
        print(f"⚠️ DB Error: {e}")
        save_data(DEFAULT_DATA)
        return DEFAULT_DATA

def save_data(data):
    try:
        with open(DB_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"❌ Error saving DB: {e}")

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

@app_web.route("/api/track", methods=["POST"])
def track_order():
    try:
        code = request.get_json().get("code", "").upper()
        db = load_data()
        for o in db.get("orders", []):
            if o["code"] == code:
                status_fa = "⏳ در انتظار" if o["status"] == "pending" else ("✅ تایید شده" if o["status"] == "accepted" else "❌ رد شده")
                return jsonify({
                    "success": True, "status": status_fa, "cp": f"{o.get('cp',0):,}", 
                    "price": f"{o.get('final_price',0):,}", "date": o.get('date','')
                })
        return jsonify({"success": False, "message": "یافت نشد"}), 404
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app_web.route("/api/check_coupon", methods=["POST"])
def check_coupon():
    code = request.get_json().get("code", "").strip().upper()
    for c in load_data().get("coupons", []):
        if c["code"] == code and c["active"]:
            return jsonify({"success": True, "type": c["type"], "amount": c["amount"]})
    return jsonify({"success": False, "message": "کد نامعتبر"}), 400

@app_web.route("/api/payment_info", methods=["POST"])
def payment_info():
    try:
        data = request.form
        db = load_data()
        oid = db.get("next_order_id", 1)
        
        receipt = request.files.get('receipt')
        receipt_path = ""
        if receipt:
            receipt_path = os.path.join(BASE_DIR, f"receipt_{oid}.jpg")
            receipt.save(receipt_path)

        order = {
            "id": oid, "code": make_code(), "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "cp": int(data.get("cp", 0)), "antiban": data.get("antiban")=="true", "speed": data.get("speed", "normal"),
            "base_price": int(data.get("totalPrice", 0)), "discount_amount": int(data.get("discountAmount", 0)), "final_price": int(data.get("finalPrice", 0)),
            "sender_card": data.get("senderCard", ""), "sent_amount": data.get("sentAmount", ""), "sent_time": data.get("sentTime", ""),
            "email": "", "pass": "", "rubika": "", "desc": "",
            "status": "pending_payment"
        }
        
        db["orders"].append(order)
        db["next_order_id"] = oid + 1
        save_data(db)
        
        send_payment_msg(order, receipt_path)
        return jsonify({"success": True, "order_code": order["code"]})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app_web.route("/api/final_order", methods=["POST"])
def final_order():
    try:
        data = request.get_json()
        code = data.get("order_code")
        db = load_data()
        
        for o in db["orders"]:
            if o["code"] == code:
                o["email"] = data.get("email", "")
                o["pass"] = data.get("pass", "")
                o["rubika"] = data.get("rubika", "")
                o["desc"] = data.get("desc", "")
                o["status"] = "pending"
                break
        
        save_data(db)
        send_account_msg(code)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

# ================= ارسال به تلگرام =================
def send_payment_msg(order, receipt_path):
    if not bot_app: return
    try:
        speed_text = "فوری" if order['speed'] == 'fast' else "زمان‌بر"
        text = (
            f"💳 **اطلاعات پرداخت (سفارش {order['code']})**\n\n"
            f"💎 {order['cp']:,} CP | 🛡️ {'✅' if order['antiban'] else '❌'} | ⚡ {speed_text}\n"
            f"💰 مبلغ نهایی: {order['final_price']:,} ت\n"
            f"🔢 کارت مبدا: `{order['sender_card']}`\n"
            f"⏰ ساعت: {order['sent_time']}"
        )
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        if receipt_path and os.path.exists(receipt_path):
            with open(receipt_path, 'rb') as photo:
                loop.run_until_complete(bot_app.bot.send_photo(chat_id=GROUP_ID, photo=photo, caption=text, parse_mode="Markdown"))
            os.remove(receipt_path)
        else:
            loop.run_until_complete(bot_app.bot.send_message(chat_id=GROUP_ID, text=text, parse_mode="Markdown"))
        loop.close()
    except Exception as e: print(f"TG Error: {e}")

def send_account_msg(code):
    if not bot_app: return
    db = load_data()
    order = next((o for o in db["orders"] if o["code"] == code), None)
    if not order: return
    try:
        text = (
            f"👤 **اطلاعات اکانت (سفارش {order['code']})**\n\n"
            f"📧 ایمیل: `{order['email']}`\n"
            f"🔑 رمز: `{order['pass']}`\n"
            f"💬 روبیکا: {order['rubika']}\n"
            f"📝 توضیحات: {order['desc'] or 'ندارد'}"
        )
        keyboard = [[InlineKeyboardButton("✅ تأیید", callback_data=f"ok_{order['id']}"), InlineKeyboardButton("❌ رد", callback_data=f"no_{order['id']}")]]
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(bot_app.bot.send_message(chat_id=GROUP_ID, text=text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)))
        loop.close()
    except Exception as e: print(f"TG Error: {e}")

# ================= پنل ادمین =================
def get_main_menu():
    return [
        [InlineKeyboardButton("📦 سفارشات", callback_data="menu_orders"), InlineKeyboardButton("📊 آمار", callback_data="menu_stats")],
        [InlineKeyboardButton("📝 ویرایش متن‌ها", callback_data="menu_texts")],
        [InlineKeyboardButton("💰 تنظیم قیمت‌ها", callback_data="menu_prices"), InlineKeyboardButton("🎟️ کد تخفیف", callback_data="menu_coupons")],
        [InlineKeyboardButton("🎁 تخفیف ویژه", callback_data="menu_special")],
        [InlineKeyboardButton("💳 تنظیم کارت", callback_data="menu_card"), InlineKeyboardButton("🔐 باز/بسته", callback_data="menu_toggle_reg")],
    ]

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    USER_STATES.pop(ADMIN_ID, None)
    await update.message.reply_text("🎮 **پنل مدیریت PhoenixCheat**", reply_markup=InlineKeyboardMarkup(get_main_menu()), parse_mode="Markdown")

async def button_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    db = load_data()
    s = db["settings"]

    if data == "back":
        USER_STATES.pop(ADMIN_ID, None)
        await query.edit_message_text("🎮 **پنل مدیریت PhoenixCheat**", reply_markup=InlineKeyboardMarkup(get_main_menu()), parse_mode="Markdown")

    # --- آمار دقیق ---
    elif data == "menu_stats":
        orders = db.get("orders", [])
        total_orders = len(orders)
        accepted = len([o for o in orders if o.get('status') == 'accepted'])
        pending = len([o for o in orders if o.get('status') == 'pending' or o.get('status') == 'pending_payment'])
        total_income = sum(o.get('final_price', 0) for o in orders if o.get('status') == 'accepted')
        
        text = (
            f"📊 **آمار کامل فروشگاه**\n\n"
            f"📦 کل سفارشات: {total_orders}\n"
            f"✅ تایید شده: {accepted}\n"
            f"⏳ در انتظار: {pending}\n"
            f"💰 مجموع درآمد (تایید شده): {total_income:,} تومان"
        )
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="back")]]), parse_mode="Markdown")

    # --- متن ها ---
    elif data == "menu_texts":
        kb = [
            [InlineKeyboardButton("خوش‌آمد ۱", callback_data="txt_welcome_text1"), InlineKeyboardButton("خوش‌آمد ۲", callback_data="txt_welcome_text2")],
            [InlineKeyboardButton("درباره ما", callback_data="txt_about_text"), InlineKeyboardButton("اعتماد", callback_data="txt_trust_text")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="back")]
        ]
        await query.edit_message_text("کدوم متن رو میخوای عوض کنی؟", reply_markup=InlineKeyboardMarkup(kb))
    elif data.startswith("txt_"):
        key = data.replace("txt_", "")
        USER_STATES[ADMIN_ID] = {"state": f"waiting_text_{key}"}
        current = db["texts"].get(key, "ندارد")
        await query.edit_message_text(f"متن فعلی:\n{current}\n\nمتن جدید رو بفرست:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 لغو", callback_data="back")]]))

    # --- قیمت ها ---
    elif data == "menu_prices":
        kb = [
            [InlineKeyboardButton("⚙️ نرخ متغیر (هر 1000)", callback_data="var_price")],
            [InlineKeyboardButton("📦 پکیج‌های تخفیف‌دار", callback_data="pkg_list")],
            [InlineKeyboardButton("🛡️ قیمت انتی بن و فوری", callback_data="extras_price")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="back")]
        ]
        await query.edit_message_text("💰 تنظیمات قیمت:", reply_markup=InlineKeyboardMarkup(kb))
    elif data == "var_price":
        USER_STATES[ADMIN_ID] = {"state": "waiting_price_var"}
        await query.edit_message_text(f"نرخ فعلی: {s.get('price_per_1000', 25000):,} ت\nنرخ جدید (هر 1000) رو بفرست:")
    elif data == "extras_price":
        USER_STATES[ADMIN_ID] = {"state": "waiting_price_antiban"}
        await query.edit_message_text(f"قیمت فعلی انتی بن: {s['price_antiban']:,} ت\nقیمت جدید انتی بن رو بفرست:")
    
    # --- پکیج ها (با قابلیت حذف) ---
    elif data == "pkg_list":
        text = "📦 **مدیریت پکیج‌ها**\n\nبرای ویرایش یا حذف، روی دکمه‌ها بزن:\n"
        kb = []
        for i, pkg in enumerate(s.get("custom_packages", [])):
            text += f"🔹 {pkg['cp']:,} CP = {pkg['price']:,} ت\n"
            kb.append([
                InlineKeyboardButton(f"✏️ ویرایش {pkg['cp']:,}", callback_data=f"edit_pkg_{i}"),
                InlineKeyboardButton(f"🗑️ حذف", callback_data=f"del_pkg_{i}")
            ])
        kb.append([InlineKeyboardButton("➕ افزودن پکیج جدید", callback_data="add_pkg")])
        kb.append([InlineKeyboardButton("🔙 بازگشت", callback_data="menu_prices")])
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
    
    elif data.startswith("del_pkg_"):
        idx = int(data.split("_")[2])
        try:
            s["custom_packages"].pop(idx)
            save_data(db)
            await query.answer("پکیج حذف شد!", show_alert=True)
            await button_handler(update, ctx)
        except:
            await query.answer("خطا در حذف!", show_alert=True)

    elif data == "add_pkg":
        USER_STATES[ADMIN_ID] = {"state": "waiting_pkg_cp"}
        await query.edit_message_text("تعداد CP رو بفرست:")
    elif data.startswith("edit_pkg_"):
        idx = int(data.split("_")[2])
        USER_STATES[ADMIN_ID] = {"state": "waiting_pkg_price", "idx": idx}
        await query.edit_message_text("قیمت جدید رو بفرست:")

    # --- تخفیف ویژه ---
    elif data == "menu_special":
        code = s.get("special_coupon_code", "تنظیم نشده")
        end = s.get("special_coupon_end_time", "تنظیم نشده")
        if end != "تنظیم نشده" and end:
            end = datetime.fromtimestamp(int(end)).strftime('%Y/%m/%d %H:%M')
        kb = [
            [InlineKeyboardButton("✏️ تغییر کد", callback_data="sd_set_code")],
            [InlineKeyboardButton("⏳ تنظیم زمان", callback_data="sd_set_time")],
            [InlineKeyboardButton("❌ حذف کامل", callback_data="sd_clear")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="back")]
        ]
        await query.edit_message_text(f"🎁 کد: `{code}`\n⏰ پایان: {end}", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
    elif data == "sd_set_code":
        USER_STATES[ADMIN_ID] = {"state": "waiting_sd_code"}
        await query.edit_message_text("کد جدید رو بفرست:")
    elif data == "sd_set_time":
        now = datetime.now() + timedelta(days=1)
        USER_STATES[ADMIN_ID] = {"state": "sd_date", "y": now.year, "m": now.month, "d": now.day, "h": now.hour, "min": now.minute}
        await show_date_picker(query, USER_STATES[ADMIN_ID])
    elif data == "sd_clear":
        s["special_coupon_code"] = ""
        s["special_coupon_end_time"] = ""
        save_data(db)
        await query.answer("حذف شد!", show_alert=True)
        await button_handler(update, ctx)
    elif data.startswith("dp_"):
        parts = data.split("_")
        field, action = parts[1], parts[2]
        st = USER_STATES[ADMIN_ID]
        dt = datetime(st['y'], st['m'], st['d'], st['h'], st['min'])
        
        if field == 'y': dt = dt.replace(year=dt.year + (1 if action=='up' else -1))
        elif field == 'm':
            m = dt.month + (1 if action=='up' else -1)
            dt = dt.replace(month=(m-1)%12+1, year=dt.year + (m//13))
        elif field == 'd': dt += timedelta(days=1 if action=='up' else -1)
        elif field == 'h': dt += timedelta(hours=1 if action=='up' else -1)
        elif field == 'min': dt += timedelta(minutes=1 if action=='up' else -1)
        
        USER_STATES[ADMIN_ID].update({"y": dt.year, "m": dt.month, "d": dt.day, "h": dt.hour, "min": dt.minute})
        await show_date_picker(query, USER_STATES[ADMIN_ID])
    elif data == "dp_save":
        st = USER_STATES[ADMIN_ID]
        dt = datetime(st['y'], st['m'], st['d'], st['h'], st['min'])
        s["special_coupon_end_time"] = str(int(dt.timestamp()))
        save_data(db)
        USER_STATES.pop(ADMIN_ID)
        await query.edit_message_text("✅ تاریخ تنظیم شد.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="menu_special")]]))

    # --- کد تخفیف ---
    elif data == "menu_coupons":
        kb = [[InlineKeyboardButton("➕ ساخت کد تخفیف", callback_data="add_coup")], [InlineKeyboardButton("🔙 بازگشت", callback_data="back")]]
        text = "🎟️ کدهای تخفیف:\n"
        for c in db.get("coupons", []): 
            type_str = f"{c['amount']}%" if c['type'] == 'percent' else f"{c['amount']:,} ت"
            text += f"`{c['code']}` - {type_str}\n"
            kb.insert(0, [InlineKeyboardButton(f"🗑️ حذف {c['code']}", callback_data=f"del_coup_{c['code']}")])
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
    elif data.startswith("del_coup_"):
        code = data.split("_")[2]
        db["coupons"] = [c for c in db["coupons"] if c["code"] != code]
        save_data(db)
        await query.answer("حذف شد!", show_alert=True)
        await button_handler(update, ctx)
    elif data == "add_coup":
        USER_STATES[ADMIN_ID] = {"state": "waiting_coupon_code"}
        await query.edit_message_text("کد تخفیف رو بفرست:")
    elif data == "coup_type_percent" or data == "coup_type_fixed":
        t = "percent" if data == "coup_type_percent" else "fixed"
        USER_STATES[ADMIN_ID] = {"state": f"waiting_coupon_amount_{t}", "code": USER_STATES[ADMIN_ID]["code"]}
        await query.edit_message_text("مقدار تخفیف رو بفرست:")
        
    # --- کارت ---
    elif data == "menu_card":
        USER_STATES[ADMIN_ID] = {"state": "waiting_card"}
        await query.edit_message_text("شماره کارت و نام صاحب کارت رو با این فرمت بفرست:\n`6219861452724577 - یوسف موسوی`", parse_mode="Markdown")
        
    # --- سفارشات ---
    elif data == "menu_orders":
        kb = []
        for o in db.get("orders", [])[-5:][::-1]:
            status = "⏳" if o.get('status') == 'pending' or o.get('status') == 'pending_payment' else ("✅" if o.get('status') == 'accepted' else "❌")
            kb.append([InlineKeyboardButton(f"{status} {o['code']} | {o.get('final_price',0):,} ت", callback_data=f"view_{o['id']}")])
        kb.append([InlineKeyboardButton("🔙 بازگشت", callback_data="back")])
        await query.edit_message_text("📦 سفارشات اخیر:", reply_markup=InlineKeyboardMarkup(kb))
    elif data.startswith("view_"):
        oid = int(data.split("_")[1])
        order = next((o for o in db["orders"] if o["id"] == oid), None)
        if not order: return
        text = f"🔢 {order['code']}\n📧 {order.get('email','ثبت نشده')}\n🔑 {order.get('pass','ثبت نشده')}\n💳 {order.get('sender_card','')}\n💰 مبلغ: {order.get('final_price',0):,} ت"
        kb = [[InlineKeyboardButton("✅ تایید", callback_data=f"ok_{oid}"), InlineKeyboardButton("❌ رد", callback_data=f"no_{oid}")], [InlineKeyboardButton("🔙 بازگشت", callback_data="menu_orders")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))
    elif data.startswith("ok_") or data.startswith("no_"):
        oid = int(data.split("_")[1])
        status = "accepted" if data.startswith("ok_") else "rejected"
        for o in db["orders"]:
            if o["id"] == oid: o["status"] = status; save_data(db); break
        await query.answer("وضعیت تغییر کرد.", show_alert=True)
        await button_handler(update, ctx)
    
    elif data == "menu_toggle_reg":
        s["registration_open"] = not s.get("registration_open", True)
        save_data(db)
        await query.answer("وضعیت ثبت‌نام تغییر کرد.", show_alert=True)
        await button_handler(update, ctx)

async def show_date_picker(query, state):
    dt = datetime(state['y'], state['m'], state['d'], state['h'], state['min'])
    text = f"📅 تاریخ انقضا:\n**{dt.strftime('%Y/%m/%d - %H:%M')}**\n\nبا دکمه‌ها تنظیم کن:"
    kb = [
        [InlineKeyboardButton("⬆️ سال", callback_data="dp_y_up"), InlineKeyboardButton("⬇️ سال", callback_data="dp_y_dn")],
        [InlineKeyboardButton("⬆️ ماه", callback_data="dp_m_up"), InlineKeyboardButton("⬇️ ماه", callback_data="dp_m_dn")],
        [InlineKeyboardButton("⬆️ روز", callback_data="dp_d_up"), InlineKeyboardButton("⬇️ روز", callback_data="dp_d_dn")],
        [InlineKeyboardButton("⬆️ ساعت", callback_data="dp_h_up"), InlineKeyboardButton("⬇️ ساعت", callback_data="dp_h_dn")],
        [InlineKeyboardButton("⬆️ دقیقه", callback_data="dp_min_up"), InlineKeyboardButton("⬇️ دقیقه", callback_data="dp_min_dn")],
        [InlineKeyboardButton("✅ ثبت تاریخ", callback_data="dp_save")]
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    st = USER_STATES.get(ADMIN_ID)
    if not st: return
    state = st.get("state")
    text = update.message.text.strip()
    db = load_data()
    s = db["settings"]

    try:
        if state == "waiting_price_var":
            s["price_per_1000"] = int(text); save_data(db)
            await update.message.reply_text("✅ نرخ متغیر تغییر کرد.")
        elif state == "waiting_price_antiban":
            s["price_antiban"] = int(text); save_data(db)
            await update.message.reply_text("✅ قیمت انتی بن تغییر کرد.")
        elif state == "waiting_pkg_cp":
            st["cp"] = int(text); st["state"] = "waiting_pkg_price"
            await update.message.reply_text("حالا قیمت این پکیج رو بفرست:")
            return
        elif state == "waiting_pkg_price":
            s["custom_packages"].append({"cp": st["cp"], "price": int(text)}); save_data(db)
            await update.message.reply_text("✅ پکیج اضافه شد.")
        elif state == "waiting_card":
            parts = text.split("-"); s["card_number"] = parts[0].strip()
            if len(parts) > 1: s["card_holder"] = parts[1].strip()
            save_data(db); await update.message.reply_text("✅ کارت تغییر کرد.")
        elif state.startswith("waiting_text_"):
            key = state.replace("waiting_text_", "")
            db["texts"][key] = text; save_data(db)
            await update.message.reply_text("✅ متن تغییر کرد.")
        elif state == "waiting_sd_code":
            s["special_coupon_code"] = text.upper(); save_data(db)
            await update.message.reply_text("✅ کد ویژه تغییر کرد.")
        elif state == "waiting_coupon_code":
            st["code"] = text.upper(); st["state"] = "waiting_coupon_type"
            await update.message.reply_text("نوع تخفیف؟", reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("درصدی (%)", callback_data="coup_type_percent")],
                [InlineKeyboardButton("مبلغی (تومان)", callback_data="coup_type_fixed")]
            ]))
            return
        elif state == "waiting_coupon_amount_percent":
            db["coupons"].append({"code": st["code"], "type": "percent", "amount": int(text), "active": True}); save_data(db)
            await update.message.reply_text("✅ کد ساخته شد.")
        elif state == "waiting_coupon_amount_fixed":
            db["coupons"].append({"code": st["code"], "type": "fixed", "amount": int(text), "active": True}); save_data(db)
            await update.message.reply_text("✅ کد ساخته شد.")
    except ValueError:
        await update.message.reply_text("❌ عدد نامعتبر.")
        return
    USER_STATES.pop(ADMIN_ID)
    await update.message.reply_text("🎮 پنل:", reply_markup=InlineKeyboardMarkup(get_main_menu()))

# ================= اجرای سرور و ربات =================
def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app_web.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

def run_bot():
    global bot_app
    bot_app = Application.builder().token(BOT_TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CallbackQueryHandler(button_handler))
    bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    print("🚀 Bot is polling...")
    bot_app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    print("🌐 Starting Web Server...")
    threading.Thread(target=run_flask, daemon=True).start()
    import time
    time.sleep(2) 
    print("🤖 Starting Bot...")
    run_bot()