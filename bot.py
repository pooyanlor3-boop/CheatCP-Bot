# -*- coding: utf-8 -*-
# PhoenixCheat Bot - Final Stable + Fixed Toggle & Confirm
# JSONBin + Robust Event Loop + Better Error Handling

import json
import os
import random
import string
import threading
import asyncio
import time
from datetime import datetime, timedelta

import requests
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# ==========================================
# تنظیمات
# ==========================================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
GROUP_ID = int(os.environ.get("GROUP_ID", "0"))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app_web = Flask(__name__, static_folder=BASE_DIR)
CORS(app_web)

bot_app = None
USER_STATES = {}

# ==========================================
# دیتای پیش‌فرض
# ==========================================
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
        "special_discount_text": "",
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

# ==========================================
# دیتابیس JSONBin
# ==========================================
def load_data():
    bin_id = os.environ.get("JSONBIN_ID")
    api_key = os.environ.get("JSONBIN_KEY")

    if not bin_id or not api_key:
        print("⚠️ JSONBIN_ID یا JSONBIN_KEY تنظیم نشده!")
        return DEFAULT_DATA.copy()

    try:
        url = f"https://api.jsonbin.io/v3/b/{bin_id}/latest"
        headers = {"X-Master-Key": api_key}
        res = requests.get(url, headers=headers, timeout=12)

        if res.status_code == 200:
            data = res.json().get("record", {})
            if not isinstance(data, dict) or "orders" not in data or "settings" not in data:
                print("⚠️ ساختار دیتا نامعتبر بود، مقدار پیش‌فرض ذخیره شد.")
                save_data(DEFAULT_DATA)
                return DEFAULT_DATA.copy()
            return data
        else:
            print(f"⚠️ JSONBin Load Error: {res.status_code}")
            return DEFAULT_DATA.copy()
    except Exception as e:
        print(f"⚠️ JSONBin Load Exception: {e}")
        return DEFAULT_DATA.copy()


def save_data(data):
    bin_id = os.environ.get("JSONBIN_ID")
    api_key = os.environ.get("JSONBIN_KEY")

    if not bin_id or not api_key:
        print("⚠️ JSONBIN_ID یا JSONBIN_KEY تنظیم نشده!")
        return False

    try:
        url = f"https://api.jsonbin.io/v3/b/{bin_id}"
        headers = {
            "Content-Type": "application/json",
            "X-Master-Key": api_key
        }
        res = requests.put(url, json=data, headers=headers, timeout=12)
        if res.status_code == 200:
            return True
        else:
            print(f"❌ JSONBin Save Error: {res.status_code} - {res.text[:200]}")
            return False
    except Exception as e:
        print(f"❌ JSONBin Save Exception: {e}")
        return False


def make_code():
    return f"ORD-{''.join(random.choices(string.ascii_uppercase + string.digits, k=6))}"


# ==========================================
# کمک‌کننده برای اجرای async
# ==========================================
def run_async(coro):
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(coro)
        loop.close()
        return result
    except Exception as e:
        print(f"❌ run_async Error: {e}")
        return None


# ==========================================
# API های سایت
# ==========================================
@app_web.route("/")
def index():
    return send_from_directory(BASE_DIR, "index.html")


