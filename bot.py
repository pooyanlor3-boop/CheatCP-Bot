# -*- coding: utf-8 -*-
# PhoenixCheat Bot - Full Version with Users + Referral System
# JSONBin + Login + Referral + Balance + Anti-Fake

import json
import os
import random
import string
import threading
import asyncio
import time
import hashlib
from datetime import datetime, timedelta
from concurrent.futures import Future

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
main_loop = None
USER_STATES = {}

# ==========================================
# دیتای پیش‌فرض
# ==========================================
DEFAULT_DATA = {
    "orders": [],
    "next_order_id": 1,
    "users": {},
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
        ],
        # رفرال
        "referral_enabled": True,
        "referral_reward": 25000,
        "referral_title": "سیستم معرفی دوستان (رایگان)",
        "referral_description": "با معرفی دوستات موجودی رایگان بگیر و باهاش سی‌پی بخر!",
        # متن بسته بودن سایت
        "closed_message": "🔒 سایت در حال بروزرسانی است.\n\nلطفاً برای اطلاع از زمان بازگشایی و اخبار مهم، در کانال زیر عضو شوید:",
        "closed_channel": "https://rubika.ir/PhoenixCheat",
        "closed_channel_text": "عضویت در کانال فونیکس چیت"
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
                print("⚠️ ساختار دیتا نامعتبر بود → مقدار پیش‌فرض ذخیره شد")
                save_data(DEFAULT_DATA)
                return DEFAULT_DATA.copy()
            # اطمینان از وجود کلیدهای جدید
            if "users" not in data:
                data["users"] = {}
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
            print(f"❌ JSONBin Save Error: {res.status_code}")
            return False
    except Exception as e:
        print(f"❌ JSONBin Save Exception: {e}")
        return False


def make_code(length=6):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))


def make_order_code():
    return f"ORD-{''.join(random.choices(string.ascii_uppercase + string.digits, k=6))}"


def get_client_ip():
    if request.headers.get("X-Forwarded-For"):
        return request.headers.get("X-Forwarded-For").split(",")[0].strip()
    return request.remote_addr or "unknown"


