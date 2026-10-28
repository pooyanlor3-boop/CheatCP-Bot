# -*- coding: utf-8 -*-
# PhoenixCheat Bot - Ultimate Version (Reviews + Timed Coupons + Google Auth)

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

BOT_TOKEN = os.environ.get("BOT_TOKEN")
try: ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
except: ADMIN_ID = 0
try: GROUP_ID = int(os.environ.get("GROUP_ID", "0"))
except: GROUP_ID = 0

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app_web = Flask(__name__, static_folder=BASE_DIR)
CORS(app_web)

bot_app = None
main_loop = None
USER_STATES = {}
DATA_LOCK = threading.Lock()

DEFAULT_DATA = {
    "orders": [], "next_order_id": 1, "users": {}, "reviews": [],
    "settings": {
        "card_number": "6219861452724577", "card_holder": "یوسف موسوی",
        "price_per_1000": 25000, "price_antiban": 50000, "price_fast": 20000,
        "registration_open": True, "special_discount_text": "", "special_coupon_code": "",
        "special_coupon_end_time": "", "custom_packages": [{"cp": 10000, "price": 250000}, {"cp": 20000, "price": 470000}],
        "referral_enabled": True, "referral_reward": 25000,
        "referral_title": "سیستم معرفی دوستان (رایگان)", "referral_description": "با معرفی دوستات موجودی رایگان بگیر و باهاش سی‌پی بخر!",
        "closed_message": "🔒 سایت در حال بروزرسانی است.\n\nلطفاً برای اطلاع از زمان بازگشایی در کانال عضو شوید:",
        "closed_channel": "https://rubika.ir/PhoenixCheat", "closed_channel_text": "عضویت در کانال فونیکس چیت",
        
        # --- Timed Coupon ---
        "timed_coupon_code": "",
        "timed_coupon_percent": 0,
        "timed_coupon_expire": 0
    },
    "coupons": [],
    "texts": {
        "site_name": "فونیکس چیت", "welcome_title": "به فروشگاه فونیکس چیت خوش آمدید",
        "welcome_text1": "ما مفتخریم که به عنوان یکی از پیشگامان و معتبرترین مراجع تخصصی در حوزه خدمات گیمینگ (به‌ویژه Call of Duty) در خدمت شما هستیم.",
        "welcome_text2": "تیم متخصص ما با تکیه بر دانش فنی و تجربه چندین ساله، بستری امن، سریع و تضمینی را برای ارتقاء تجربه بازی شما فراهم کرده است.",
        "about_text": "ما یه تیم حرفه‌ای از گیمرهای کالاف دیوتی هستیم.",
        "trust_text": "✓ بیش از ۵۰۰ مشتری راضی\n✓ چنل اعتماد فعال\n✓ پشتیبانی ۲۴/۷",
    }
}

def load_data():
    bin_id, api_key = os.environ.get("JSONBIN_ID"), os.environ.get("JSONBIN_KEY")
    if not bin_id or not api_key: return copy.deepcopy(DEFAULT_DATA)
    try:
        res = requests.get(f"https://api.jsonbin.io/v3/b/{bin_id}/latest", headers={"X-Master-Key": api_key}, timeout=12)
        if res.status_code == 200:
            data = res.json().get("record", {})
            if not isinstance(data, dict) or "orders" not in data: return copy.deepcopy(DEFAULT_DATA)
            if "reviews" not in data: data["reviews"] = []
            return data
        return copy.deepcopy(DEFAULT_DATA)
    except: return copy.deepcopy(DEFAULT_DATA)

def save_data(data):
    bin_id, api_key = os.environ.get("JSONBIN_ID"), os.environ.get("JSONBIN_KEY")
    if not bin_id or not api_key: return False
    try:
        res = requests.put(f"https://api.jsonbin.io/v3/b/{bin_id}", json=data, headers={"Content-Type": "application/json", "X-Master-Key": api_key}, timeout=12)
        return res.status_code == 200
    except: return False

