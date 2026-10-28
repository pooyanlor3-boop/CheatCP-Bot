# -*- coding: utf-8 -*-
# PhoenixCheat Bot - Clean Stable Version
# Features: Login/Register, Referral, Reviews, Site Close, Admin Panel

import json
import os
import random
import string
import threading
import asyncio
import time
import copy
from datetime import datetime, timedelta

import requests
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# ==================== ENV ====================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
try:
    ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
except:
    ADMIN_ID = 0
try:
    GROUP_ID = int(os.environ.get("GROUP_ID", "0"))
except:
    GROUP_ID = 0

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app_web = Flask(__name__, static_folder=BASE_DIR)
CORS(app_web)

bot_app = None
main_loop = None
USER_STATES = {}
DATA_LOCK = threading.Lock()

# ==================== DEFAULT DATA ====================
DEFAULT_DATA = {
    "orders": [],
    "next_order_id": 1,
    "users": {},
    "reviews": [],
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
        "referral_enabled": True,
        "referral_reward": 25000,
        "referral_title": "سیستم معرفی دوستان",
        "referral_description": "با معرفی دوستات موجودی رایگان بگیر و باهاش سی‌پی بخر!",
        "closed_message": "🔒 سایت در حال بروزرسانی است.\n\nلطفاً برای اطلاع از زمان بازگشایی در کانال عضو شوید:",
        "closed_channel": "https://rubika.ir/PhoenixCheat",
        "closed_channel_text": "عضویت در کانال فونیکس چیت",
        "timed_coupon_code": "",
        "timed_coupon_percent": 0,
        "timed_coupon_expire": 0,
        "max_reviews_per_day": 3
    },
    "coupons": [],
    "texts": {
        "site_name": "فونیکس چیت",
        "welcome_title": "به خانواده فونیکس چیت خوش اومدی",
        "welcome_text1": "اینجا فقط یه فروشگاه ساده نیست. ما یه تیم واقعی از گیمرهای عاشق کالاف دیوتی هستیم که با خون دل و تجربه چندساله، بهترین و امن‌ترین سرویس سی‌پی رو برات آماده کردیم.",
        "welcome_text2": "با فونیکس چیت دیگه نگران بن نباش. آماده‌ای قدرتت رو چند برابر کنی؟",
        "about_text": "ما یک تیم واقعی و حرفه‌ای از گیمرهای کالاف دیوتی هستیم.",
        "trust_text": "✓ بیش از ۵۰۰ مشتری راضی\n✓ کانال اعتماد فعال\n✓ پشتیبانی ۲۴/۷"
    }
}

# ==================== DATA SAFE LOAD/SAVE ====================
def load_data():
    bin_id = os.environ.get("JSONBIN_ID")
    api_key = os.environ.get("JSONBIN_KEY")

    if not bin_id or not api_key:
        print("⚠️ JSONBIN_ID یا JSONBIN_KEY تنظیم نشده")
        return copy.deepcopy(DEFAULT_DATA)

    try:
        res = requests.get(
            f"https://api.jsonbin.io/v3/b/{bin_id}/latest",
            headers={"X-Master-Key": api_key},
            timeout=15
        )
        if res.status_code == 200:
            data = res.json().get("record", {})
            if isinstance(data, dict) and "orders" in data and "users" in data:
                # اطمینان از وجود فیلدهای جدید
                if "reviews" not in data:
                    data["reviews"] = []
                if "settings" not in data:
                    data["settings"] = copy.deepcopy(DEFAULT_DATA["settings"])
                else:
                    # اضافه کردن تنظیمات جدید اگر نبود
                    for k, v in DEFAULT_DATA["settings"].items():
                        if k not in data["settings"]:
                            data["settings"][k] = v
                if "texts" not in data:
                    data["texts"] = copy.deepcopy(DEFAULT_DATA["texts"])
                if "coupons" not in data:
                    data["coupons"] = []
                return data
            else:
                print("⚠️ ساختار داده JSONBin نامعتبر است")
                return copy.deepcopy(DEFAULT_DATA)
        else:
            print(f"⚠️ خطا در خواندن JSONBin: {res.status_code}")
            return copy.deepcopy(DEFAULT_DATA)
    except Exception as e:
        print(f"⚠️ خطای اتصال به JSONBin: {e}")
        return copy.deepcopy(DEFAULT_DATA)


def save_data(data):
    bin_id = os.environ.get("JSONBIN_ID")
    api_key = os.environ.get("JSONBIN_KEY")

    if not bin_id or not api_key:
        print("⚠️ نمی‌توان ذخیره کرد - کلیدها تنظیم نشده")
        return False

    if not isinstance(data, dict) or "orders" not in data or "users" not in data:
        print("⚠️ تلاش برای ذخیره داده نامعتبر - لغو شد")
        return False

    try:
        res = requests.put(
            f"https://api.jsonbin.io/v3/b/{bin_id}",
            json=data,
            headers={
                "Content-Type": "application/json",
                "X-Master-Key": api_key
            },
            timeout=15
        )
        if res.status_code == 200:
            return True
        else:
            print(f"⚠️ خطا در ذخیره JSONBin: {res.status_code}")
            return False
    except Exception as e:
        print(f"⚠️ خطای ذخیره در JSONBin: {e}")
        return False