@app_web.route("/api/settings", methods=["GET"])
def get_settings():
    try:
        db = load_data()
        return jsonify({
            "texts": db.get("texts", {}),
            "settings": db.get("settings", {}),
            "special_coupon": db["settings"].get("special_coupon_code", "")
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app_web.route("/api/track", methods=["POST"])
def track_order():
    try:
        body = request.get_json(silent=True) or {}
        code = str(body.get("code", "")).strip().upper()

        if not code:
            return jsonify({"success": False, "message": "کد وارد نشده"}), 400

        db = load_data()
        for o in db.get("orders", []):
            if o.get("code") == code:
                status = o.get("status", "pending")
                if status in ("pending", "pending_payment"):
                    status_fa = "⏳ در انتظار بررسی"
                elif status == "accepted":
                    status_fa = "✅ تایید شده"
                else:
                    status_fa = "❌ رد شده"

                return jsonify({
                    "success": True,
                    "status": status_fa,
                    "cp": f"{o.get('cp', 0):,}",
                    "price": f"{o.get('final_price', 0):,}",
                    "date": o.get("date", "")
                })

        return jsonify({"success": False, "message": "سفارشی با این کد یافت نشد"}), 404
    except Exception as e:
        return jsonify({"success": False, "message": "خطای سرور"}), 500


@app_web.route("/api/check_coupon", methods=["POST"])
def check_coupon():
    try:
        body = request.get_json(silent=True) or {}
        code = str(body.get("code", "")).strip().upper()

        if not code:
            return jsonify({"success": False, "message": "کد وارد نشده"}), 400

        db = load_data()
        for c in db.get("coupons", []):
            if c.get("code") == code and c.get("active", True):
                return jsonify({
                    "success": True,
                    "type": c.get("type", "fixed"),
                    "amount": c.get("amount", 0)
                })

        return jsonify({"success": False, "message": "کد نامعتبر است"}), 400
    except Exception as e:
        return jsonify({"success": False, "message": "خطای سرور"}), 500


@app_web.route("/api/payment_info", methods=["POST"])
def payment_info():
    try:
        db = load_data()
        settings = db.get("settings", {})

        if not settings.get("registration_open", True):
            return jsonify({"success": False, "message": "سایت فعلاً بسته است"}), 403

        data = request.form
        oid = db.get("next_order_id", 1)

        receipt = request.files.get("receipt")
        receipt_path = None
        if receipt and receipt.filename:
            receipt_path = os.path.join(BASE_DIR, f"temp_receipt_{oid}_{int(time.time())}.jpg")
            receipt.save(receipt_path)

        order = {
            "id": oid,
            "code": make_code(),
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "cp": int(data.get("cp", 0) or 0),
            "antiban": str(data.get("antiban", "")).lower() == "true",
            "speed": data.get("speed", "normal"),
            "base_price": int(data.get("totalPrice", 0) or 0),
            "discount_amount": int(data.get("discountAmount", 0) or 0),
            "final_price": int(data.get("finalPrice", 0) or 0),
            "sender_card": data.get("senderCard", ""),
            "sent_amount": data.get("sentAmount", ""),
            "sent_time": data.get("sentTime", ""),
            "email": "",
            "pass": "",
            "rubika": "",
            "desc": "",
            "status": "pending_payment"
        }

        db["orders"].append(order)
        db["next_order_id"] = oid + 1
        save_data(db)

        send_payment_msg(order, receipt_path)

        if receipt_path and os.path.exists(receipt_path):
            try:
                os.remove(receipt_path)
            except:
                pass

        return jsonify({"success": True, "order_code": order["code"]})
    except Exception as e:
        print(f"payment_info Error: {e}")
        return jsonify({"success": False, "message": "خطا در ثبت اطلاعات پرداخت"}), 500


@app_web.route("/api/final_order", methods=["POST"])
def final_order():
    try:
        db = load_data()
        settings = db.get("settings", {})

        if not settings.get("registration_open", True):
            return jsonify({"success": False, "message": "سایت فعلاً بسته است"}), 403

        data = request.get_json(silent=True) or {}
        code = str(data.get("order_code", "")).strip()

        if not code:
            return jsonify({"success": False, "message": "کد سفارش نامعتبر"}), 400

        found = False
        for o in db.get("orders", []):
            if o.get("code") == code:
                o["email"] = data.get("email", "")
                o["pass"] = data.get("pass", "")
                o["rubika"] = data.get("rubika", "")
                o["desc"] = data.get("desc", "")
                o["status"] = "pending"
                found = True
                break

        if not found:
            return jsonify({"success": False, "message": "سفارش یافت نشد"}), 404

        save_data(db)
        send_account_msg(code)
        return jsonify({"success": True})
    except Exception as e:
        print(f"final_order Error: {e}")
        return jsonify({"success": False, "message": "خطا در ثبت نهایی"}), 500


# ==========================================
# ارسال پیام به تلگرام
# ==========================================
def send_payment_msg(order, receipt_path=None):
    if not bot_app:
        return

    try:
        speed_text = "فوری ⚡" if order.get("speed") == "fast" else "زمان‌بر"
        antiban_text = "✅" if order.get("antiban") else "❌"

        text = (
            f"💳 **اطلاعات پرداخت**\n"
            f"🔢 کد: `{order['code']}`\n\n"
            f"💎 {order.get('cp', 0):,} CP\n"
            f"🛡️ آنتی‌بن: {antiban_text}\n"
            f"⚡ سرعت: {speed_text}\n"
            f"💰 مبلغ نهایی: {order.get('final_price', 0):,} تومان\n\n"
            f"🔢 کارت مبدا: `{order.get('sender_card', '-')}`\n"
            f"⏰ ساعت واریز: {order.get('sent_time', '-')}"
        )

        async def _send():
            if receipt_path and os.path.exists(receipt_path):
                with open(receipt_path, "rb") as photo:
                    await bot_app.bot.send_photo(
                        chat_id=GROUP_ID,
                        photo=photo,
                        caption=text,
                        parse_mode="Markdown"
                    )
            else:
                await bot_app.bot.send_message(
                    chat_id=GROUP_ID,
                    text=text,
                    parse_mode="Markdown"
                )

        run_async(_send())
    except Exception as e:
        print(f"send_payment_msg Error: {e}")


def send_account_msg(code):
    if not bot_app:
        return

    try:
        db = load_data()
        order = next((o for o in db.get("orders", []) if o.get("code") == code), None)
        if not order:
            return

        text = (
            f"👤 **اطلاعات اکانت**\n"
            f"🔢 کد: `{order['code']}`\n\n"
            f"📧 ایمیل: `{order.get('email', '-')}`\n"
            f"🔑 رمز: `{order.get('pass', '-')}`\n"
            f"💬 روبیکا: {order.get('rubika', '-')}\n"
            f"📝 توضیحات: {order.get('desc') or 'ندارد'}"
        )

        keyboard = [[
            InlineKeyboardButton("✅ تأیید", callback_data=f"ok_{order['id']}"),
            InlineKeyboardButton("❌ رد", callback_data=f"no_{order['id']}")
        ]]

        async def _send():
            await bot_app.bot.send_message(
                chat_id=GROUP_ID,
                text=text,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

        run_async(_send())
    except Exception as e:
        print(f"send_account_msg Error: {e}")


# ==========================================
# پنل ادمین
# ==========================================
def get_main_menu(db=None):
    if db is None:
        db = load_data()
    is_open = db.get("settings", {}).get("registration_open", True)
    status_text = "🟢 سایت باز است" if is_open else "🔴 سایت بسته است"

    return [
        [InlineKeyboardButton("📦 سفارشات", callback_data="menu_orders"),
         InlineKeyboardButton("📊 آمار", callback_data="menu_stats")],
        [InlineKeyboardButton("📝 ویرایش متن‌ها", callback_data="menu_texts")],
        [InlineKeyboardButton("💰 تنظیم قیمت‌ها", callback_data="menu_prices"),
         InlineKeyboardButton("🎟️ کد تخفیف", callback_data="menu_coupons")],
        [InlineKeyboardButton("🎁 تخفیف ویژه", callback_data="menu_special")],
        [InlineKeyboardButton("💳 تنظیم کارت", callback_data="menu_card")],
        [InlineKeyboardButton(status_text, callback_data="menu_toggle_reg")],
    ]


async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    USER_STATES.pop(ADMIN_ID, None)
    db = load_data()
    await update.message.reply_text(
        "🎮 **پنل مدیریت PhoenixCheat**",
        reply_markup=InlineKeyboardMarkup(get_main_menu(db)),
        parse_mode="Markdown"
    )


async def button_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    db = load_data()
    s = db.get("settings", {})

    try:
        if data == "back":
            USER_STATES.pop(ADMIN_ID, None)
            await query.edit_message_text(
                "🎮 **پنل مدیریت PhoenixCheat**",
                reply_markup=InlineKeyboardMarkup(get_main_menu(db)),
                parse_mode="Markdown"
            )

        # آمار
        elif data == "menu_stats":
            orders = db.get("orders", [])
            total = len(orders)
            accepted = len([o for o in orders if o.get("status") == "accepted"])
            pending = len([o for o in orders if o.get("status") in ("pending", "pending_payment")])
            income = sum(o.get("final_price", 0) for o in orders if o.get("status") == "accepted")

            text = (
                f"📊 **آمار کامل**\n\n"
                f"📦 کل سفارشات: {total}\n"
                f"✅ تایید شده: {accepted}\n"
                f"⏳ در انتظار: {pending}\n"
                f"💰 درآمد تایید شده: {income:,} تومان"
            )
            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="back")]]),
                parse_mode="Markdown"
            )

        # متن‌ها
        elif data == "menu_texts":
            kb = [
                [InlineKeyboardButton("خوش‌آمد ۱", callback_data="txt_welcome_text1"),
                 InlineKeyboardButton("خوش‌آمد ۲", callback_data="txt_welcome_text2")],
                [InlineKeyboardButton("درباره ما", callback_data="txt_about_text"),
                 InlineKeyboardButton("اعتماد", callback_data="txt_trust_text")],
                [InlineKeyboardButton("🔙 بازگشت", callback_data="back")]
            ]
            await query.edit_message_text("کدوم متن رو می‌خوای عوض کنی؟", reply_markup=InlineKeyboardMarkup(kb))

        elif data.startswith("txt_"):
            key = data.replace("txt_", "")
            USER_STATES[ADMIN_ID] = {"state": f"waiting_text_{key}"}
            current = db.get("texts", {}).get(key, "ندارد")
            await query.edit_message_text(
                f"متن فعلی:\n{current}\n\nمتن جدید رو بفرست:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 لغو", callback_data="back")]])
            )

        # قیمت‌ها
        elif data == "menu_prices":
            kb = [
                [InlineKeyboardButton("⚙️ نرخ متغیر (هر ۱۰۰۰)", callback_data="var_price")],
                [InlineKeyboardButton("📦 پکیج‌های تخفیف‌دار", callback_data="pkg_list")],
                [InlineKeyboardButton("🛡️ قیمت آنتی‌بن و فوری", callback_data="extras_price")],
                [InlineKeyboardButton("🔙 بازگشت", callback_data="back")]
            ]
            await query.edit_message_text("💰 تنظیمات قیمت:", reply_markup=InlineKeyboardMarkup(kb))

        elif data == "var_price":
            USER_STATES[ADMIN_ID] = {"state": "waiting_price_var"}
            await query.edit_message_text(f"نرخ فعلی: {s.get('price_per_1000', 25000):,} تومان\nنرخ جدید رو بفرست:")

        elif data == "extras_price":
            USER_STATES[ADMIN_ID] = {"state": "waiting_price_antiban"}
            await query.edit_message_text(f"قیمت فعلی آنتی‌بن: {s.get('price_antiban', 50000):,} تومان\nقیمت جدید آنتی‌بن رو بفرست:")

        # پکیج‌ها
        elif data == "pkg_list":
            text = "📦 **مدیریت پکیج‌ها**\n\n"
            kb = []
            for i, pkg in enumerate(s.get("custom_packages", [])):
                text += f"🔹 {pkg['cp']:,} CP = {pkg['price']:,} ت\n"
                kb.append([
                    InlineKeyboardButton(f"✏️ {pkg['cp']:,}", callback_data=f"edit_pkg_{i}"),
                    InlineKeyboardButton("🗑️", callback_data=f"del_pkg_{i}")
                ])
            kb.append([InlineKeyboardButton("➕ افزودن پکیج", callback_data="add_pkg")])
            kb.append([InlineKeyboardButton("🔙 بازگشت", callback_data="menu_prices")])
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

        elif data.startswith("del_pkg_"):
            idx = int(data.split("_")[2])
            try:
                s["custom_packages"].pop(idx)
                save_data(db)
                await query.answer("✅ پکیج حذف شد", show_alert=True)
            except:
                await query.answer("❌ خطا در حذف", show_alert=True)
            # برگشت به لیست پکیج
            text = "📦 **مدیریت پکیج‌ها**\n\n"
            kb = []
            for i, pkg in enumerate(s.get("custom_packages", [])):
                text += f"🔹 {pkg['cp']:,} CP = {pkg['price']:,} ت\n"
                kb.append([
                    InlineKeyboardButton(f"✏️ {pkg['cp']:,}", callback_data=f"edit_pkg_{i}"),
                    InlineKeyboardButton("🗑️", callback_data=f"del_pkg_{i}")
                ])
            kb.append([InlineKeyboardButton("➕ افزودن پکیج", callback_data="add_pkg")])
            kb.append([InlineKeyboardButton("🔙 بازگشت", callback_data="menu_prices")])
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

        elif data == "add_pkg":
            USER_STATES[ADMIN_ID] = {"state": "waiting_pkg_cp"}
            await query.edit_message_text("تعداد CP رو بفرست:")

        elif data.startswith("edit_pkg_"):
            idx = int(data.split("_")[2])
            USER_STATES[ADMIN_ID] = {"state": "waiting_pkg_price", "idx": idx}
            await query.edit_message_text("قیمت جدید رو بفرست:")

        # تخفیف ویژه
        elif data == "menu_special":
            code = s.get("special_coupon_code") or "تنظیم نشده"
            end = s.get("special_coupon_end_time") or "تنظیم نشده"
            if end not in ("تنظیم نشده", "") and end:
                try:
                    end = datetime.fromtimestamp(int(end)).strftime("%Y/%m/%d %H:%M")
                except:
                    pass
            kb = [
                [InlineKeyboardButton("✏️ تغییر کد", callback_data="sd_set_code")],
                [InlineKeyboardButton("⏳ تنظیم زمان", callback_data="sd_set_time")],
                [InlineKeyboardButton("❌ حذف کامل", callback_data="sd_clear")],
                [InlineKeyboardButton("🔙 بازگشت", callback_data="back")]
            ]
            await query.edit_message_text(
                f"🎁 کد ویژه: `{code}`\n⏰ پایان: {end}",
                reply_markup=InlineKeyboardMarkup(kb),
                parse_mode="Markdown"
            )

        elif data == "sd_set_code":
            USER_STATES[ADMIN_ID] = {"state": "waiting_sd_code"}
            await query.edit_message_text("کد جدید رو بفرست:")

        elif data == "sd_set_time":
            now = datetime.now() + timedelta(days=1)
            USER_STATES[ADMIN_ID] = {
                "state": "sd_date",
                "y": now.year, "m": now.month, "d": now.day,
                "h": now.hour, "min": now.minute
            }
            await show_date_picker(query, USER_STATES[ADMIN_ID])

        elif data == "sd_clear":
            s["special_coupon_code"] = ""
            s["special_coupon_end_time"] = ""
            s["special_discount_text"] = ""
            save_data(db)
            await query.answer("✅ حذف شد", show_alert=True)
            await query.edit_message_text(
                "🎁 کد ویژه حذف شد.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="back")]])
            )

        elif data.startswith("dp_"):
            parts = data.split("_")
            if len(parts) < 3:
                return
            field, action = parts[1], parts[2]
            st = USER_STATES.get(ADMIN_ID, {})
            try:
                dt = datetime(st["y"], st["m"], st["d"], st["h"], st["min"])
                if field == "y":
                    dt = dt.replace(year=dt.year + (1 if action == "up" else -1))
                elif field == "m":
                    m = dt.month + (1 if action == "up" else -1)
                    if m > 12:
                        dt = dt.replace(year=dt.year + 1, month=1)
                    elif m < 1:
                        dt = dt.replace(year=dt.year - 1, month=12)
                    else:
                        dt = dt.replace(month=m)
                elif field == "d":
                    dt += timedelta(days=1 if action == "up" else -1)
                elif field == "h":
                    dt += timedelta(hours=1 if action == "up" else -1)
                elif field == "min":
                    dt += timedelta(minutes=1 if action == "up" else -1)

                USER_STATES[ADMIN_ID].update({
                    "y": dt.year, "m": dt.month, "d": dt.day,
                    "h": dt.hour, "min": dt.minute
                })
                await show_date_picker(query, USER_STATES[ADMIN_ID])
            except Exception as e:
                print(f"Date picker error: {e}")

        elif data == "dp_save":
            st = USER_STATES.get(ADMIN_ID, {})
            try:
                dt = datetime(st["y"], st["m"], st["d"], st["h"], st["min"])
                s["special_coupon_end_time"] = str(int(dt.timestamp()))
                save_data(db)
                USER_STATES.pop(ADMIN_ID, None)
                await query.edit_message_text(
                    "✅ تاریخ تنظیم شد.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="menu_special")]])
                )
            except Exception as e:
                await query.answer("❌ خطا در ذخیره تاریخ", show_alert=True)

        # کد تخفیف عادی
        elif data == "menu_coupons":
            kb = [[InlineKeyboardButton("➕ ساخت کد تخفیف", callback_data="add_coup")]]
            text = "🎟️ **کدهای تخفیف:**\n\n"
            for c in db.get("coupons", []):
                type_str = f"{c['amount']}%" if c.get("type") == "percent" else f"{c['amount']:,} تومان"
                text += f"`{c['code']}` → {type_str}\n"
                kb.insert(0, [InlineKeyboardButton(f"🗑️ حذف {c['code']}", callback_data=f"del_coup_{c['code']}")])
            kb.append([InlineKeyboardButton("🔙 بازگشت", callback_data="back")])
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

        elif data.startswith("del_coup_"):
            code = data.replace("del_coup_", "")
            db["coupons"] = [c for c in db.get("coupons", []) if c.get("code") != code]
            save_data(db)
            await query.answer("✅ حذف شد", show_alert=True)
            # رفرش لیست
            kb = [[InlineKeyboardButton("➕ ساخت کد تخفیف", callback_data="add_coup")]]
            text = "🎟️ **کدهای تخفیف:**\n\n"
            for c in db.get("coupons", []):
                type_str = f"{c['amount']}%" if c.get("type") == "percent" else f"{c['amount']:,} تومان"
                text += f"`{c['code']}` → {type_str}\n"
                kb.insert(0, [InlineKeyboardButton(f"🗑️ حذف {c['code']}", callback_data=f"del_coup_{c['code']}")])
            kb.append([InlineKeyboardButton("🔙 بازگشت", callback_data="back")])
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

        elif data == "add_coup":
            USER_STATES[ADMIN_ID] = {"state": "waiting_coupon_code"}
            await query.edit_message_text("کد تخفیف رو بفرست:")

        elif data in ("coup_type_percent", "coup_type_fixed"):
            t = "percent" if data == "coup_type_percent" else "fixed"
            st = USER_STATES.get(ADMIN_ID, {})
            USER_STATES[ADMIN_ID] = {"state": f"waiting_coupon_amount_{t}", "code": st.get("code")}
            await query.edit_message_text("مقدار تخفیف رو بفرست:")

        # کارت
        elif data == "menu_card":
            USER_STATES[ADMIN_ID] = {"state": "waiting_card"}
            await query.edit_message_text(
                "شماره کارت و نام صاحب کارت رو با این فرمت بفرست:\n`6219861452724577 - یوسف موسوی`",
                parse_mode="Markdown"
            )

        # سفارشات
        elif data == "menu_orders":
            kb = []
            for o in db.get("orders", [])[-8:][::-1]:
                status = o.get("status", "pending")
                icon = "⏳" if status in ("pending", "pending_payment") else ("✅" if status == "accepted" else "❌")
                kb.append([InlineKeyboardButton(
                    f"{icon} {o.get('code')} | {o.get('final_price', 0):,} ت",
                    callback_data=f"view_{o['id']}"
                )])
            kb.append([InlineKeyboardButton("🔙 بازگشت", callback_data="back")])
            await query.edit_message_text("📦 سفارشات اخیر:", reply_markup=InlineKeyboardMarkup(kb))

        elif data.startswith("view_"):
            oid = int(data.split("_")[1])
            order = next((o for o in db.get("orders", []) if o.get("id") == oid), None)
            if not order:
                await query.answer("سفارش پیدا نشد", show_alert=True)
                return

            text = (
                f"🔢 `{order.get('code')}`\n"
                f"📧 {order.get('email') or 'ثبت نشده'}\n"
                f"🔑 {order.get('pass') or 'ثبت نشده'}\n"
                f"💳 {order.get('sender_card') or '-'}\n"
                f"💰 مبلغ: {order.get('final_price', 0):,} تومان\n"
                f"📅 {order.get('date', '')}"
            )
            kb = [[
                InlineKeyboardButton("✅ تایید", callback_data=f"ok_{oid}"),
                InlineKeyboardButton("❌ رد", callback_data=f"no_{oid}")
            ], [InlineKeyboardButton("🔙 بازگشت", callback_data="menu_orders")]]
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

        # تایید / رد سفارش (بهبود یافته)
        elif data.startswith("ok_") or data.startswith("no_"):
            try:
                oid = int(data.split("_")[1])
                new_status = "accepted" if data.startswith("ok_") else "rejected"

                for o in db.get("orders", []):
                    if o.get("id") == oid:
                        o["status"] = new_status
                        break

                save_data(db)

                status_text = "تایید شد ✅" if new_status == "accepted" else "رد شد ❌"
                await query.answer(status_text, show_alert=True)

                # برگشت به لیست سفارشات بدون کرش
                kb = []
                for o in db.get("orders", [])[-8:][::-1]:
                    status = o.get("status", "pending")
                    icon = "⏳" if status in ("pending", "pending_payment") else ("✅" if status == "accepted" else "❌")
                    kb.append([InlineKeyboardButton(
                        f"{icon} {o.get('code')} | {o.get('final_price', 0):,} ت",
                        callback_data=f"view_{o['id']}"
                    )])
                kb.append([InlineKeyboardButton("🔙 بازگشت", callback_data="back")])
                await query.edit_message_text("📦 سفارشات اخیر:", reply_markup=InlineKeyboardMarkup(kb))

            except Exception as e:
                print(f"Confirm/Reject Error: {e}")
                await query.answer("❌ خطا در تغییر وضعیت", show_alert=True)

        # باز / بسته کردن سایت (نسخه کاملاً درست شده)
        elif data == "menu_toggle_reg":
            current = s.get("registration_open", True)
            s["registration_open"] = not current
            success = save_data(db)

            if success:
                new_status = "باز 🟢" if s["registration_open"] else "بسته 🔴"
                await query.answer(f"سایت الان {new_status} شد", show_alert=True)
            else:
                await query.answer("❌ خطا در ذخیره وضعیت", show_alert=True)

            # آپدیت منو با وضعیت جدید
            await query.edit_message_text(
                "🎮 **پنل مدیریت PhoenixCheat**",
                reply_markup=InlineKeyboardMarkup(get_main_menu(db)),
                parse_mode="Markdown"
            )

    except Exception as e:
        print(f"button_handler Error: {e}")
        try:
            await query.answer("خطایی رخ داد", show_alert=True)
        except:
            pass