def make_code(length=6): return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))
def make_order_code(): return f"ORD-{''.join(random.choices(string.ascii_uppercase + string.digits, k=6))}"

def get_client_ip():
    if request.headers.get("X-Forwarded-For"): return request.headers.get("X-Forwarded-For").split(",")[0].strip()
    return request.remote_addr or "unknown"

def send_telegram_safe(coro):
    global main_loop, bot_app
    if not bot_app or not main_loop or main_loop.is_closed(): return False
    try:
        future = asyncio.run_coroutine_threadsafe(coro, main_loop)
        future.result(timeout=15)
        return True
    except: return False

# ==================== API ها ====================
@app_web.route("/")
def index(): return send_from_directory(BASE_DIR, "index.html")

@app_web.route("/api/settings", methods=["GET"])
def get_settings():
    try:
        db = load_data()
        return jsonify({"texts": db.get("texts", {}), "settings": db.get("settings", {})})
    except: return jsonify({"error": "Error"}), 500

@app_web.route("/api/reviews", methods=["GET"])
def get_reviews():
    try:
        db = load_data()
        approved = [r for r in db.get("reviews", []) if r.get("status") == "approved"]
        return jsonify(approved[::-1]) # Newest first
    except: return jsonify([])

@app_web.route("/api/submit_review", methods=["POST"])
def submit_review():
    try:
        data = request.get_json(silent=True) or {}
        name, text = str(data.get("name", "")).strip(), str(data.get("text", "")).strip()
        if not name or not text: return jsonify({"success": False, "message": "نام و متن الزامی است"}), 400

        with DATA_LOCK:
            db = load_data()
            rev_id = make_code(6)
            review = {"id": rev_id, "name": name, "text": text, "status": "pending", "date": datetime.now().strftime("%Y-%m-%d")}
            db.setdefault("reviews", []).append(review)
            save_data(db)

        text_msg = f"💬 **نظر جدید**\n\n👤 {name}\n📝 {text}\n\nآیا تایید می‌کنید؟"
        kb = [[InlineKeyboardButton("✅ تایید", callback_data=f"rev_ok_{rev_id}"), InlineKeyboardButton("❌ رد", callback_data=f"rev_no_{rev_id}")]]
        async def _send(): await bot_app.bot.send_message(chat_id=GROUP_ID, text=text_msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
        send_telegram_safe(_send())
        return jsonify({"success": True})
    except: return jsonify({"success": False}), 500

@app_web.route("/api/register", methods=["POST"])
def register():
    try:
        data = request.get_json(silent=True) or {}
        rubika = str(data.get("rubika", "")).strip() # Here rubika is the username
        code = str(data.get("code", "")).strip().upper() # Here code is the ID
        fingerprint = str(data.get("fingerprint", "")).strip()
        ref_code = str(data.get("ref", "")).strip().upper() or None

        if len(code) < 5 or not all(c.isalnum() or c in ['_', '.'] for c in code):
            return jsonify({"success": False, "message": "آیدی نامعتبر است (حداقل ۵ کاراکتر، حروف، عدد، _ و .)"}), 400

        with DATA_LOCK:
            db = load_data()
            users = db.get("users", {})
            if code in users: return jsonify({"success": False, "message": "این آیدی قبلا انتخاب شده"}), 400
            if not db["settings"].get("referral_enabled", True): ref_code = None
            
            user = {"code": code, "rubika": rubika, "balance": 0, "referral_count": 0, "referred_by": None, "ip": get_client_ip(), "fingerprint": fingerprint, "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"), "suspended": False}
            if ref_code and ref_code in users and ref_code != code:
                users[ref_code]["balance"] += db["settings"].get("referral_reward", 25000)
                users[ref_code]["referral_count"] += 1
                user["referred_by"] = ref_code
            users[code] = user
            db["users"] = users
            save_data(db)

        text = f"🆕 **اکانت جدید**\n\n👤 نام: {rubika}\n🆔 آیدی: `{code}`\n🌐 IP: `{user['ip']}`"
        async def _send(): await bot_app.bot.send_message(chat_id=GROUP_ID, text=text, parse_mode="Markdown")
        send_telegram_safe(_send())
        return jsonify({"success": True, "code": code, "balance": 0})
    except: return jsonify({"success": False}), 500