def make_code(length=6):
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=length))


def make_order_code():
    return f"ORD-{''.join(random.choices(string.ascii_uppercase + string.digits, k=6))}"


def get_client_ip():
    if request.headers.get("X-Forwarded-For"):
        return request.headers.get("X-Forwarded-For").split(",")[0].strip()
    return request.remote_addr or "unknown"


def send_telegram_safe(coro):
    global main_loop, bot_app
    if not bot_app or not main_loop or main_loop.is_closed():
        return False
    try:
        future = asyncio.run_coroutine_threadsafe(coro, main_loop)
        future.result(timeout=15)
        return True
    except Exception as e:
        print(f"send_telegram_safe error: {e}")
        return False


# ==================== FLASK ROUTES ====================
@app_web.route("/")
def index():
    return send_from_directory(BASE_DIR, "index.html")


@app_web.route("/api/settings", methods=["GET"])
def get_settings():
    try:
        db = load_data()
        return jsonify({
            "texts": db.get("texts", {}),
            "settings": db.get("settings", {})
        })
    except Exception as e:
        print(e)
        return jsonify({"error": "Error"}), 500


@app_web.route("/api/reviews", methods=["GET"])
def get_reviews():
    try:
        db = load_data()
        approved = [r for r in db.get("reviews", []) if r.get("status") == "approved"]
        return jsonify(approved[::-1])
    except:
        return jsonify([])


@app_web.route("/api/submit_review", methods=["POST"])
def submit_review():
    try:
        data = request.get_json(silent=True) or {}
        name = str(data.get("name", "")).strip()
        text = str(data.get("text", "")).strip()
        stars = int(data.get("stars", 5) or 5)
        user_code = str(data.get("user_code", "")).strip().upper()

        if not name or not text:
            return jsonify({"success": False, "message": "نام و متن الزامی است"}), 400
        if stars < 1 or stars > 5:
            stars = 5

        with DATA_LOCK:
            db = load_data()
            max_per_day = db.get("settings", {}).get("max_reviews_per_day", 3)

            # محدودیت روزانه
            today = datetime.now().strftime("%Y-%m-%d")
            if user_code:
                user_reviews_today = [
                    r for r in db.get("reviews", [])
                    if r.get("user_code") == user_code and r.get("date", "").startswith(today)
                ]
                if len(user_reviews_today) >= max_per_day:
                    return jsonify({"success": False, "message": f"حداکثر {max_per_day} نظر در روز مجاز است"}), 400

            rev_id = make_code(6)
            review = {
                "id": rev_id,
                "name": name,
                "text": text,
                "stars": stars,
                "user_code": user_code,
                "status": "pending",
                "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "replies": []
            }
            db.setdefault("reviews", []).append(review)
            save_data(db)

        text_msg = (
            f"💬 **نظر جدید**\n\n"
            f"👤 {name}\n"
            f"⭐ {stars}/5\n"
            f"📝 {text}\n\n"
            f"آیدی سایت: `{user_code or 'مهمان'}`"
        )
        kb = [[
            InlineKeyboardButton("✅ تایید", callback_data=f"rev_ok_{rev_id}"),
            InlineKeyboardButton("❌ رد", callback_data=f"rev_no_{rev_id}")
        ]]

        async def _send():
            await bot_app.bot.send_message(
                chat_id=GROUP_ID,
                text=text_msg,
                reply_markup=InlineKeyboardMarkup(kb),
                parse_mode="Markdown"
            )
        send_telegram_safe(_send())
        return jsonify({"success": True})
    except Exception as e:
        print(e)
        return jsonify({"success": False}), 500