# ==========================================
# ارسال امن به تلگرام
# ==========================================
def send_telegram_safe(coro):
    global main_loop, bot_app
    if not bot_app or not main_loop or main_loop.is_closed():
        print("❌ Bot loop is not ready")
        return False
    try:
        future = asyncio.run_coroutine_threadsafe(coro, main_loop)
        future.result(timeout=12)
        return True
    except Exception as e:
        print(f"❌ send_telegram_safe Error: {e}")
        return False


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
        s = db.get("settings", {})
        return jsonify({
            "texts": db.get("texts", {}),
            "settings": {
                "card_number": s.get("card_number"),
                "card_holder": s.get("card_holder"),
                "price_per_1000": s.get("price_per_1000", 25000),
                "price_antiban": s.get("price_antiban", 50000),
                "price_fast": s.get("price_fast", 20000),
                "registration_open": s.get("registration_open", True),
                "custom_packages": s.get("custom_packages", []),
                "special_discount_text": s.get("special_discount_text", ""),
                "special_coupon_code": s.get("special_coupon_code", ""),
                "special_coupon_end_time": s.get("special_coupon_end_time", ""),
                "referral_enabled": s.get("referral_enabled", True),
                "referral_reward": s.get("referral_reward", 25000),
                "referral_title": s.get("referral_title", ""),
                "referral_description": s.get("referral_description", ""),
                "closed_message": s.get("closed_message", ""),
                "closed_channel": s.get("closed_channel", ""),
                "closed_channel_text": s.get("closed_channel_text", "")
            },
            "special_coupon": s.get("special_coupon_code", "")
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ==================== سیستم کاربران ====================
@app_web.route("/api/register", methods=["POST"])
def register():
    try:
        data = request.get_json(silent=True) or {}
        rubika = str(data.get("rubika", "")).strip()
        code = str(data.get("code", "")).strip().upper()
        fingerprint = str(data.get("fingerprint", "")).strip()
        ref_code = str(data.get("ref", "")).strip().upper() or None

        # اعتبارسنجی روبیکا
        if not rubika.startswith("@") or len(rubika) < 4:
            return jsonify({"success": False, "message": "آیدی روبیکا باید با @ شروع شود"}), 400

        # اعتبارسنجی کد
        if len(code) < 5 or len(code) > 18:
            return jsonify({"success": False, "message": "کد ورود باید بین ۵ تا ۱۸ کاراکتر باشد"}), 400
        if not all(c.isalnum() for c in code):
            return jsonify({"success": False, "message": "کد ورود فقط می‌تواند شامل حروف انگلیسی و عدد باشد"}), 400

        db = load_data()
        users = db.get("users", {})

        # چک تکراری بودن کد
        if code in users:
            return jsonify({"success": False, "message": "این کد قبلاً استفاده شده، کد دیگری انتخاب کنید"}), 400

        # چک تکراری بودن روبیکا
        for u in users.values():
            if u.get("rubika", "").lower() == rubika.lower():
                return jsonify({"success": False, "message": "این آیدی روبیکا قبلاً ثبت شده"}), 400

        ip = get_client_ip()

        # جلوگیری از رفرال فیک
        is_fake_referral = False
        if ref_code and ref_code in users:
            # چک IP
            for u in users.values():
                if u.get("ip") == ip and u.get("code") != ref_code:
                    is_fake_referral = True
                    break
            # چک fingerprint
            if fingerprint:
                for u in users.values():
                    if u.get("fingerprint") == fingerprint and u.get("code") != ref_code:
                        is_fake_referral = True
                        break

        user = {
            "code": code,
            "rubika": rubika,
            "balance": 0,
            "referral_count": 0,
            "referred_by": None,
            "ip": ip,
            "fingerprint": fingerprint,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "suspended": False
        }

        # اعمال رفرال
        if ref_code and ref_code in users and not is_fake_referral and ref_code != code:
            reward = db["settings"].get("referral_reward", 25000)
            users[ref_code]["balance"] = users[ref_code].get("balance", 0) + reward
            users[ref_code]["referral_count"] = users[ref_code].get("referral_count", 0) + 1
            user["referred_by"] = ref_code

        users[code] = user
        db["users"] = users
        save_data(db)

        # ارسال به گروه
        text = (
            f"🆕 **اکانت جدید ساخته شد**\n\n"
            f"🔑 کد ورود: `{code}`\n"
            f"💬 روبیکا: {rubika}\n"
            f"🌐 IP: `{ip}`\n"
            f"📎 رفرال: {ref_code if ref_code and not is_fake_referral else 'ندارد'}"
        )
        async def _send():
            await bot_app.bot.send_message(chat_id=GROUP_ID, text=text, parse_mode="Markdown")
        send_telegram_safe(_send())

        return jsonify({
            "success": True,
            "code": code,
            "balance": user["balance"],
            "message": "اکانت با موفقیت ساخته شد. حتماً کد ورود را ذخیره کنید!"
        })
    except Exception as e:
        print(f"register Error: {e}")
        return jsonify({"success": False, "message": "خطا در ساخت اکانت"}), 500


@app_web.route("/api/login", methods=["POST"])
def login():
    try:
        data = request.get_json(silent=True) or {}
        code = str(data.get("code", "")).strip().upper()
        fingerprint = str(data.get("fingerprint", "")).strip()

        if not code:
            return jsonify({"success": False, "message": "کد ورود را وارد کنید"}), 400

        db = load_data()
        user = db.get("users", {}).get(code)

        if not user:
            return jsonify({"success": False, "message": "کد ورود اشتباه است"}), 404

        if user.get("suspended"):
            return jsonify({"success": False, "message": "این اکانت تعلیق شده است"}), 403

        # آپدیت fingerprint و IP در صورت نیاز
        ip = get_client_ip()
        user["ip"] = ip
        if fingerprint:
            user["fingerprint"] = fingerprint
        save_data(db)

        return jsonify({
            "success": True,
            "code": code,
            "rubika": user.get("rubika"),
            "balance": user.get("balance", 0),
            "referral_count": user.get("referral_count", 0)
        })
    except Exception as e:
        print(f"login Error: {e}")
        return jsonify({"success": False, "message": "خطا در ورود"}), 500


@app_web.route("/api/user_info", methods=["POST"])
def user_info():
    try:
        data = request.get_json(silent=True) or {}
        code = str(data.get("code", "")).strip().upper()

        db = load_data()
        user = db.get("users", {}).get(code)

        if not user:
            return jsonify({"success": False, "message": "کاربر یافت نشد"}), 404

        if user.get("suspended"):
            return jsonify({"success": False, "message": "اکانت تعلیق شده"}), 403

        return jsonify({
            "success": True,
            "code": code,
            "rubika": user.get("rubika"),
            "balance": user.get("balance", 0),
            "referral_count": user.get("referral_count", 0)
        })
    except Exception as e:
        return jsonify({"success": False, "message": "خطا"}), 500


@app_web.route("/api/generate_code", methods=["GET"])
def generate_code():
    """ساخت کد تصادفی برای کاربر"""
    while True:
        code = make_code(8)
        db = load_data()
        if code not in db.get("users", {}):
            return jsonify({"success": True, "code": code})


# ==================== سفارشات ====================
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
                return jsonify({"success": True, "type": c.get("type", "fixed"), "amount": c.get("amount", 0)})
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
        user_code = str(data.get("user_code", "")).strip().upper()
        oid = db.get("next_order_id", 1)

        # چک کاربر
        user = None
        if user_code:
            user = db.get("users", {}).get(user_code)
            if not user:
                return jsonify({"success": False, "message": "کاربر یافت نشد، دوباره لاگین کنید"}), 401
            if user.get("suspended"):
                return jsonify({"success": False, "message": "اکانت شما تعلیق شده است"}), 403

        receipt = request.files.get("receipt")
        receipt_path = None
        if receipt and receipt.filename:
            receipt_path = os.path.join(BASE_DIR, f"temp_receipt_{oid}_{int(time.time())}.jpg")
            receipt.save(receipt_path)

        # محاسبه موجودی
        balance_used = int(data.get("balance_used", 0) or 0)
        if user and balance_used > 0:
            if balance_used > user.get("balance", 0):
                balance_used = user.get("balance", 0)
            user["balance"] -= balance_used

        order = {
            "id": oid,
            "code": make_order_code(),
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "cp": int(data.get("cp", 0) or 0),
            "antiban": str(data.get("antiban", "")).lower() == "true",
            "speed": data.get("speed", "normal"),
            "base_price": int(data.get("totalPrice", 0) or 0),
            "discount_amount": int(data.get("discountAmount", 0) or 0),
            "balance_used": balance_used,
            "final_price": int(data.get("finalPrice", 0) or 0),
            "sender_card": data.get("senderCard", ""),
            "sent_amount": data.get("sentAmount", ""),
            "sent_time": data.get("sentTime", ""),
            "user_code": user_code,
            "email": "",
            "pass": "",
            "rubika": "",
            "desc": "",
            "status": "pending_payment"
        }

        db["orders"].append(order)
        db["next_order_id"] = oid + 1
        if user:
            db["users"][user_code] = user
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
        return False
    try:
        speed_text = "فوری ⚡" if order.get("speed") == "fast" else "زمان‌بر"
        antiban_text = "✅" if order.get("antiban") else "❌"
        balance_text = f"\n💰 استفاده از موجودی: {order.get('balance_used', 0):,} تومان" if order.get("balance_used") else ""

        text = (
            f"💳 **اطلاعات پرداخت**\n"
            f"🔢 کد: `{order['code']}`\n"
            f"👤 کاربر: `{order.get('user_code', '-')}`\n\n"
            f"💎 {order.get('cp', 0):,} CP\n"
            f"🛡️ آنتی‌بن: {antiban_text}\n"
            f"⚡ سرعت: {speed_text}\n"
            f"💰 مبلغ نهایی: {order.get('final_price', 0):,} تومان{balance_text}\n\n"
            f"🔢 کارت مبدا: `{order.get('sender_card', '-')}`\n"
            f"⏰ ساعت واریز: {order.get('sent_time', '-')}"
        )

        async def _send():
            if receipt_path and os.path.exists(receipt_path):
                with open(receipt_path, "rb") as photo:
                    await bot_app.bot.send_photo(chat_id=GROUP_ID, photo=photo, caption=text, parse_mode="Markdown")
            else:
                await bot_app.bot.send_message(chat_id=GROUP_ID, text=text, parse_mode="Markdown")
        return send_telegram_safe(_send())
    except Exception as e:
        print(f"send_payment_msg Error: {e}")
        return False


def send_account_msg(code):
    if not bot_app:
        return False
    try:
        db = load_data()
        order = next((o for o in db.get("orders", []) if o.get("code") == code), None)
        if not order:
            return False

        text = (
            f"👤 **اطلاعات اکانت**\n"
            f"🔢 کد: `{order['code']}`\n"
            f"👤 کاربر: `{order.get('user_code', '-')}`\n\n"
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
                chat_id=GROUP_ID, text=text, parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        return send_telegram_safe(_send())
    except Exception as e:
        print(f"send_account_msg Error: {e}")
        return False


# ==========================================
# پنل ادمین
# ==========================================
def get_main_menu(db=None):
    if db is None:
        db = load_data()
    is_open = db.get("settings", {}).get("registration_open", True)
    status_text = "🟢 سایت باز است" if is_open else "🔴 سایت بسته است"
    ref_enabled = db.get("settings", {}).get("referral_enabled", True)
    ref_text = "🎁 رفرال: روشن" if ref_enabled else "🎁 رفرال: خاموش"

    return [
        [InlineKeyboardButton("📦 سفارشات", callback_data="menu_orders"),
         InlineKeyboardButton("📊 آمار", callback_data="menu_stats")],
        [InlineKeyboardButton("👥 مدیریت کاربران", callback_data="menu_users")],
        [InlineKeyboardButton("📝 ویرایش متن‌ها", callback_data="menu_texts")],
        [InlineKeyboardButton("💰 تنظیم قیمت‌ها", callback_data="menu_prices"),
         InlineKeyboardButton("🎟️ کد تخفیف", callback_data="menu_coupons")],
        [InlineKeyboardButton("🎁 تخفیف ویژه", callback_data="menu_special")],
        [InlineKeyboardButton(ref_text, callback_data="menu_referral")],
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

        # ========== مدیریت کاربران ==========
        elif data == "menu_users":
            users = db.get("users", {})
            if not users:
                await query.edit_message_text(
                    "هنوز هیچ کاربری ثبت نشده.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="back")]])
                )
                return

            text = "👥 **لیست کاربران**\n\n"
            kb = []
            for code, u in list(users.items())[-15:]:  # آخرین ۱۵ تا
                status = "🚫" if u.get("suspended") else "✅"
                text += f"{status} `{code}` | {u.get('rubika')} | موجودی: {u.get('balance', 0):,}\n"
                kb.append([InlineKeyboardButton(
                    f"{status} {code}",
                    callback_data=f"user_{code}"
                )])
            kb.append([InlineKeyboardButton("🔙 بازگشت", callback_data="back")])
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

        elif data.startswith("user_"):
            code = data.replace("user_", "")
            user = db.get("users", {}).get(code)
            if not user:
                await query.answer("کاربر پیدا نشد", show_alert=True)
                return

            status = "تعلیق شده 🚫" if user.get("suspended") else "فعال ✅"
            text = (
                f"👤 **اطلاعات کاربر**\n\n"
                f"🔑 کد: `{code}`\n"
                f"💬 روبیکا: {user.get('rubika')}\n"
                f"💰 موجودی: {user.get('balance', 0):,} تومان\n"
                f"🎁 تعداد رفرال: {user.get('referral_count', 0)}\n"
                f"📅 تاریخ ساخت: {user.get('created_at', '-')}\n"
                f"🌐 IP: `{user.get('ip', '-')}`\n"
                f"وضعیت: {status}"
            )
            kb = [
                [InlineKeyboardButton("➕ افزایش موجودی", callback_data=f"bal_add_{code}"),
                 InlineKeyboardButton("➖ کسر موجودی", callback_data=f"bal_sub_{code}")],
                [InlineKeyboardButton("🚫 تعلیق / رفع تعلیق", callback_data=f"suspend_{code}")],
                [InlineKeyboardButton("🔙 بازگشت", callback_data="menu_users")]
            ]
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

        elif data.startswith("bal_add_"):
            code = data.replace("bal_add_", "")
            USER_STATES[ADMIN_ID] = {"state": "waiting_balance_add", "code": code}
            await query.edit_message_text(f"مبلغ افزایش موجودی برای `{code}` را به تومان بفرست:", parse_mode="Markdown")

        elif data.startswith("bal_sub_"):
            code = data.replace("bal_sub_", "")
            USER_STATES[ADMIN_ID] = {"state": "waiting_balance_sub", "code": code}
            await query.edit_message_text(f"مبلغ کسر موجودی برای `{code}` را به تومان بفرست:", parse_mode="Markdown")

        elif data.startswith("suspend_"):
            code = data.replace("suspend_", "")
            user = db.get("users", {}).get(code)
            if user:
                user["suspended"] = not user.get("suspended", False)
                save_data(db)
                status = "تعلیق شد 🚫" if user["suspended"] else "رفع تعلیق شد ✅"
                await query.answer(status, show_alert=True)
                # برگشت به صفحه کاربر
                await button_handler(update, ctx)

        # ========== رفرال ==========
        elif data == "menu_referral":
            enabled = s.get("referral_enabled", True)
            reward = s.get("referral_reward", 25000)
            text = (
                f"🎁 **تنظیمات رفرال**\n\n"
                f"وضعیت: {'🟢 روشن' if enabled else '🔴 خاموش'}\n"
                f"پاداش هر معرفی: {reward:,} تومان"
            )
            kb = [
                [InlineKeyboardButton("🔄 روشن/خاموش کردن", callback_data="ref_toggle")],
                [InlineKeyboardButton("💰 تغییر پاداش", callback_data="ref_reward")],
                [InlineKeyboardButton("📝 تغییر توضیحات", callback_data="ref_desc")],
                [InlineKeyboardButton("🔙 بازگشت", callback_data="back")]
            ]
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

        elif data == "ref_toggle":
            s["referral_enabled"] = not s.get("referral_enabled", True)
            save_data(db)
            await query.answer("وضعیت رفرال تغییر کرد", show_alert=True)
            await button_handler(update, ctx)

        elif data == "ref_reward":
            USER_STATES[ADMIN_ID] = {"state": "waiting_ref_reward"}
            await query.edit_message_text("مبلغ پاداش هر معرفی را به تومان بفرست:")

        elif data == "ref_desc":
            USER_STATES[ADMIN_ID] = {"state": "waiting_ref_desc"}
            await query.edit_message_text("توضیحات جدید رفرال را بفرست:")

        # ========== بقیه منوها (قبلی‌ها) ==========
        elif data == "menu_stats":
            orders = db.get("orders", [])
            total = len(orders)
            accepted = len([o for o in orders if o.get("status") == "accepted"])
            pending = len([o for o in orders if o.get("status") in ("pending", "pending_payment")])
            income = sum(o.get("final_price", 0) for o in orders if o.get("status") == "accepted")
            users_count = len(db.get("users", {}))

            text = (
                f"📊 **آمار کامل**\n\n"
                f"👥 تعداد کاربران: {users_count}\n"
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

        elif data == "menu_texts":
            kb = [
                [InlineKeyboardButton("خوش‌آمد ۱", callback_data="txt_welcome_text1"),
                 InlineKeyboardButton("خوش‌آمد ۲", callback_data="txt_welcome_text2")],
                [InlineKeyboardButton("درباره ما", callback_data="txt_about_text"),
                 InlineKeyboardButton("اعتماد", callback_data="txt_trust_text")],
                [InlineKeyboardButton("متن بسته بودن سایت", callback_data="txt_closed_message")],
                [InlineKeyboardButton("🔙 بازگشت", callback_data="back")]
            ]
            await query.edit_message_text("کدوم متن رو می‌خوای عوض کنی؟", reply_markup=InlineKeyboardMarkup(kb))

        elif data.startswith("txt_"):
            key = data.replace("txt_", "")
            USER_STATES[ADMIN_ID] = {"state": f"waiting_text_{key}"}
            if key == "closed_message":
                current = s.get("closed_message", "ندارد")
            else:
                current = db.get("texts", {}).get(key, "ندارد")
            await query.edit_message_text(
                f"متن فعلی:\n{current}\n\nمتن جدید رو بفرست:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 لغو", callback_data="back")]])
            )

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
                await query.answer("❌ خطا", show_alert=True)
            await button_handler(update, ctx)

        elif data == "add_pkg":
            USER_STATES[ADMIN_ID] = {"state": "waiting_pkg_cp"}
            await query.edit_message_text("تعداد CP رو بفرست:")

        elif data.startswith("edit_pkg_"):
            idx = int(data.split("_")[2])
            USER_STATES[ADMIN_ID] = {"state": "waiting_pkg_price", "idx": idx}
            await query.edit_message_text("قیمت جدید رو بفرست:")

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
            await query.edit_message_text(f"🎁 کد ویژه: `{code}`\n⏰ پایان: {end}", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

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
            s["special_discount_text"] = ""
            save_data(db)
            await query.answer("✅ حذف شد", show_alert=True)
            await button_handler(update, ctx)

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
                    if m > 12: dt = dt.replace(year=dt.year + 1, month=1)
                    elif m < 1: dt = dt.replace(year=dt.year - 1, month=12)
                    else: dt = dt.replace(month=m)
                elif field == "d": dt += timedelta(days=1 if action == "up" else -1)
                elif field == "h": dt += timedelta(hours=1 if action == "up" else -1)
                elif field == "min": dt += timedelta(minutes=1 if action == "up" else -1)
                USER_STATES[ADMIN_ID].update({"y": dt.year, "m": dt.month, "d": dt.day, "h": dt.hour, "min": dt.minute})
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
                await query.edit_message_text("✅ تاریخ تنظیم شد.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="menu_special")]]))
            except:
                await query.answer("❌ خطا", show_alert=True)

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
            await button_handler(update, ctx)

        elif data == "add_coup":
            USER_STATES[ADMIN_ID] = {"state": "waiting_coupon_code"}
            await query.edit_message_text("کد تخفیف رو بفرست:")

        elif data in ("coup_type_percent", "coup_type_fixed"):
            t = "percent" if data == "coup_type_percent" else "fixed"
            st = USER_STATES.get(ADMIN_ID, {})
            USER_STATES[ADMIN_ID] = {"state": f"waiting_coupon_amount_{t}", "code": st.get("code")}
            await query.edit_message_text("مقدار تخفیف رو بفرست:")

        elif data == "menu_card":
            USER_STATES[ADMIN_ID] = {"state": "waiting_card"}
            await query.edit_message_text("شماره کارت و نام صاحب کارت رو با این فرمت بفرست:\n`6219861452724577 - یوسف موسوی`", parse_mode="Markdown")

        elif data == "menu_orders":
            kb = []
            for o in db.get("orders", [])[-8:][::-1]:
                status = o.get("status", "pending")
                icon = "⏳" if status in ("pending", "pending_payment") else ("✅" if status == "accepted" else "❌")
                kb.append([InlineKeyboardButton(f"{icon} {o.get('code')} | {o.get('final_price', 0):,} ت", callback_data=f"view_{o['id']}")])
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
                f"👤 کاربر: `{order.get('user_code', '-')}`\n"
                f"📧 {order.get('email') or 'ثبت نشده'}\n"
                f"🔑 {order.get('pass') or 'ثبت نشده'}\n"
                f"💳 {order.get('sender_card') or '-'}\n"
                f"💰 مبلغ: {order.get('final_price', 0):,} تومان\n"
                f"📅 {order.get('date', '')}"
            )
            kb = [[InlineKeyboardButton("✅ تایید", callback_data=f"ok_{oid}"), InlineKeyboardButton("❌ رد", callback_data=f"no_{oid}")],
                  [InlineKeyboardButton("🔙 بازگشت", callback_data="menu_orders")]]
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

        elif data.startswith("ok_") or data.startswith("no_"):
            try:
                oid = int(data.split("_")[1])
                new_status = "accepted" if data.startswith("ok_") else "rejected"
                for o in db.get("orders", []):
                    if o.get("id") == oid:
                        o["status"] = new_status
                        break
                save_data(db)
                await query.answer("تایید شد ✅" if new_status == "accepted" else "رد شد ❌", show_alert=True)
                await button_handler(update, ctx)
            except Exception as e:
                print(f"Confirm Error: {e}")
                await query.answer("❌ خطا", show_alert=True)

        elif data == "menu_toggle_reg":
            s["registration_open"] = not s.get("registration_open", True)
            save_data(db)
            status = "باز 🟢" if s["registration_open"] else "بسته 🔴"
            await query.answer(f"سایت الان {status} شد", show_alert=True)
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
        if state == "waiting_balance_add":
            amount = int(text)
            code = st["code"]
            if code in db["users"]:
                db["users"][code]["balance"] = db["users"][code].get("balance", 0) + amount
                save_data(db)
                await update.message.reply_text(f"✅ {amount:,} تومان به موجودی `{code}` اضافه شد.")
            else:
                await update.message.reply_text("کاربر پیدا نشد.")

        elif state == "waiting_balance_sub":
            amount = int(text)
            code = st["code"]
            if code in db["users"]:
                db["users"][code]["balance"] = max(0, db["users"][code].get("balance", 0) - amount)
                save_data(db)
                await update.message.reply_text(f"✅ {amount:,} تومان از موجودی `{code}` کم شد.")
            else:
                await update.message.reply_text("کاربر پیدا نشد.")

        elif state == "waiting_ref_reward":
            s["referral_reward"] = int(text)
            save_data(db)
            await update.message.reply_text(f"✅ پاداش رفرال به {int(text):,} تومان تغییر کرد.")

        elif state == "waiting_ref_desc":
            s["referral_description"] = text
            save_data(db)
            await update.message.reply_text("✅ توضیحات رفرال تغییر کرد.")

        elif state == "waiting_price_var":
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
            if key == "closed_message":
                s["closed_message"] = text
            else:
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
            await update.message.reply_text("نوع تخفیف؟", reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("درصدی (%)", callback_data="coup_type_percent")],
                [InlineKeyboardButton("مبلغی (تومان)", callback_data="coup_type_fixed")]
            ]))
            return

        elif state == "waiting_coupon_amount_percent":
            db.setdefault("coupons", []).append({"code": st["code"], "type": "percent", "amount": int(text), "active": True})
            save_data(db)
            await update.message.reply_text("✅ کد تخفیف ساخته شد.")

        elif state == "waiting_coupon_amount_fixed":
            db.setdefault("coupons", []).append({"code": st["code"], "type": "fixed", "amount": int(text), "active": True})
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
    await update.message.reply_text("🎮 پنل مدیریت:", reply_markup=InlineKeyboardMarkup(get_main_menu(db)))


# ==========================================
# اجرای سرور و ربات
# ==========================================
def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app_web.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)


def run_bot():
    global bot_app, main_loop

    if not BOT_TOKEN:
        print("❌ BOT_TOKEN تنظیم نشده!")
        return

    bot_app = Application.builder().token(BOT_TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CallbackQueryHandler(button_handler))
    bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("🚀 Bot is polling...")
    main_loop = asyncio.get_event_loop()
    bot_app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    print("🌐 Starting Web Server...")
    threading.Thread(target=run_flask, daemon=True).start()
    time.sleep(2)
    print("🤖 Starting Bot...")
    run_bot()