@app_web.route("/api/login", methods=["POST"])
def login():
    try:
        code = str((request.get_json(silent=True) or {}).get("code", "")).strip().upper()
        with DATA_LOCK:
            db = load_data()
            user = db.get("users", {}).get(code)
            if not user: return jsonify({"success": False, "message": "آیدی یافت نشد"}), 404
            if user.get("suspended"): return jsonify({"success": False, "message": "اکانت تعلیق شده"}), 403
            save_data(db)
        return jsonify({"success": True, "code": code, "rubika": user.get("rubika"), "balance": user.get("balance", 0), "referral_count": user.get("referral_count", 0)})
    except: return jsonify({"success": False}), 500

@app_web.route("/api/generate_code", methods=["GET"])
def generate_code():
    db = load_data()
    for _ in range(20):
        code = make_code(8)
        if code not in db.get("users", {}): return jsonify({"success": True, "code": code})
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
                return jsonify({"success": True, "status": status_fa, "step": step, "cp": f"{o.get('cp', 0):,}", "price": f"{o.get('final_price', 0):,}", "date": o.get("date", "")})
        return jsonify({"success": False, "message": "یافت نشد"}), 404
    except: return jsonify({"success": False}), 500

@app_web.route("/api/check_coupon", methods=["POST"])
def check_coupon():
    try:
        code = str((request.get_json(silent=True) or {}).get("code", "")).strip().upper()
        db = load_data()
        s = db.get("settings", {})
        
        # چک کردن کد تایم دار
        if s.get("timed_coupon_code") and s.get("timed_coupon_code") == code:
            if time.time() < s.get("timed_coupon_expire", 0):
                return jsonify({"success": True, "type": "percent", "amount": s.get("timed_coupon_percent", 0)})
            else:
                return jsonify({"success": False, "message": "کد منقضی شده"}), 400

        # چک کردن کدهای عادی
        for c in db.get("coupons", []):
            if c.get("code") == code and c.get("active", True): return jsonify({"success": True, "type": c.get("type", "fixed"), "amount": c.get("amount", 0)})
        return jsonify({"success": False, "message": "کد نامعتبر"}), 400
    except: return jsonify({"success": False}), 500

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
                if ext in ['.jpg', '.jpeg', '.png', '.webp']:
                    receipt_path = os.path.join(BASE_DIR, f"temp_{oid}_{int(time.time())}{ext}")
                    receipt.save(receipt_path)

            balance_used = int(data.get("balance_used", 0) or 0)
            if user and balance_used > 0:
                user["balance"] -= min(balance_used, user.get("balance", 0))

            order = {"id": oid, "code": make_order_code(), "date": datetime.now().strftime("%Y-%m-%d %H:%M"), "cp": int(data.get("cp", 0)), "antiban": str(data.get("antiban", "")).lower() == "true", "speed": data.get("speed"), "base_price": int(data.get("totalPrice", 0)), "discount_amount": int(data.get("discountAmount", 0)), "balance_used": balance_used, "final_price": int(data.get("finalPrice", 0)), "sender_card": data.get("senderCard"), "sent_amount": data.get("sentAmount"), "sent_time": data.get("sentTime"), "user_code": user_code, "email": "", "pass": "", "rubika": "", "desc": "", "status": "pending_payment"}
            db["orders"].append(order); db["next_order_id"] = oid + 1
            if user: db["users"][user_code] = user
            save_data(db)

        send_payment_msg(order, receipt_path)
        if receipt_path and os.path.exists(receipt_path):
            try: os.remove(receipt_path)
            except: pass
        return jsonify({"success": True, "order_code": order["code"]})
    except: return jsonify({"success": False}), 500