@app_web.route("/api/register", methods=["POST"])
def register():
    try:
        data = request.get_json(silent=True) or {}
        name = str(data.get("name", "")).strip()
        rubika = str(data.get("rubika", "")).strip()
        code = str(data.get("code", "")).strip().upper()
        password = str(data.get("password", "")).strip()
        fingerprint = str(data.get("fingerprint", "")).strip()
        ref_code = str(data.get("ref", "")).strip().upper() or None

        # اعتبارسنجی
        if not name or len(name) > 15:
            return jsonify({"success": False, "message": "نام باید بین ۱ تا ۱۵ کاراکتر باشد"}), 400
        if not rubika.startswith("@") or len(rubika) < 6 or not all(c.isalnum() or c == "_" for c in rubika[1:]):
            return jsonify({"success": False, "message": "آیدی روبیکا نامعتبر است"}), 400
        if len(code) < 5 or len(code) > 15 or not all(c.isalnum() or c == "_" for c in code):
            return jsonify({"success": False, "message": "آیدی سایت نامعتبر است (۵ تا ۱۵ کاراکتر، حروف، عدد و _)"}), 400
        if len(password) < 6 or len(password) > 20:
            return jsonify({"success": False, "message": "رمز باید ۶ تا ۲۰ کاراکتر باشد"}), 400
        if not any(c.isalpha() for c in password) or not any(c.isdigit() for c in password):
            return jsonify({"success": False, "message": "رمز باید شامل حروف و عدد باشد"}), 400

        with DATA_LOCK:
            db = load_data()
            users = db.get("users", {})

            if code in users:
                return jsonify({"success": False, "message": "این آیدی سایت قبلاً انتخاب شده"}), 400

            if not db["settings"].get("referral_enabled", True):
                ref_code = None

            user = {
                "code": code,
                "name": name,
                "rubika": rubika,
                "password": password,
                "balance": 0,
                "referral_count": 0,
                "referred_by": None,
                "ip": get_client_ip(),
                "fingerprint": fingerprint,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "suspended": False,
                "avatar": ""
            }

            # رفرال
            if ref_code and ref_code in users and ref_code != code:
                # جلوگیری از رفرال فیک ساده (همون IP)
                referrer = users[ref_code]
                if referrer.get("ip") != user["ip"] and referrer.get("fingerprint") != fingerprint:
                    users[ref_code]["balance"] = users[ref_code].get("balance", 0) + db["settings"].get("referral_reward", 25000)
                    users[ref_code]["referral_count"] = users[ref_code].get("referral_count", 0) + 1
                    user["referred_by"] = ref_code

            users[code] = user
            db["users"] = users
            save_data(db)

        text = (
            f"🆕 **اکانت جدید**\n\n"
            f"👤 نام: {name}\n"
            f"🆔 آیدی سایت: `{code}`\n"
            f"📱 روبیکا: {rubika}\n"
            f"🌐 IP: `{user['ip']}`"
        )
        if user.get("referred_by"):
            text += f"\n🎁 رفرال از: `{user['referred_by']}`"

        async def _send():
            await bot_app.bot.send_message(chat_id=GROUP_ID, text=text, parse_mode="Markdown")
        send_telegram_safe(_send())

        return jsonify({"success": True, "code": code, "balance": 0, "name": name})
    except Exception as e:
        print(e)
        return jsonify({"success": False, "message": "خطای سرور"}), 500


@app_web.route("/api/login", methods=["POST"])
def login():
    try:
        data = request.get_json(silent=True) or {}
        code = str(data.get("code", "")).strip().upper()
        password = str(data.get("password", "")).strip()
        fingerprint = str(data.get("fingerprint", "")).strip()

        if not code:
            return jsonify({"success": False, "message": "آیدی را وارد کنید"}), 400

        with DATA_LOCK:
            db = load_data()
            user = db.get("users", {}).get(code)

            if not user:
                return jsonify({"success": False, "message": "آیدی یافت نشد"}), 404
            if user.get("suspended"):
                return jsonify({"success": False, "message": "اکانت تعلیق شده"}), 403

            # اگر پسورد ارسال شده چک کن
            if password:
                if user.get("password") and user.get("password") != password:
                    return jsonify({"success": False, "message": "رمز عبور اشتباه است"}), 403
            # اگر پسورد نداشت (اکانت قدیمی) اجازه بده

            # آپدیت fingerprint
            if fingerprint:
                user["fingerprint"] = fingerprint
                db["users"][code] = user
                save_data(db)

        return jsonify({
            "success": True,
            "code": code,
            "name": user.get("name", code),
            "balance": user.get("balance", 0),
            "referral_count": user.get("referral_count", 0),
            "avatar": user.get("avatar", "")
        })
    except Exception as e:
        print(e)
        return jsonify({"success": False}), 500


@app_web.route("/api/generate_code", methods=["GET"])
def generate_code():
    db = load_data()
    for _ in range(30):
        code = make_code(8)
        if code not in db.get("users", {}):
            return jsonify({"success": True, "code": code})
    return jsonify({"success": False}), 500


@app_web.route("/api/track", methods=["POST"])
def track_order():
    try:
        code = str((request.get_json(silent=True) or {}).get("code", "")).strip().upper()
        db = load_data()
        for o in db.get("orders", []):
            if o.get("code") == code:
                status = o.get("status", "pending")
                step = 1 if status in ("pending", "pending_payment") else (2 if status == "accepted" else 3)
                status_fa = "⏳ در انتظار" if step == 1 else ("✅ تایید شده" if step == 2 else "❌ رد شده")
                return jsonify({
                    "success": True,
                    "status": status_fa,
                    "step": step,
                    "cp": f"{o.get('cp', 0):,}",
                    "price": f"{o.get('final_price', 0):,}",
                    "date": o.get("date", "")
                })
        return jsonify({"success": False, "message": "یافت نشد"}), 404
    except:
        return jsonify({"success": False}), 500