async def show_date_picker(query, state):
    try:
        dt = datetime(state["y"], state["m"], state["d"], state["h"], state["min"])
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
    except Exception as e:
        print(f"show_date_picker Error: {e}")


async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    st = USER_STATES.get(ADMIN_ID)
    if not st:
        return

    state = st.get("state")
    text = update.message.text.strip()
    db = load_data()
    s = db.get("settings", {})

    try:
        if state == "waiting_price_var":
            s["price_per_1000"] = int(text)
            save_data(db)
            await update.message.reply_text("✅ نرخ متغیر تغییر کرد.")

        elif state == "waiting_price_antiban":
            s["price_antiban"] = int(text)
            save_data(db)
            USER_STATES[ADMIN_ID] = {"state": "waiting_price_fast"}
            await update.message.reply_text("✅ قیمت آنتی‌بن تغییر کرد.\nحالا قیمت تحویل فوری رو بفرست:")
            return

        elif state == "waiting_price_fast":
            s["price_fast"] = int(text)
            save_data(db)
            await update.message.reply_text("✅ قیمت تحویل فوری تغییر کرد.")

        elif state == "waiting_pkg_cp":
            st["cp"] = int(text)
            st["state"] = "waiting_pkg_price"
            await update.message.reply_text("حالا قیمت این پکیج رو بفرست:")
            return

        elif state == "waiting_pkg_price":
            if "idx" in st:
                s["custom_packages"][st["idx"]]["price"] = int(text)
            else:
                s["custom_packages"].append({"cp": st["cp"], "price": int(text)})
            save_data(db)
            await update.message.reply_text("✅ پکیج ذخیره شد.")

        elif state == "waiting_card":
            parts = text.split("-")
            s["card_number"] = parts[0].strip()
            if len(parts) > 1:
                s["card_holder"] = parts[1].strip()
            save_data(db)
            await update.message.reply_text("✅ کارت تغییر کرد.")

        elif state.startswith("waiting_text_"):
            key = state.replace("waiting_text_", "")
            if "texts" not in db:
                db["texts"] = {}
            db["texts"][key] = text
            save_data(db)
            await update.message.reply_text("✅ متن تغییر کرد.")

        elif state == "waiting_sd_code":
            s["special_coupon_code"] = text.upper()
            save_data(db)
            await update.message.reply_text("✅ کد ویژه تغییر کرد.")

        elif state == "waiting_coupon_code":
            st["code"] = text.upper()
            st["state"] = "waiting_coupon_type"
            await update.message.reply_text(
                "نوع تخفیف؟",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("درصدی (%)", callback_data="coup_type_percent")],
                    [InlineKeyboardButton("مبلغی (تومان)", callback_data="coup_type_fixed")]
                ])
            )
            return

        elif state == "waiting_coupon_amount_percent":
            db.setdefault("coupons", []).append({
                "code": st["code"],
                "type": "percent",
                "amount": int(text),
                "active": True
            })
            save_data(db)
            await update.message.reply_text("✅ کد تخفیف ساخته شد.")

        elif state == "waiting_coupon_amount_fixed":
            db.setdefault("coupons", []).append({
                "code": st["code"],
                "type": "fixed",
                "amount": int(text),
                "active": True
            })
            save_data(db)
            await update.message.reply_text("✅ کد تخفیف ساخته شد.")

        else:
            await update.message.reply_text("دستور نامشخص.")

    except ValueError:
        await update.message.reply_text("❌ لطفاً عدد معتبر وارد کن.")
        return
    except Exception as e:
        print(f"handle_text Error: {e}")
        await update.message.reply_text("❌ خطایی رخ داد.")
        return

    USER_STATES.pop(ADMIN_ID, None)
    await update.message.reply_text(
        "🎮 پنل مدیریت:",
        reply_markup=InlineKeyboardMarkup(get_main_menu(db))
    )


# ==========================================
# اجرای سرور و ربات
# ==========================================
def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app_web.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)


def run_bot():
    global bot_app

    if not BOT_TOKEN:
        print("❌ BOT_TOKEN تنظیم نشده!")
        return

    bot_app = Application.builder().token(BOT_TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CallbackQueryHandler(button_handler))
    bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("🚀 Bot is polling...")
    bot_app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    print("🌐 Starting Web Server...")
    threading.Thread(target=run_flask, daemon=True).start()
    time.sleep(2)
    print("🤖 Starting Bot...")
    run_bot()