@app_web.route("/api/final_order", methods=["POST"])
def final_order():
    try:
        with DATA_LOCK:
            db = load_data()
            data = request.get_json(silent=True) or {}
            code = str(data.get("order_code", "")).strip()
            for o in db.get("orders", []):
                if o.get("code") == code:
                    o["email"], o["pass"], o["rubika"], o["desc"] = data.get("email", ""), data.get("pass", ""), data.get("rubika", ""), data.get("desc", "")
                    o["status"] = "pending"
                    save_data(db); send_account_msg(code); return jsonify({"success": True})
            return jsonify({"success": False}), 404
    except: return jsonify({"success": False}), 500

# ==================== Telegram Messages ====================
def send_payment_msg(order, receipt_path=None):
    text = f"💳 **پرداخت**\n🔢 `{order['code']}`\n👤 `{order.get('user_code')}`\n\n💎 {order.get('cp'):,} CP\n💰 {order.get('final_price'):,} ت"
    async def _send():
        if receipt_path and os.path.exists(receipt_path):
            with open(receipt_path, "rb") as photo: await bot_app.bot.send_photo(chat_id=GROUP_ID, photo=photo, caption=text, parse_mode="Markdown")
        else: await bot_app.bot.send_message(chat_id=GROUP_ID, text=text, parse_mode="Markdown")
    send_telegram_safe(_send())