@app_web.route("/api/check_coupon", methods=["POST"])
def check_coupon():
    try:
        code = str((request.get_json(silent=True) or {}).get("code", "")).strip().upper()
        db = load_data()
        s = db.get("settings", {})

        if s.get("timed_coupon_code") and s.get("timed_coupon_code") == code:
            if time.time() < s.get("timed_coupon_expire", 0):
                return jsonify({"success": True, "type": "percent", "amount": s.get("timed_coupon_percent", 0)})
            return jsonify({"success": False, "message": "کد منقضی شده"}), 400

        for c in db.get("coupons", []):
            if c.get("code") == code and c.get("active", True):
                return jsonify({"success": True, "type": c.get("type", "fixed"), "amount": c.get("amount", 0)})
        return jsonify({"success": False, "message": "کد نامعتبر"}), 400
    except:
        return jsonify({"success": False}), 500


@app_web.route("/api/payment_info", methods=["POST"])
def payment_info():
    try:
        with DATA_LOCK:
            db = load_data()
            data = request.form
            user_code = str(data.get("user_code", "")).strip().upper()
            oid = db.get("next_order_id", 1)
            user = db.get("users", {}).get(user_code) if user_code else None

            receipt = request.files.get("receipt")
            receipt_path = None
            if receipt and receipt.filename:
                ext = os.path.splitext(receipt.filename)[1].lower()
                if ext in [".jpg", ".jpeg", ".png", ".webp"]:
                    receipt_path = os.path.join(BASE_DIR, f"temp_{oid}_{int(time.time())}{ext}")
                    receipt.save(receipt_path)

            balance_used = int(data.get("balance_used", 0) or 0)
            if user and balance_used > 0:
                user["balance"] = max(0, user.get("balance", 0) - min(balance_used, user.get("balance", 0)))

            order = {
                "id": oid,
                "code": make_order_code(),
                "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "cp": int(data.get("cp", 0)),
                "antiban": str(data.get("antiban", "")).lower() == "true",
                "speed": data.get("speed"),
                "base_price": int(data.get("totalPrice", 0)),
                "discount_amount": int(data.get("discountAmount", 0)),
                "balance_used": balance_used,
                "final_price": int(data.get("finalPrice", 0)),
                "sender_card": data.get("senderCard"),
                "sent_amount": data.get("sentAmount"),
                "sent_time": data.get("sentTime"),
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
        print(e)
        return jsonify({"success": False}), 500


@app_web.route("/api/final_order", methods=["POST"])
def final_order():
    try:
        with DATA_LOCK:
            db = load_data()
            data = request.get_json(silent=True) or {}
            code = str(data.get("order_code", "")).strip()
            for o in db.get("orders", []):
                if o.get("code") == code:
                    o["email"] = data.get("email", "")
                    o["pass"] = data.get("pass", "")
                    o["rubika"] = data.get("rubika", "")
                    o["desc"] = data.get("desc", "")
                    o["status"] = "pending"
                    save_data(db)
                    send_account_msg(code)
                    return jsonify({"success": True})
            return jsonify({"success": False}), 404
    except Exception as e:
        print(e)
        return jsonify({"success": False}), 500


# ==================== TELEGRAM MESSAGES ====================
def send_payment_msg(order, receipt_path=None):
    text = (
        f"💳 **پرداخت جدید**\n"
        f"🔢 `{order['code']}`\n"
        f"👤 `{order.get('user_code')}`\n\n"
        f"💎 {order.get('cp'):,} CP\n"
        f"💰 {order.get('final_price'):,} تومان"
    )
    async def _send():
        if receipt_path and os.path.exists(receipt_path):
            with open(receipt_path, "rb") as photo:
                await bot_app.bot.send_photo(
                    chat_id=GROUP_ID, photo=photo, caption=text, parse_mode="Markdown"
                )
        else:
            await bot_app.bot.send_message(chat_id=GROUP_ID, text=text, parse_mode="Markdown")
    send_telegram_safe(_send())


def send_account_msg(code):
    db = load_data()
    order = next((o for o in db.get("orders", []) if o.get("code") == code), None)
    if not order:
        return
    text = (
        f"👤 **اطلاعات اکانت**\n"
        f"🔢 `{order['code']}`\n"
        f"👤 `{order.get('user_code')}`\n\n"
        f"📧 `{order.get('email')}`\n"
        f"🔑 `{order.get('pass')}`\n"
        f"📱 {order.get('rubika')}\n"
        f"📝 {order.get('desc')}"
    )
    kb = [[
        InlineKeyboardButton("✅ تایید", callback_data=f"ok_{order['id']}"),
        InlineKeyboardButton("❌ رد", callback_data=f"no_{order['id']}")
    ]]
    async def _send():
        await bot_app.bot.send_message(
            chat_id=GROUP_ID, text=text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown"
        )
    send_telegram_safe(_send())


# ==================== ADMIN PANEL ====================
def get_main_menu(db=None):
    if db is None:
        db = load_data()
    s = db.get("settings", {})
    is_open = s.get("registration_open", True)
    ref_enabled = s.get("referral_enabled", True)
    return [
        [InlineKeyboardButton("📦 سفارشات", callback_data="menu_orders"),
         InlineKeyboardButton("📊 آمار", callback_data="menu_stats")],
        [InlineKeyboardButton("👥 مدیریت کاربران", callback_data="menu_users")],
        [InlineKeyboardButton("💬 نظرات", callback_data="menu_reviews")],
        [InlineKeyboardButton("📝 ویرایش متن‌ها", callback_data="menu_texts")],
        [InlineKeyboardButton("💰 تنظیم قیمت‌ها", callback_data="menu_prices"),
         InlineKeyboardButton("🎟️ کد تخفیف", callback_data="menu_coupons")],
        [InlineKeyboardButton("⏳ کد تایم‌دار", callback_data="menu_timed_coupon")],
        [InlineKeyboardButton("🎁 رفرال: روشن" if ref_enabled else "🎁 رفرال: خاموش", callback_data="menu_referral")],
        [InlineKeyboardButton("💳 تنظیم کارت", callback_data="menu_card")],
        [InlineKeyboardButton("🟢 سایت باز است" if is_open else "🔴 سایت بسته است", callback_data="menu_toggle_reg")],
    ]


async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    USER_STATES.pop(ADMIN_ID, None)
    await update.message.reply_text(
        "🎮 **پنل مدیریت فونیکس چیت**",
        reply_markup=InlineKeyboardMarkup(get_main_menu()),
        parse_mode="Markdown"
    )


async def button_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    db = load_data()
    s = db.get("settings", {})

    # --- Review Approve/Reject ---
    if data.startswith("rev_ok_") or data.startswith("rev_no_"):
        rev_id = data.split("_")[2]
        new_status = "approved" if data.startswith("rev_ok_") else "rejected"
        with DATA_LOCK:
            for r in db.get("reviews", []):
                if r["id"] == rev_id:
                    r["status"] = new_status
                    break
            save_data(db)
        await query.answer("✅ ثبت شد", show_alert=True)
        try:
            await query.message.delete()
        except:
            pass
        return

    await query.answer()

    try:
        if data == "back":
            USER_STATES.pop(ADMIN_ID, None)
            await query.edit_message_text(
                "🎮 **پنل مدیریت**",
                reply_markup=InlineKeyboardMarkup(get_main_menu(db)),
                parse_mode="Markdown"
            )

        # --- Reviews Menu ---
        elif data == "menu_reviews":
            reviews = db.get("reviews", [])
            pending = [r for r in reviews if r.get("status") == "pending"]
            approved = [r for r in reviews if r.get("status") == "approved"]
            text = f"💬 **نظرات**\n\nدر انتظار: {len(pending)}\nتایید شده: {len(approved)}\nکل: {len(reviews)}"
            kb = []
            for r in reviews[-10:][::-1]:
                status_icon = "⏳" if r.get("status") == "pending" else ("✅" if r.get("status") == "approved" else "❌")
                kb.append([InlineKeyboardButton(
                    f"{status_icon} {r.get('name', '')[:10]} - {r.get('stars', 5)}★",
                    callback_data=f"viewrev_{r['id']}"
                )])
            kb.append([InlineKeyboardButton("🔙 بازگشت", callback_data="back")])
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

        elif data.startswith("viewrev_"):
            rev_id = data.replace("viewrev_", "")
            rev = next((r for r in db.get("reviews", []) if r["id"] == rev_id), None)
            if not rev:
                await query.answer("یافت نشد")
                return
            text = (
                f"💬 **نظر**\n\n"
                f"👤 {rev.get('name')}\n"
                f"⭐ {rev.get('stars', 5)}/5\n"
                f"📝 {rev.get('text')}\n"
                f"📅 {rev.get('date')}\n"
                f"وضعیت: {rev.get('status')}"
            )
            kb = [
                [InlineKeyboardButton("✅ تایید", callback_data=f"rev_ok_{rev_id}"),
                 InlineKeyboardButton("❌ رد", callback_data=f"rev_no_{rev_id}")],
                [InlineKeyboardButton("🗑 حذف", callback_data=f"rev_del_{rev_id}")],
                [InlineKeyboardButton("🔙", callback_data="menu_reviews")]
            ]
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

        elif data.startswith("rev_del_"):
            rev_id = data.replace("rev_del_", "")
            with DATA_LOCK:
                db["reviews"] = [r for r in db.get("reviews", []) if r.get("id") != rev_id]
                save_data(db)
            await query.answer("حذف شد")
            await button_handler(update, ctx)

        # --- Timed Coupon ---
        elif data == "menu_timed_coupon":
            code = s.get("timed_coupon_code") or "ندارد"
            pct = s.get("timed_coupon_percent", 0)
            exp = s.get("timed_coupon_expire", 0)
            exp_str = datetime.fromtimestamp(exp).strftime("%H:%M") if exp > time.time() else "منقضی"
            text = f"⏳ **کد تایم‌دار**\n\nکد: `{code}`\nدرصد: {pct}%\nانقضا: {exp_str}"
            kb = [
                [InlineKeyboardButton("➕ ساخت / تغییر", callback_data="timed_set")],
                [InlineKeyboardButton("❌ حذف", callback_data="timed_del")],
                [InlineKeyboardButton("🔙 بازگشت", callback_data="back")]
            ]
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

        elif data == "timed_set":
            USER_STATES[ADMIN_ID] = {"state": "waiting_timed_code"}
            await query.edit_message_text("کد تخفیف جدید را بفرست:")

        elif data == "timed_del":
            s["timed_coupon_code"] = ""
            s["timed_coupon_percent"] = 0
            s["timed_coupon_expire"] = 0
            save_data(db)
            await query.answer("حذف شد")
            await button_handler(update, ctx)

        # --- Referral ---
        elif data == "menu_referral":
            enabled = s.get("referral_enabled", True)
            kb = [
                [InlineKeyboardButton("🙈 خاموش کردن" if enabled else "🎁 روشن کردن", callback_data="ref_toggle")],
                [InlineKeyboardButton("💰 تغییر پاداش", callback_data="ref_reward")],
                [InlineKeyboardButton("📝 توضیحات", callback_data="ref_desc")],
                [InlineKeyboardButton("🔢 حداکثر نظر روزانه", callback_data="set_max_reviews")],
                [InlineKeyboardButton("🔙 بازگشت", callback_data="back")]
            ]
            await query.edit_message_text(
                f"🎁 وضعیت رفرال: {'روشن ✅' if enabled else 'خاموش ❌'}\nپاداش: {s.get('referral_reward', 25000):,} تومان",
                reply_markup=InlineKeyboardMarkup(kb)
            )

        elif data == "ref_toggle":
            s["referral_enabled"] = not s.get("referral_enabled", True)
            save_data(db)
            await button_handler(update, ctx)

        elif data == "ref_reward":
            USER_STATES[ADMIN_ID] = {"state": "waiting_ref_reward"}
            await query.edit_message_text("مبلغ پاداش رفرال (تومان):")

        elif data == "ref_desc":
            USER_STATES[ADMIN_ID] = {"state": "waiting_ref_desc"}
            await query.edit_message_text("توضیحات بخش رفرال:")

        elif data == "set_max_reviews":
            USER_STATES[ADMIN_ID] = {"state": "waiting_max_reviews"}
            await query.edit_message_text("حداکثر تعداد نظر روزانه هر کاربر:")

        # --- Users ---
        elif data == "menu_users":
            users = db.get("users", {})
            if not users:
                await query.edit_message_text("کاربری نیست.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙", callback_data="back")]]))
                return
            text = "👥 **کاربران**\n\n"
            kb = []
            for code, u in list(users.items())[-20:]:
                text += f"`{code}` | {u.get('name', u.get('rubika', ''))} | {u.get('balance', 0):,}\n"
                kb.append([InlineKeyboardButton(code, callback_data=f"user_{code}")])
            kb.append([InlineKeyboardButton("🔙 بازگشت", callback_data="back")])
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

        elif data.startswith("user_"):
            code = data.replace("user_", "")
            user = db.get("users", {}).get(code)
            if not user:
                await query.answer("یافت نشد")
                return
            text = (
                f"👤 `{code}`\n"
                f"نام: {user.get('name', '-')}\n"
                f"روبیکا: {user.get('rubika', '-')}\n"
                f"💰 موجودی: {user.get('balance', 0):,}\n"
                f"🎁 رفرال: {user.get('referral_count', 0)}\n"
                f"وضعیت: {'🚫 تعلیق' if user.get('suspended') else '✅ فعال'}"
            )
            kb = [
                [InlineKeyboardButton("➕ موجودی", callback_data=f"bal_add_{code}"),
                 InlineKeyboardButton("➖ موجودی", callback_data=f"bal_sub_{code}")],
                [InlineKeyboardButton("🚫 تعلیق / رفع", callback_data=f"suspend_{code}")],
                [InlineKeyboardButton("🔙", callback_data="menu_users")]
            ]
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

        elif data.startswith("bal_add_"):
            USER_STATES[ADMIN_ID] = {"state": "waiting_balance_add", "code": data.replace("bal_add_", "")}
            await query.edit_message_text("مبلغ افزایش موجودی:")

        elif data.startswith("bal_sub_"):
            USER_STATES[ADMIN_ID] = {"state": "waiting_balance_sub", "code": data.replace("bal_sub_", "")}
            await query.edit_message_text("مبلغ کسر موجودی:")

        elif data.startswith("suspend_"):
            code = data.replace("suspend_", "")
            if code in db["users"]:
                db["users"][code]["suspended"] = not db["users"][code].get("suspended", False)
                save_data(db)
            await button_handler(update, ctx)

        # --- Stats ---
        elif data == "menu_stats":
            orders = db.get("orders", [])
            text = (
                f"📊 **آمار**\n\n"
                f"کاربران: {len(db.get('users', {}))}\n"
                f"سفارشات: {len(orders)}\n"
                f"تایید شده: {len([o for o in orders if o.get('status') == 'accepted'])}\n"
                f"درآمد: {sum(o.get('final_price', 0) for o in orders if o.get('status') == 'accepted'):,} تومان\n"
                f"نظرات: {len(db.get('reviews', []))}"
            )
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙", callback_data="back")]]), parse_mode="Markdown")

        # --- Texts ---
        elif data == "menu_texts":
            kb = [
                [InlineKeyboardButton("خوش‌آمد ۱", callback_data="txt_welcome_text1"),
                 InlineKeyboardButton("خوش‌آمد ۲", callback_data="txt_welcome_text2")],
                [InlineKeyboardButton("درباره ما", callback_data="txt_about_text")],
                [InlineKeyboardButton("پیام بستن سایت", callback_data="txt_closed_message")],
                [InlineKeyboardButton("🔙", callback_data="back")]
            ]
            await query.edit_message_text("کدام متن را ویرایش می‌کنید؟", reply_markup=InlineKeyboardMarkup(kb))

        elif data.startswith("txt_"):
            key = data.replace("txt_", "")
            USER_STATES[ADMIN_ID] = {"state": f"waiting_text_{key}"}
            await query.edit_message_text("متن جدید را بفرست:")

        # --- Prices ---
        elif data == "menu_prices":
            kb = [
                [InlineKeyboardButton("نرخ هر ۱۰۰۰", callback_data="var_price")],
                [InlineKeyboardButton("آنتی‌بن", callback_data="extras_price")],
                [InlineKeyboardButton("🔙", callback_data="back")]
            ]
            await query.edit_message_text(
                f"قیمت فعلی:\nهر ۱۰۰۰: {s.get('price_per_1000', 25000):,}\nآنتی‌بن: {s.get('price_antiban', 50000):,}\nفوری: {s.get('price_fast', 20000):,}",
                reply_markup=InlineKeyboardMarkup(kb)
            )

        elif data == "var_price":
            USER_STATES[ADMIN_ID] = {"state": "waiting_price_var"}
            await query.edit_message_text("نرخ جدید هر ۱۰۰۰ سی‌پی:")

        elif data == "extras_price":
            USER_STATES[ADMIN_ID] = {"state": "waiting_price_antiban"}
            await query.edit_message_text("قیمت آنتی‌بن:")

        # --- Card ---
        elif data == "menu_card":
            USER_STATES[ADMIN_ID] = {"state": "waiting_card"}
            await query.edit_message_text("شماره کارت - نام صاحب کارت\nمثال:\n6219... - یوسف موسوی")

        # --- Orders ---
        elif data == "menu_orders":
            kb = []
            for o in db.get("orders", [])[-10:][::-1]:
                kb.append([InlineKeyboardButton(f"{o.get('code')} | {o.get('status')}", callback_data=f"view_{o['id']}")])
            kb.append([InlineKeyboardButton("🔙", callback_data="back")])
            await query.edit_message_text("آخرین سفارشات:", reply_markup=InlineKeyboardMarkup(kb))

        elif data.startswith("view_"):
            oid = int(data.split("_")[1])
            order = next((o for o in db.get("orders", []) if o.get("id") == oid), None)
            if order:
                text = (
                    f"🔢 `{order.get('code')}`\n"
                    f"👤 {order.get('user_code')}\n"
                    f"💎 {order.get('cp'):,} CP\n"
                    f"💰 {order.get('final_price', 0):,}\n"
                    f"وضعیت: {order.get('status')}"
                )
                kb = [
                    [InlineKeyboardButton("✅ تایید", callback_data=f"ok_{order['id']}"),
                     InlineKeyboardButton("❌ رد", callback_data=f"no_{order['id']}")],
                    [InlineKeyboardButton("🔙", callback_data="menu_orders")]
                ]
                await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

        elif data.startswith("ok_") or data.startswith("no_"):
            oid = int(data.split("_")[1])
            new_status = "accepted" if data.startswith("ok_") else "rejected"
            for o in db.get("orders", []):
                if o.get("id") == oid:
                    o["status"] = new_status
                    break
            save_data(db)
            await button_handler(update, ctx)

        # --- Toggle Site ---
        elif data == "menu_toggle_reg":
            s["registration_open"] = not s.get("registration_open", True)
            save_data(db)
            await button_handler(update, ctx)

        # --- Coupons placeholder ---
        elif data == "menu_coupons":
            await query.edit_message_text(
                "مدیریت کدهای تخفیف عادی (به زودی کامل‌تر می‌شود)",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙", callback_data="back")]])
            )

    except Exception as e:
        print(f"button_handler error: {e}")


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
            code = st["code"]
            amount = int(text)
            if code in db["users"]:
                db["users"][code]["balance"] = db["users"][code].get("balance", 0) + amount
                save_data(db)
                await update.message.reply_text(f"✅ {amount:,} تومان اضافه شد.", reply_markup=InlineKeyboardMarkup(get_main_menu(db)))
            USER_STATES.pop(ADMIN_ID, None)
            return

        elif state == "waiting_balance_sub":
            code = st["code"]
            amount = int(text)
            if code in db["users"]:
                db["users"][code]["balance"] = max(0, db["users"][code].get("balance", 0) - amount)
                save_data(db)
                await update.message.reply_text(f"✅ {amount:,} تومان کسر شد.", reply_markup=InlineKeyboardMarkup(get_main_menu(db)))
            USER_STATES.pop(ADMIN_ID, None)
            return

        elif state == "waiting_ref_reward":
            s["referral_reward"] = int(text)
            save_data(db)
            USER_STATES.pop(ADMIN_ID, None)
            await update.message.reply_text("✅ ذخیره شد.", reply_markup=InlineKeyboardMarkup(get_main_menu(db)))
            return

        elif state == "waiting_ref_desc":
            s["referral_description"] = text
            save_data(db)
            USER_STATES.pop(ADMIN_ID, None)
            await update.message.reply_text("✅ ذخیره شد.", reply_markup=InlineKeyboardMarkup(get_main_menu(db)))
            return

        elif state == "waiting_max_reviews":
            s["max_reviews_per_day"] = int(text)
            save_data(db)
            USER_STATES.pop(ADMIN_ID, None)
            await update.message.reply_text("✅ ذخیره شد.", reply_markup=InlineKeyboardMarkup(get_main_menu(db)))
            return

        elif state == "waiting_price_var":
            s["price_per_1000"] = int(text)
            save_data(db)
            USER_STATES.pop(ADMIN_ID, None)
            await update.message.reply_text("✅ ذخیره شد.", reply_markup=InlineKeyboardMarkup(get_main_menu(db)))
            return

        elif state == "waiting_price_antiban":
            s["price_antiban"] = int(text)
            USER_STATES[ADMIN_ID] = {"state": "waiting_price_fast"}
            await update.message.reply_text("حالا قیمت تحویل فوری را بفرست:")
            return

        elif state == "waiting_price_fast":
            s["price_fast"] = int(text)
            save_data(db)
            USER_STATES.pop(ADMIN_ID, None)
            await update.message.reply_text("✅ ذخیره شد.", reply_markup=InlineKeyboardMarkup(get_main_menu(db)))
            return

        elif state == "waiting_card":
            parts = text.split("-")
            s["card_number"] = parts[0].strip()
            s["card_holder"] = parts[1].strip() if len(parts) > 1 else ""
            save_data(db)
            USER_STATES.pop(ADMIN_ID, None)
            await update.message.reply_text("✅ ذخیره شد.", reply_markup=InlineKeyboardMarkup(get_main_menu(db)))
            return

        elif state.startswith("waiting_text_"):
            key = state.replace("waiting_text_", "")
            if key == "closed_message":
                s["closed_message"] = text
            else:
                db.setdefault("texts", {})[key] = text
            save_data(db)
            USER_STATES.pop(ADMIN_ID, None)
            await update.message.reply_text("✅ ذخیره شد.", reply_markup=InlineKeyboardMarkup(get_main_menu(db)))
            return

        # Timed coupon flow
        elif state == "waiting_timed_code":
            st["code"] = text.upper()
            st["state"] = "waiting_timed_percent"
            await update.message.reply_text("چند درصد تخفیف؟ (فقط عدد):")
            return

        elif state == "waiting_timed_percent":
            st["percent"] = int(text)
            st["state"] = "waiting_timed_time"
            await update.message.reply_text("چند دقیقه اعتبار داشته باشد؟ (فقط عدد):")
            return

        elif state == "waiting_timed_time":
            mins = int(text)
            s["timed_coupon_code"] = st["code"]
            s["timed_coupon_percent"] = st["percent"]
            s["timed_coupon_expire"] = time.time() + (mins * 60)
            save_data(db)
            USER_STATES.pop(ADMIN_ID, None)
            await update.message.reply_text(
                f"✅ کد `{st['code']}` برای {mins} دقیقه فعال شد.",
                reply_markup=InlineKeyboardMarkup(get_main_menu(db)),
                parse_mode="Markdown"
            )
            return

    except ValueError:
        await update.message.reply_text("❌ عدد معتبر وارد کنید.")
    except Exception as e:
        print(f"handle_text error: {e}")
        await update.message.reply_text("❌ خطا رخ داد.")


# ==================== RUN ====================
def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app_web.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)


def run_bot():
    global bot_app, main_loop
    if not BOT_TOKEN:
        print("BOT_TOKEN not set")
        return

    async def _main():
        global bot_app, main_loop
        main_loop = asyncio.get_running_loop()
        bot_app = Application.builder().token(BOT_TOKEN).build()
        bot_app.add_handler(CommandHandler("start", start))
        bot_app.add_handler(CallbackQueryHandler(button_handler))
        bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
        await bot_app.initialize()
        await bot_app.start()
        await bot_app.updater.start_polling(drop_pending_updates=True)
        print("Bot started successfully")
        await asyncio.Event().wait()

    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    time.sleep(2)
    run_bot()