def send_account_msg(code):
    db = load_data()
    order = next((o for o in db.get("orders", []) if o.get("code") == code), None)
    if not order: return
    text = f"👤 **اطلاعات اکانت**\n🔢 `{order['code']}`\n👤 `{order.get('user_code')}`\n\n📧 `{order.get('email')}`\n🔑 `{order.get('pass')}`\n📝 {order.get('desc')}"
    kb = [[InlineKeyboardButton("✅ تایید", callback_data=f"ok_{order['id']}"), InlineKeyboardButton("❌ رد", callback_data=f"no_{order['id']}")]]
    async def _send(): await bot_app.bot.send_message(chat_id=GROUP_ID, text=text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
    send_telegram_safe(_send())

# ==================== Admin Panel ====================
def get_main_menu(db=None):
    if db is None: db = load_data()
    s = db.get("settings", {})
    is_open, ref_enabled = s.get("registration_open", True), s.get("referral_enabled", True)
    return [
        [InlineKeyboardButton("📦 سفارشات", callback_data="menu_orders"), InlineKeyboardButton("📊 آمار", callback_data="menu_stats")],
        [InlineKeyboardButton("👥 مدیریت کاربران", callback_data="menu_users")],
        [InlineKeyboardButton("📝 ویرایش متن‌ها", callback_data="menu_texts")],
        [InlineKeyboardButton("💰 تنظیم قیمت‌ها", callback_data="menu_prices"), InlineKeyboardButton("🎟️ کد تخفیف", callback_data="menu_coupons")],
        [InlineKeyboardButton("🎁 تخفیف ویژه", callback_data="menu_special")],
        [InlineKeyboardButton("⏳ کد تخفیف تایم‌دار", callback_data="menu_timed_coupon")], # جدید
        [InlineKeyboardButton("🎁 رفرال: روشن" if ref_enabled else "🎁 رفرال: خاموش", callback_data="menu_referral")],
        [InlineKeyboardButton("💳 تنظیم کارت", callback_data="menu_card")],
        [InlineKeyboardButton("🟢 سایت باز است" if is_open else "🔴 سایت بسته است", callback_data="menu_toggle_reg")],
    ]

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    USER_STATES.pop(ADMIN_ID, None)
    await update.message.reply_text("🎮 **پنل مدیریت**", reply_markup=InlineKeyboardMarkup(get_main_menu()), parse_mode="Markdown")

async def button_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    db = load_data()
    s = db.get("settings", {})

    # --- Review Handlers ---
    if data.startswith("rev_ok_") or data.startswith("rev_no_"):
        rev_id = data.split("_")[2]
        new_status = "approved" if data.startswith("rev_ok_") else "rejected"
        with DATA_LOCK:
            for r in db.get("reviews", []):
                if r["id"] == rev_id: r["status"] = new_status; break
            save_data(db)
        await query.answer("ثبت شد ✅", show_alert=True)
        await query.message.delete()
        return

    await query.answer()
    try:
        if data == "back":
            USER_STATES.pop(ADMIN_ID, None)
            await query.edit_message_text("🎮 **پنل مدیریت**", reply_markup=InlineKeyboardMarkup(get_main_menu(db)), parse_mode="Markdown")
        elif data == "menu_timed_coupon":
            code = s.get("timed_coupon_code") or "ندارد"
            pct = s.get("timed_coupon_percent", 0)
            exp = s.get("timed_coupon_expire", 0)
            exp_str = datetime.fromtimestamp(exp).strftime('%H:%M') if exp > time.time() else "منقضی"
            text = f"⏳ **کد تخفیف تایم‌دار**\n\nکد: `{code}`\nدرصد: {pct}%\nانقضا: {exp_str}"
            kb = [[InlineKeyboardButton("➕ ساخت / تغییر", callback_data="timed_set")], [InlineKeyboardButton("❌ حذف", callback_data="timed_del")], [InlineKeyboardButton("🔙 بازگشت", callback_data="back")]]
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
        elif data == "timed_set":
            USER_STATES[ADMIN_ID] = {"state": "waiting_timed_code"}
            await query.edit_message_text("کد تخفیف جدید را بفرست:")
        elif data == "timed_del":
            s["timed_coupon_code"], s["timed_coupon_percent"], s["timed_coupon_expire"] = "", 0, 0
            save_data(db); await query.answer("حذف شد", show_alert=True); await button_handler(update, ctx)
            
        elif data == "menu_referral":
            enabled = s.get("referral_enabled", True)
            kb = [[InlineKeyboardButton("🙈 حذف کامل" if enabled else "🎁 برگرداندن", callback_data="ref_toggle")],[InlineKeyboardButton("💰 تغییر پاداش", callback_data="ref_reward")],[InlineKeyboardButton("📝 توضیحات", callback_data="ref_desc")],[InlineKeyboardButton("🔙 بازگشت", callback_data="back")]]
            await query.edit_message_text(f"🎁 وضعیت: {'روشن' if enabled else 'خاموش'}", reply_markup=InlineKeyboardMarkup(kb))
        elif data == "ref_toggle":
            s["referral_enabled"] = not s.get("referral_enabled", True); save_data(db); await button_handler(update, ctx)
        elif data == "ref_reward": USER_STATES[ADMIN_ID] = {"state": "waiting_ref_reward"}; await query.edit_message_text("مبلغ جدید:")
        elif data == "ref_desc": USER_STATES[ADMIN_ID] = {"state": "waiting_ref_desc"}; await query.edit_message_text("توضیحات جدید:")
        
        elif data == "menu_users":
            users = db.get("users", {})
            if not users: await query.edit_message_text("کاربری نیست.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙", callback_data="back")]])); return
            text, kb = "👥 **کاربران**\n\n", []
            for code, u in list(users.items())[-15:]:
                text += f"`{code}` | {u.get('rubika')} | {u.get('balance', 0):,}\n"
                kb.append([InlineKeyboardButton(code, callback_data=f"user_{code}")])
            kb.append([InlineKeyboardButton("🔙 بازگشت", callback_data="back")])
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
        elif data.startswith("user_"):
            code = data.replace("user_", ""); user = db.get("users", {}).get(code)
            text = f"👤 `{code}`\n💰 {user.get('balance', 0):,}\n🎁 {user.get('referral_count', 0)} رفرال"
            kb = [[InlineKeyboardButton("➕ موجودی", callback_data=f"bal_add_{code}"), InlineKeyboardButton("➖", callback_data=f"bal_sub_{code}")],[InlineKeyboardButton("🚫 تعلیق", callback_data=f"suspend_{code}")],[InlineKeyboardButton("🔙", callback_data="menu_users")]]
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
        elif data.startswith("bal_add_"): USER_STATES[ADMIN_ID] = {"state": "waiting_balance_add", "code": data.replace("bal_add_", "")}; await query.edit_message_text("مبلغ:")
        elif data.startswith("bal_sub_"): USER_STATES[ADMIN_ID] = {"state": "waiting_balance_sub", "code": data.replace("bal_sub_", "")}; await query.edit_message_text("مبلغ:")
        elif data.startswith("suspend_"):
            code = data.replace("suspend_", ""); db["users"][code]["suspended"] = not db["users"][code].get("suspended", False); save_data(db); await button_handler(update, ctx)
        
        elif data == "menu_stats":
            orders = db.get("orders", [])
            text = f"📊 کاربران: {len(db.get('users', {}))}\n📦 سفارشات: {len(orders)}\n✅ تایید: {len([o for o in orders if o.get('status') == 'accepted'])}\n💰 درآمد: {sum(o.get('final_price', 0) for o in orders if o.get('status') == 'accepted'):,}"
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙", callback_data="back")]]))
        elif data == "menu_texts":
            kb = [[InlineKeyboardButton("خوش‌آمد", callback_data="txt_welcome_text1"), InlineKeyboardButton("درباره ما", callback_data="txt_about_text")],[InlineKeyboardButton("🔙", callback_data="back")]]
            await query.edit_message_text("کدوم؟", reply_markup=InlineKeyboardMarkup(kb))
        elif data.startswith("txt_"): USER_STATES[ADMIN_ID] = {"state": f"waiting_text_{data.replace('txt_', '')}"}; await query.edit_message_text("متن جدید:")
        elif data == "menu_prices":
            kb = [[InlineKeyboardButton("نرخ", callback_data="var_price"), InlineKeyboardButton("پکیج", callback_data="pkg_list")],[InlineKeyboardButton("آنتی‌بن", callback_data="extras_price")],[InlineKeyboardButton("🔙", callback_data="back")]]
            await query.edit_message_text("قیمت‌ها:", reply_markup=InlineKeyboardMarkup(kb))
        elif data == "var_price": USER_STATES[ADMIN_ID] = {"state": "waiting_price_var"}; await query.edit_message_text("نرخ جدید:")
        elif data == "extras_price": USER_STATES[ADMIN_ID] = {"state": "waiting_price_antiban"}; await query.edit_message_text("قیمت آنتی‌بن:")
        elif data == "pkg_list": await query.edit_message_text("مدیریت پکیج‌ها (همون قبلی)", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙", callback_data="menu_prices")]]))
        elif data == "menu_special": await query.edit_message_text("تخفیف ویژه (همون قبلی)", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙", callback_data="back")]]))
        elif data == "menu_coupons": await query.edit_message_text("کدهای تخفیف (همون قبلی)", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙", callback_data="back")]]))
        elif data == "menu_card": USER_STATES[ADMIN_ID] = {"state": "waiting_card"}; await query.edit_message_text("شماره کارت - نام:")
        elif data == "menu_orders":
            kb = [[InlineKeyboardButton(o.get('code'), callback_data=f"view_{o['id']}")] for o in db.get("orders", [])[-8:][::-1]]
            kb.append([InlineKeyboardButton("🔙", callback_data="back")]); await query.edit_message_text("سفارشات:", reply_markup=InlineKeyboardMarkup(kb))
        elif data.startswith("view_"):
            order = next((o for o in db.get("orders", []) if o.get("id") == int(data.split("_")[1])), None)
            if order:
                kb = [[InlineKeyboardButton("✅", callback_data=f"ok_{order['id']}"), InlineKeyboardButton("❌", callback_data=f"no_{order['id']}")],[InlineKeyboardButton("🔙", callback_data="menu_orders")]]
                await query.edit_message_text(f"🔢 `{order.get('code')}`\n💰 {order.get('final_price', 0):,}", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
        elif data.startswith("ok_") or data.startswith("no_"):
            oid = int(data.split("_")[1]); new = "accepted" if data.startswith("ok_") else "rejected"
            for o in db.get("orders", []):
                if o.get("id") == oid: o["status"] = new; break
            save_data(db); await button_handler(update, ctx)
        elif data == "menu_toggle_reg":
            s["registration_open"] = not s.get("registration_open", True); save_data(db); await button_handler(update, ctx)
    except Exception as e: print(e)

async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    st = USER_STATES.get(ADMIN_ID)
    if not st: return
    state, text, db, s = st.get("state"), update.message.text.strip(), load_data(), load_data().get("settings", {})
    try:
        if state == "waiting_balance_add": db["users"][st["code"]]["balance"] += int(text)
        elif state == "waiting_balance_sub": db["users"][st["code"]]["balance"] = max(0, db["users"][st["code"]]["balance"] - int(text))
        elif state == "waiting_ref_reward": s["referral_reward"] = int(text)
        elif state == "waiting_ref_desc": s["referral_description"] = text
        elif state == "waiting_price_var": s["price_per_1000"] = int(text)
        elif state == "waiting_price_antiban": s["price_antiban"] = int(text); save_data(db); USER_STATES[ADMIN_ID] = {"state": "waiting_price_fast"}; await update.message.reply_text("قیمت فوری:"); return
        elif state == "waiting_price_fast": s["price_fast"] = int(text)
        elif state == "waiting_card": parts = text.split("-"); s["card_number"] = parts[0].strip(); s["card_holder"] = parts[1].strip() if len(parts) > 1 else ""
        elif state.startswith("waiting_text_"): db.setdefault("texts", {})[state.replace("waiting_text_", "")] = text
        
        # --- Timed Coupon Flow ---
        elif state == "waiting_timed_code":
            st["code"] = text.upper(); st["state"] = "waiting_timed_percent"
            await update.message.reply_text("چند درصد تخفیف؟ (فقط عدد):"); return
        elif state == "waiting_timed_percent":
            st["percent"] = int(text); st["state"] = "waiting_timed_time"
            await update.message.reply_text("چند دقیقه اعتبار داشته باشه؟ (فقط عدد):"); return
        elif state == "waiting_timed_time":
            mins = int(text)
            s["timed_coupon_code"] = st["code"]
            s["timed_coupon_percent"] = st["percent"]
            s["timed_coupon_expire"] = time.time() + (mins * 60)
            save_data(db); USER_STATES.pop(ADMIN_ID, None)
            await update.message.reply_text(f"✅ کد `{st['code']}` برای {mins} دقیقه فعال شد.", reply_markup=InlineKeyboardMarkup(get_main_menu(db)))
            return

        save_data(db); USER_STATES.pop(ADMIN_ID, None)
        await update.message.reply_text("✅ ذخیره شد.", reply_markup=InlineKeyboardMarkup(get_main_menu(db)))
    except ValueError: await update.message.reply_text("❌ خطا در عدد.")
    except Exception as e: print(e)

def run_flask(): app_web.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False, use_reloader=False)

def run_bot():
    global bot_app, main_loop
    if not BOT_TOKEN: return
    async def _main():
        global bot_app, main_loop
        main_loop = asyncio.get_running_loop()
        bot_app = Application.builder().token(BOT_TOKEN).build()
        bot_app.add_handler(CommandHandler("start", start))
        bot_app.add_handler(CallbackQueryHandler(button_handler))
        bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
        await bot_app.initialize(); await bot_app.start(); await bot_app.updater.start_polling(drop_pending_updates=True)
        await asyncio.Event().wait()
    try: asyncio.run(_main())
    except KeyboardInterrupt: pass

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    time.sleep(2)
    run_bot()