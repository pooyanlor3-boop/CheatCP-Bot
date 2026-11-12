# -*- coding: utf-8 -*-
# PhoenixCheat Bot - Fully Debugged & Upgraded Stable Version
# New Update: Added /api/my_orders endpoint for users to view their order history in profile!

import json
import re
import os
import random
import string
import threading
import asyncio
import time
import copy
from datetime import datetime

import requests
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from werkzeug.security import generate_password_hash, check_password_hash

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
RATE_LIMITS = {}  # key -> last ts
LOGIN_FAILS = {}  # ip/fingerprint -> {count, until}
TELEGRAM_QUEUE = []


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
        "custom_packages": [
            {"cp": 10000, "price": 250000, "discount": False},
            {"cp": 20000, "price": 450000, "discount": True},
            {"cp": 30000, "price": 650000, "discount": True},
            {"cp": 40000, "price": 850000, "discount": True}
        ],
        "referral_enabled": True,
        "referral_reward": 25000,
        "referral_title": "سیستم معرفی دوستان",
        "referral_description": "با معرفی دوستات موجودی رایگان بگیر و باهاش سی‌پی بخر!",
        "referral_daily_limit": 10,
        "closed_message": "🔒 سایت در حال بروزرسانی است.\n\nلطفاً برای اطلاع از زمان بازگشایی در کانال عضو شوید:",
        "closed_channel": "https://rubika.ir/PhoenixCheat",
        "closed_channel_text": "عضویت در کانال فونیکس چیت",
        "closed_until": "",
        "timed_coupon_code": "",
        "timed_coupon_percent": 0,
        "timed_coupon_expire": 0,
        "max_reviews_per_day": 3,
        "mod_price_15": 350000,
        "mod_price_30": 500000,
        "mod_price_antiban": 50000,
        "mod_enabled": True,
        "support_user_code": "",
        "blacklist_codes": [],
        "blacklist_uids": [],
        "blocked_fingerprints": [],
        "blocked_ips": [],
        "banner_text": "🎁 افتتاحیه فونیکس چیت — خرید امن سی‌پی و مود منو",
        "banner_enabled": True,
        "faq_items": [],
        "rules_text": "",
        "rate_limit_review_seconds": 20
    },
    "mod_images": {},
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

# ---- in-memory cache to stop freezes when JSONBin is slow ----
_CACHE = {"data": None, "ts": 0.0}
_CACHE_TTL = 5.0  # seconds

def _normalize_db(data):
    if not isinstance(data, dict):
        return copy.deepcopy(DEFAULT_DATA)
    if "orders" not in data or "users" not in data:
        return copy.deepcopy(DEFAULT_DATA)
    if "reviews" not in data:
        data["reviews"] = []
    if "settings" not in data:
        data["settings"] = copy.deepcopy(DEFAULT_DATA["settings"])
    else:
        for k, v in DEFAULT_DATA["settings"].items():
            if k not in data["settings"]:
                data["settings"][k] = v
    if "texts" not in data:
        data["texts"] = copy.deepcopy(DEFAULT_DATA["texts"])
    if "coupons" not in data:
        data["coupons"] = []
    if "mod_images" not in data:
        data["mod_images"] = {}
    return data

def load_data(force=False):
    """Load DB. Uses short memory cache so concurrent logins/payments don't all hit JSONBin."""
    global _CACHE
    now = time.time()
    if (not force) and _CACHE["data"] is not None and (now - _CACHE["ts"]) < _CACHE_TTL:
        return copy.deepcopy(_CACHE["data"])
    bin_id = os.environ.get("JSONBIN_ID")
    api_key = os.environ.get("JSONBIN_KEY")
    if not bin_id or not api_key:
        data = copy.deepcopy(DEFAULT_DATA)
        _CACHE["data"] = copy.deepcopy(data)
        _CACHE["ts"] = now
        return data
    try:
        res = requests.get(
            f"https://api.jsonbin.io/v3/b/{bin_id}/latest",
            headers={"X-Master-Key": api_key},
            timeout=8
        )
        if res.status_code == 200:
            data = _normalize_db(res.json().get("record", {}))
            _CACHE["data"] = copy.deepcopy(data)
            _CACHE["ts"] = time.time()
            return copy.deepcopy(data)
        # keep last good cache if remote fails
        if _CACHE["data"] is not None:
            print("load_data: remote fail, using cache", res.status_code)
            return copy.deepcopy(_CACHE["data"])
        return copy.deepcopy(DEFAULT_DATA)
    except Exception as e:
        print("load_data error:", e)
        if _CACHE["data"] is not None:
            return copy.deepcopy(_CACHE["data"])
        return copy.deepcopy(DEFAULT_DATA)

def _slim_for_jsonbin(data):
    """Keep JSONBin payload small — free tier rejects large bodies."""
    data = copy.deepcopy(data)
    # never persist heavy base64 avatars
    for r in data.get("reviews", []) or []:
        r["avatar"] = ""
        for rep in r.get("replies", []) or []:
            if isinstance(rep, dict):
                rep["avatar"] = ""
                rep.pop("avatar", None)
    users = data.get("users") or {}
    if isinstance(users, dict):
        for u in users.values():
            if isinstance(u, dict):
                u["avatar"] = ""
    # cap lists
    reviews = data.get("reviews") or []
    if len(reviews) > 80:
        # keep newest
        data["reviews"] = reviews[-80:]
    orders = data.get("orders") or []
    if len(orders) > 120:
        data["orders"] = orders[-120:]
    return data

def save_data(data):
    global _CACHE
    bin_id = os.environ.get("JSONBIN_ID")
    api_key = os.environ.get("JSONBIN_KEY")
    if not bin_id or not api_key:
        print("save_data: missing JSONBIN_ID or JSONBIN_KEY env")
        return False
    if not isinstance(data, dict) or "orders" not in data or "users" not in data:
        print("save_data: invalid structure keys=", list(data.keys()) if isinstance(data, dict) else type(data))
        return False
    payload = _slim_for_jsonbin(data)
    headers = {
        "Content-Type": "application/json",
        "X-Master-Key": api_key,
        "X-Bin-Versioning": "false"
    }
    url = f"https://api.jsonbin.io/v3/b/{bin_id}"
    try:
        body = json.dumps(payload, ensure_ascii=False, default=str)
        size_kb = len(body.encode("utf-8")) / 1024.0
        print(f"save_data: putting {size_kb:.1f} KB")
        res = requests.put(url, data=body.encode("utf-8"), headers=headers, timeout=20)
        if res.status_code == 200:
            _CACHE["data"] = copy.deepcopy(payload)
            _CACHE["ts"] = time.time()
            return True
        print("save_data fail:", res.status_code, res.text[:400])
        # retry once
        time.sleep(0.8)
        res2 = requests.put(url, data=body.encode("utf-8"), headers=headers, timeout=20)
        if res2.status_code == 200:
            _CACHE["data"] = copy.deepcopy(payload)
            _CACHE["ts"] = time.time()
            return True
        print("save_data retry fail:", res2.status_code, res2.text[:400])
        # emergency: minimal structure (settings + users + last orders/reviews)
        emergency = {
            "orders": (payload.get("orders") or [])[-40:],
            "next_order_id": payload.get("next_order_id", 1),
            "users": payload.get("users") or {},
            "reviews": (payload.get("reviews") or [])[-30:],
            "settings": payload.get("settings") or {},
            "mod_images": {},
            "coupons": payload.get("coupons") or [],
            "texts": payload.get("texts") or {}
        }
        body3 = json.dumps(emergency, ensure_ascii=False, default=str)
        res3 = requests.put(url, data=body3.encode("utf-8"), headers=headers, timeout=20)
        if res3.status_code == 200:
            print("save_data: emergency slim save OK")
            _CACHE["data"] = copy.deepcopy(emergency)
            _CACHE["ts"] = time.time()
            return True
        print("save_data emergency fail:", res3.status_code, res3.text[:400])
        return False
    except Exception as e:
        print("save_data error:", e)
        return False


WEAK_PASSWORDS = {
    "12345678","123456789","password1","password123","qwerty123","abc12345",
    "11111111","00000000","12qwaszx","admin123","phoenix1","cheat123"
}

def is_weak_password(pw: str) -> bool:
    p = (pw or "").strip().lower()
    if p in WEAK_PASSWORDS:
        return True
    if p.isdigit() and len(p) <= 10:
        return True
    if len(set(p)) <= 2:
        return True
    return False

def security_log(db, event, detail=""):
    logs = db.setdefault("security_logs", [])
    logs.append({
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "event": event,
        "detail": str(detail)[:300],
        "ip": get_client_ip()
    })
    db["security_logs"] = logs[-200:]

def suspend_related(db, user, reason="مشترک بودن دستگاه/IP"):
    users = db.get("users", {})
    hit = []
    ip = user.get("ip")
    fp = user.get("fingerprint")
    rubika = user.get("rubika")
    for c, u in users.items():
        if u.get("suspended"):
            continue
        same = False
        if ip and u.get("ip") == ip:
            same = True
        if fp and u.get("fingerprint") and u.get("fingerprint") == fp:
            same = True
        if rubika and u.get("rubika") == rubika and c != user.get("code"):
            same = True
        if same:
            u["suspended"] = True
            u["suspend_reason"] = reason
            users[c] = u
            hit.append(c)
    db["users"] = users
    return hit

def rate_limited(key, seconds=10):
    now = time.time()
    last = RATE_LIMITS.get(key, 0)
    if now - last < seconds:
        return True
    RATE_LIMITS[key] = now
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
    """Schedule telegram coroutine WITHOUT blocking the Flask request thread.
    Blocking future.result() was freezing login/payment after a while."""
    global main_loop, bot_app
    if not bot_app or not main_loop or main_loop.is_closed():
        return False
    try:
        asyncio.run_coroutine_threadsafe(coro, main_loop)
        return True
    except Exception as e:
        print("send_telegram_safe:", e)
        return False

# ==================== FLASK ====================
@app_web.route("/")
def index():
    return send_from_directory(BASE_DIR, "index.html")

@app_web.route("/api/settings", methods=["GET"])
def get_settings():
    try:
        db = load_data()
        return jsonify({"texts": db.get("texts", {}), "settings": db.get("settings", {}), "mod_images": db.get("mod_images", {})})
    except:
        return jsonify({"error": "Error"}), 500


@app_web.route("/api/db_ping", methods=["GET"])
def db_ping():
    """Diagnose JSONBin connectivity — open in browser to see status."""
    bin_id = os.environ.get("JSONBIN_ID") or ""
    api_key = os.environ.get("JSONBIN_KEY") or ""
    info = {
        "has_bin_id": bool(bin_id),
        "has_key": bool(api_key),
        "key_prefix": (api_key[:6] + "...") if len(api_key) > 6 else "",
        "read_ok": False,
        "write_ok": False,
        "read_status": None,
        "write_status": None,
        "write_body": "",
        "users": 0,
        "orders": 0,
        "reviews": 0
    }
    if not bin_id or not api_key:
        return jsonify(info)
    try:
        r = requests.get(
            f"https://api.jsonbin.io/v3/b/{bin_id}/latest",
            headers={"X-Master-Key": api_key},
            timeout=12
        )
        info["read_status"] = r.status_code
        info["read_ok"] = r.status_code == 200
        if r.status_code == 200:
            rec = r.json().get("record") or {}
            info["users"] = len(rec.get("users") or {})
            info["orders"] = len(rec.get("orders") or [])
            info["reviews"] = len(rec.get("reviews") or [])
            # try tiny write of same record (slim)
            ok = save_data(rec)
            info["write_ok"] = ok
            info["write_status"] = 200 if ok else "fail"
    except Exception as e:
        info["error"] = str(e)
    return jsonify(info)


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
        ip = get_client_ip()
        wait_s = int((load_data().get("settings") or {}).get("rate_limit_review_seconds", 20) or 20)
        if rate_limited(f"review:{ip}", wait_s):
            return jsonify({"success": False, "message": "لطفاً کمی صبر کنید و دوباره نظر بدهید"}), 429
        if stars < 1 or stars > 5:
            stars = 5
        with DATA_LOCK:
            db = load_data()
            max_per_day = db.get("settings", {}).get("max_reviews_per_day", 3)
            today = datetime.now().strftime("%Y-%m-%d")
            if user_code:
                user_reviews_today = [r for r in db.get("reviews", []) if r.get("user_code") == user_code and str(r.get("date", "")).startswith(today)]
                if len(user_reviews_today) >= max_per_day:
                    return jsonify({"success": False, "message": f"حداکثر {max_per_day} نظر در روز مجاز است"}), 400
            rev_id = make_code(6)
            avatar = str(data.get("avatar", "") or "")[:80000]
            review = {
                "id": rev_id, "name": name, "text": text, "stars": stars,
                "user_code": user_code, "status": "pending",
                "avatar": avatar,
                "date": datetime.now().strftime("%Y-%m-%d %H:%M"), "replies": []
            }
            db.setdefault("reviews", []).append(review)
            saved = save_data(db)
        if not saved:
            return jsonify({"success": False, "message": "خطا در ذخیره نظر. دوباره تلاش کنید"}), 500
        text_msg = f"💬 نظر جدید\n\n👤 {name}\n⭐ {stars}/5\n📝 {text}\n\nآیدی: {user_code or 'مهمان'}\nکدنظر: {rev_id}"
        kb = [[InlineKeyboardButton("✅ تایید", callback_data=f"rev_ok_{rev_id}"),
               InlineKeyboardButton("❌ رد", callback_data=f"rev_no_{rev_id}")]]
        async def _send():
            await bot_app.bot.send_message(chat_id=GROUP_ID, text=text_msg, reply_markup=InlineKeyboardMarkup(kb))
        send_telegram_safe(_send())
        return jsonify({"success": True})
    except Exception as e:
        print(e)
        return jsonify({"success": False}), 500

@app_web.route("/api/submit_reply", methods=["POST"])
def submit_reply():
    try:
        data = request.get_json(silent=True) or {}
        review_id = str(data.get("review_id", "")).strip()
        name = str(data.get("name", "")).strip()
        text = str(data.get("text", "")).strip()
        user_code = str(data.get("user_code", "")).strip().upper()
        is_admin = bool(data.get("is_admin", False))
        if not review_id or not name or not text:
            return jsonify({"success": False, "message": "اطلاعات ناقص"}), 400
        with DATA_LOCK:
            db = load_data()
            found = False
            for r in db.get("reviews", []):
                if r.get("id") == review_id:
                    reply = {
                        "id": make_code(5),
                        "name": name,
                        "text": text,
                        "user_code": user_code,
                        "is_admin": is_admin,
                        "status": "approved" if is_admin else "pending",
                        "date": datetime.now().strftime("%Y-%m-%d %H:%M")
                    }
                    r.setdefault("replies", []).append(reply)
                    found = True
                    break
            if not found:
                return jsonify({"success": False, "message": "نظر یافت نشد"}), 404
            save_data(db)
        if not is_admin:
            text_msg = f"💬 **پاسخ جدید به نظر**\n\n👤 {name}\n📝 {text}\n\nآیدی نظر: `{review_id}`"
            kb = [[InlineKeyboardButton("✅ تایید پاسخ", callback_data=f"rep_ok_{review_id}_{reply['id']}"),
                   InlineKeyboardButton("❌ رد", callback_data=f"rep_no_{review_id}_{reply['id']}")]]
            async def _send():
                await bot_app.bot.send_message(chat_id=GROUP_ID, text=text_msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
            send_telegram_safe(_send())
        return jsonify({"success": True})
    except Exception as e:
        print(e)
        return jsonify({"success": False, "message": "خطا"}), 500


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
        captcha_ok = str(data.get("captcha_ok", "")).strip()
        ip = get_client_ip()

        if rate_limited(f"register:{ip}", 8):
            return jsonify({"success": False, "message": "لطفاً کمی صبر کنید"}), 429

        # captcha: client sends expected sum as captcha_ok matching captcha_a+captcha_b
        try:
            ca = int(data.get("captcha_a", -1))
            cb = int(data.get("captcha_b", -1))
            cans = int(data.get("captcha_answer", -999))
            if ca < 0 or cb < 0 or cans != ca + cb:
                return jsonify({"success": False, "message": "کد امنیتی اشتباه است"}), 400
        except Exception:
            return jsonify({"success": False, "message": "کد امنیتی نامعتبر است"}), 400

        # sanitize name
        if not name or len(name) > 15:
            return jsonify({"success": False, "message": "نام باید بین ۱ تا ۱۵ کاراکتر باشد"}), 400
        forbidden = set('<>{}[]\\/`\'";')
        if any(ch in forbidden for ch in name):
            return jsonify({"success": False, "message": "نام شامل کاراکتر غیرمجاز است"}), 400

        if not rubika.startswith("@") or len(rubika) < 6 or not re.match(r'^@[a-zA-Z0-9_]{5,14}$', rubika):
            return jsonify({"success": False, "message": "آیدی روبیکا نامعتبر است"}), 400
        if len(code) < 5 or len(code) > 15 or not all(c.isalnum() or c == "_" for c in code):
            return jsonify({"success": False, "message": "آیدی سایت نامعتبر است"}), 400
        if len(password) < 8 or len(password) > 20:
            return jsonify({"success": False, "message": "رمز باید ۸ تا ۲۰ کاراکتر باشد"}), 400
        if not any(c.isalpha() for c in password) or not any(c.isdigit() for c in password):
            return jsonify({"success": False, "message": "رمز باید شامل حروف و عدد باشد"}), 400
        if is_weak_password(password):
            return jsonify({"success": False, "message": "رمز خیلی ساده است؛ رمز قوی‌تری انتخاب کنید"}), 400

        with DATA_LOCK:
            db = load_data()
            s = db.get("settings", {})
            if not s.get("registration_open", True):
                return jsonify({"success": False, "message": "ثبت‌نام فعلاً بسته است"}), 403

            users = db.get("users", {}) or {}
            if code in users:
                return jsonify({"success": False, "message": "نمی‌توانید با این کد اکانت بسازید"}), 400

            bl_codes = s.get("blacklist_codes") or []
            bl_rubika = s.get("blacklist_rubika") or []
            if code in bl_codes:
                return jsonify({"success": False, "message": "این آیدی مسدود است"}), 403
            if rubika.lower() in [x.lower() for x in bl_rubika]:
                return jsonify({"success": False, "message": "این روبیکا مسدود است"}), 403

            # unique rubika
            for u in users.values():
                if (u.get("rubika") or "").lower() == rubika.lower():
                    return jsonify({"success": False, "message": "این آیدی روبیکا قبلاً ثبت شده است"}), 400

            # permanent device blocks
            blocked_fp = s.get("blocked_fingerprints") or []
            blocked_ips = s.get("blocked_ips") or []
            if fingerprint and fingerprint in blocked_fp:
                security_log(db, "register_blocked_fp_perm", fingerprint[:16])
                save_data(db)
                return jsonify({"success": False, "message": "این دستگاه برای همیشه مسدود است"}), 403
            if ip and ip in blocked_ips:
                security_log(db, "register_blocked_ip_perm", ip)
                save_data(db)
                return jsonify({"success": False, "message": "این اینترنت برای همیشه مسدود است"}), 403

            # one account per fingerprint
            if fingerprint:
                for u in users.values():
                    if u.get("fingerprint") and u.get("fingerprint") == fingerprint and not u.get("_fp_reset"):
                        security_log(db, "register_blocked_fp", f"{code}/{fingerprint[:12]}")
                        save_data(db)
                        return jsonify({"success": False, "message": "از این دستگاه قبلاً اکانت ساخته شده است"}), 403

            # max 1 register per IP / 24h
            now = datetime.now()
            for u in users.values():
                if u.get("ip") == ip and u.get("created_at"):
                    try:
                        created = datetime.strptime(u["created_at"], "%Y-%m-%d %H:%M")
                        if (now - created).total_seconds() < 86400:
                            security_log(db, "register_blocked_ip", f"{ip}")
                            save_data(db)
                            return jsonify({"success": False, "message": "از این اینترنت امروز یک اکانت ساخته شده است"}), 403
                    except Exception:
                        pass

            if not s.get("referral_enabled", True):
                ref_code = None

            hashed_password = generate_password_hash(password)
            user = {
                "code": code, "name": name, "rubika": rubika, "password": hashed_password,
                "balance": 0, "referral_count": 0, "referred_by": None,
                "ip": ip, "fingerprint": fingerprint,
                "created_at": now.strftime("%Y-%m-%d %H:%M"),
                "suspended": False, "suspend_reason": "",
                "avatar": "",
                "last_login": "", "is_new": True,
                "pending_approval": True,
                "mod_expires": "", "session_token": make_code(16),
                "referral_today": 0, "referral_day": "",
                "last_activity": now.strftime("%Y-%m-%d %H:%M")
            }

            # referral only different device
            if ref_code and ref_code in users and ref_code != code:
                referrer = users[ref_code]
                same_device = (referrer.get("ip") == ip) or (fingerprint and referrer.get("fingerprint") == fingerprint)
                if not same_device:
                    today = now.strftime("%Y-%m-%d")
                    if referrer.get("referral_day") != today:
                        referrer["referral_day"] = today
                        referrer["referral_today"] = 0
                    limit = int(s.get("referral_daily_limit", 10) or 10)
                    if referrer.get("referral_today", 0) < limit:
                        users[ref_code]["balance"] = users[ref_code].get("balance", 0) + s.get("referral_reward", 25000)
                        users[ref_code]["referral_count"] = users[ref_code].get("referral_count", 0) + 1
                        users[ref_code]["referral_today"] = referrer.get("referral_today", 0) + 1
                        users[ref_code]["referral_day"] = today
                        user["referred_by"] = ref_code
                        try:
                            reward = s.get("referral_reward", 25000)
                            async def _ref_msg():
                                await bot_app.bot.send_message(
                                    chat_id=GROUP_ID,
                                    text=f"🎁 رفرال موفق\nمعرف: `{ref_code}`\nجدید: `{code}`\n+{reward:,} تومان",
                                    parse_mode="Markdown"
                                )
                            send_telegram_safe(_ref_msg())
                        except Exception:
                            pass

            users[code] = user
            db["users"] = users
            security_log(db, "register_ok", f"{code} {rubika}")
            save_data(db)

        # notify admin for approval
        try:
            async def _new_acc():
                kb = [[
                    InlineKeyboardButton("✅ تأیید اکانت", callback_data=f"approve_user_{code}"),
                    InlineKeyboardButton("🚫 رد/تعلیق", callback_data=f"reject_user_{code}")
                ]]
                await bot_app.bot.send_message(
                    chat_id=GROUP_ID,
                    text=(
                        f"🆕 درخواست اکانت جدید\n"
                        f"نام: {name}\n"
                        f"آیدی سایت: `{code}`\n"
                        f"روبیکا: {rubika}\n"
                        f"IP: `{ip}`\n"
                        f"وضعیت: در انتظار تأیید ادمین"
                    ),
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(kb)
                )
            send_telegram_safe(_new_acc())
        except Exception as e:
            print("new account notify:", e)

        return jsonify({
            "success": True,
            "message": "اکانت ساخته شد. پس از تأیید ادمین می‌توانید وارد شوید.",
            "code": code,
            "pending_approval": True
        })
    except Exception as e:
        print("register error:", e)
        return jsonify({"success": False, "message": "خطای سرور"}), 500



@app_web.route("/api/login", methods=["POST"])
def login():
    try:
        data = request.get_json(silent=True) or {}
        code = str(data.get("code", "")).strip().upper()
        password = str(data.get("password", "")).strip()
        fingerprint = str(data.get("fingerprint", "")).strip()
        ip = get_client_ip()
        fail_key = f"{ip}|{(fingerprint or '')[:32]}"

        if rate_limited(f"login:{ip}", 3):
            return jsonify({"success": False, "message": "لطفاً کمی صبر کنید"}), 429

        info = LOGIN_FAILS.get(fail_key) or {}
        if info.get("until", 0) > time.time():
            left = int(info["until"] - time.time())
            return jsonify({"success": False, "message": f"تلاش زیاد. {left} ثانیه صبر کنید"}), 429
        if not password:
            return jsonify({"success": False, "message": "اطلاعات ورود ناقص است"}), 400

        db = load_data()
        users = db.get("users", {}) or {}
        bl = db.get("settings", {}).get("blacklist_codes") or []
        user = None
        need_upgrade = False

        def _match(u, pw):
            nonlocal need_upgrade
            stored = u.get("password", "")
            if stored.startswith("pbkdf2:") or stored.startswith("scrypt:"):
                return check_password_hash(stored, pw)
            if stored == pw:
                need_upgrade = True
                return True
            return False

        if code and code in users:
            if _match(users[code], password):
                user = users[code]
        else:
            for c_key, u in users.items():
                if _match(u, password):
                    user = u
                    code = c_key
                    break

        if not user:
            fails = int(info.get("count", 0)) + 1
            until = time.time() + (300 if fails >= 5 else 0)
            LOGIN_FAILS[fail_key] = {"count": fails, "until": until}
            # artificial delay against bots
            time.sleep(min(1.5, 0.35 * fails))
            try:
                with DATA_LOCK:
                    db2 = load_data()
                    security_log(db2, "login_fail", f"code={code or '?'} ip={ip}")
                    fails_log = db2.setdefault("login_fails", [])
                    fails_log.append({"time": datetime.now().strftime("%Y-%m-%d %H:%M"), "ip": ip, "code": code or "?"})
                    db2["login_fails"] = fails_log[-100:]
                    save_data(db2)
            except Exception:
                pass
            return jsonify({"success": False, "message": "رمز عبور اشتباه است"}), 403

        if code in bl:
            return jsonify({"success": False, "message": "این اکانت مسدود است"}), 403
        if user.get("suspended"):
            reason = user.get("suspend_reason") or "تخلف امنیتی"
            return jsonify({
                "success": False,
                "suspended": True,
                "message": f"اکانت تعلیق شده است.\nدلیل: {reason}\nبرای پیگیری به پشتیبانی پیام دهید:\nhttps://rubika.ir/My_HINATA"
            }), 403
        if user.get("pending_approval"):
            return jsonify({
                "success": False,
                "pending": True,
                "message": "اکانت شما هنوز توسط ادمین تأیید نشده است. لطفاً صبر کنید."
            }), 403

        # 15 days inactivity expiry
        try:
            la = user.get("last_activity") or user.get("last_login") or user.get("created_at")
            if la:
                last = datetime.strptime(la[:16], "%Y-%m-%d %H:%M")
                if (datetime.now() - last).days > 15:
                    return jsonify({
                        "success": False,
                        "message": "نشست منقضی شده (بیش از ۱۵ روز بی‌فعالیتی). دوباره با رمز وارد شوید و در صورت مشکل به پشتیبانی پیام دهید."
                    }), 403
        except Exception:
            pass

        LOGIN_FAILS.pop(fail_key, None)
        token = make_code(16)
        with DATA_LOCK:
            db2 = load_data(force=False)
            u2 = db2.get("users", {}).get(code)
            if u2:
                if need_upgrade:
                    u2["password"] = generate_password_hash(password)
                if fingerprint:
                    # if fingerprint changed drastically, log
                    old_fp = u2.get("fingerprint") or ""
                    if old_fp and fingerprint and old_fp != fingerprint:
                        security_log(db2, "fp_change", f"{code}")
                    u2["fingerprint"] = fingerprint
                now_s = datetime.now().strftime("%Y-%m-%d %H:%M")
                u2["last_login"] = now_s
                u2["last_activity"] = now_s
                u2["session_token"] = token
                u2["ip"] = ip
                db2["users"][code] = u2
                security_log(db2, "login_ok", code)
                save_data(db2)
                user = u2

        return jsonify({
            "success": True,
            "code": code,
            "name": user.get("name", code),
            "balance": user.get("balance", 0),
            "referral_count": user.get("referral_count", 0),
            "avatar": user.get("avatar", ""),
            "session_token": user.get("session_token", token),
            "last_login": user.get("last_login", ""),
            "mod_expires": user.get("mod_expires", ""),
            "is_new": bool(user.get("is_new", False))
        })
    except Exception as e:
        print("login error:", e)
        return jsonify({"success": False, "message": "خطای سرور"}), 500


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
    except:
        return jsonify({"success": False}), 500

# NEW UPDATE: API endpoint to fetch all orders belonging to a logged-in user code
@app_web.route("/api/my_orders", methods=["POST"])
def my_orders():
    try:
        data = request.get_json(silent=True) or {}
        user_code = str(data.get("user_code", "")).strip().upper()
        if not user_code:
            return jsonify({"success": False, "orders": []}), 400
        db = load_data()
        user_orders = [o for o in db.get("orders", []) if str(o.get("user_code", "")).upper() == user_code]
        # Return newest first
        formatted_orders = []
        for o in user_orders[::-1]:
            st = o.get("status", "pending")
            status_fa = "⏳ در انتظار" if st in ("pending", "pending_payment") else ("✅ تایید شده" if st == "accepted" else "❌ رد شده")
            formatted_orders.append({
                "code": o.get("code"),
                "cp": f"{o.get('cp', 0):,}",
                "price": f"{o.get('final_price', 0):,}",
                "date": o.get("date", ""),
                "status": status_fa,
                "raw_status": st
            })
        return jsonify({"success": True, "orders": formatted_orders})
    except Exception as e:
        print("my_orders error:", e)
        return jsonify({"success": False, "orders": []}), 500

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


@app_web.route("/api/session", methods=["POST"])
def session_check():
    try:
        data = request.get_json(silent=True) or {}
        code = str(data.get("user_code","")).strip().upper()
        token = str(data.get("session_token","")).strip()
        db = load_data()
        u = (db.get("users") or {}).get(code)
        if not u or not token or u.get("session_token") != token:
            return jsonify({"success": False}), 401
        if u.get("suspended") or code in (db.get("settings",{}).get("blacklist_codes") or []):
            return jsonify({"success": False, "suspended": True, "message": u.get("suspend_reason") or "مسدود"}), 403
        if u.get("pending_approval"):
            return jsonify({"success": False, "pending": True, "message": "در انتظار تأیید ادمین"}), 403
        try:
            la = u.get("last_activity") or u.get("last_login") or u.get("created_at")
            if la:
                last = datetime.strptime(str(la)[:16], "%Y-%m-%d %H:%M")
                if (datetime.now() - last).days > 15:
                    return jsonify({"success": False, "message": "نشست منقضی (۱۵ روز بی‌فعالیتی)"}), 401
        except Exception:
            pass
        # touch activity lightly without heavy save every time - skip for speed
        return jsonify({
            "success": True,
            "code": code,
            "name": u.get("name", code),
            "balance": u.get("balance", 0),
            "referral_count": u.get("referral_count", 0),
            "avatar": u.get("avatar", ""),
            "last_login": u.get("last_login", ""),
            "mod_expires": u.get("mod_expires", ""),
            "is_new": bool(u.get("is_new", False))
        })
    except Exception as e:
        return jsonify({"success": False}), 500

@app_web.route("/api/logout_all", methods=["POST"])
def logout_all():
    try:
        data = request.get_json(silent=True) or {}
        code = str(data.get("user_code","")).strip().upper()
        token = str(data.get("session_token","")).strip()
        with DATA_LOCK:
            db = load_data()
            u = (db.get("users") or {}).get(code)
            if not u or u.get("session_token") != token:
                return jsonify({"success": False}), 401
            u["session_token"] = make_code(16)
            db["users"][code] = u
            save_data(db)
        return jsonify({"success": True})
    except Exception:
        return jsonify({"success": False}), 500

@app_web.route("/api/public_extra", methods=["GET"])
def public_extra():
    try:
        db = load_data()
        s = db.get("settings", {})
        texts = db.get("texts", {})
        # recent deliveries anonymized
        recent = []
        for o in (db.get("orders") or [])[::-1]:
            if o.get("status") == "accepted":
                recent.append({
                    "cp": o.get("cp", 0),
                    "when": o.get("date", ""),
                    "type": o.get("product_type") or "cp"
                })
            if len(recent) >= 8:
                break
        return jsonify({
            "banner_text": s.get("banner_text", ""),
            "banner_enabled": s.get("banner_enabled", True),
            "faq_items": s.get("faq_items") or [],
            "rules_text": s.get("rules_text") or "",
            "closed_until": s.get("closed_until") or "",
            "support_user_code": s.get("support_user_code") or "",
            "recent_deliveries": recent,
            "trust_link": texts.get("trust_link") or "https://rubika.ir/PhoenixCheatTrust",
            "channel_link": texts.get("channel_link") or "https://rubika.ir/PhoenixCheat"
        })
    except Exception as e:
        print(e)
        return jsonify({}), 500


@app_web.route("/api/payment_info", methods=["POST"])
def payment_info():
    receipt_path = None
    try:
        data = request.form
        user_code = str(data.get("user_code", "")).strip().upper()
        receipt = request.files.get("receipt")

        def safe_int(v, default=0):
            try:
                return int(float(str(v or 0).replace(",", "")))
            except:
                return default

        try:
            balance_used = int(float(str(data.get("balance_used", 0) or 0).replace(",", "")))
        except:
            balance_used = 0

        # Mutate under lock, network save can use cache (fast path)
        with DATA_LOCK:
            db = load_data()
            oid = db.get("next_order_id", 1)
            user = db.get("users", {}).get(user_code) if user_code else None
            if receipt and receipt.filename:
                ext = os.path.splitext(receipt.filename)[1].lower()
                if ext in [".jpg", ".jpeg", ".png", ".webp"]:
                    receipt_path = os.path.join(BASE_DIR, f"temp_{oid}_{int(time.time())}{ext}")
                    receipt.save(receipt_path)
            if user and balance_used > 0:
                user["balance"] = max(0, user.get("balance", 0) - min(balance_used, user.get("balance", 0)))
            order = {
                "id": oid, "code": make_order_code(),
                "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "cp": safe_int(data.get("cp")),
                "antiban": str(data.get("antiban", "")).lower() == "true",
                "speed": data.get("speed") or "normal",
                "base_price": safe_int(data.get("totalPrice")),
                "discount_amount": safe_int(data.get("discountAmount")),
                "balance_used": balance_used,
                "final_price": safe_int(data.get("finalPrice")),
                "sender_card": data.get("senderCard") or "",
                "sent_amount": data.get("sentAmount") or "",
                "sent_time": data.get("sentTime") or "",
                "user_code": user_code,
                "email": "", "pass": "", "rubika": "", "desc": "",
                "status": "pending_payment",
                "product_type": str(data.get("product_type") or "cp"),
                "mod_plan": str(data.get("mod_plan") or ""),
                "mod_rubika": str(data.get("mod_rubika") or ""),
                "mod_desc": str(data.get("mod_desc") or "")
            }
            db["orders"].append(order)
            db["next_order_id"] = oid + 1
            if user and user_code:
                db["users"][user_code] = user
            saved = save_data(db)

        if not saved:
            print("ERROR: payment order save failed")
            if receipt_path and os.path.exists(receipt_path):
                try: os.remove(receipt_path)
                except Exception: pass
            return jsonify({"success": False, "message": "خطا در ذخیره سفارش. چند ثانیه بعد دوباره تلاش کنید"}), 500
        try:
            send_payment_msg(order, receipt_path)
        except Exception as se:
            print("send_payment_msg error:", se)
        if receipt_path and os.path.exists(receipt_path):
            try:
                os.remove(receipt_path)
            except Exception:
                pass
        return jsonify({"success": True, "order_code": order["code"]})
    except Exception as e:
        print("payment_info error:", e)
        import traceback
        traceback.print_exc()
        if receipt_path and os.path.exists(receipt_path):
            try:
                os.remove(receipt_path)
            except Exception:
                pass
        return jsonify({"success": False, "message": "خطا در ثبت پرداخت"}), 500


@app_web.route("/api/final_order", methods=["POST"])
def final_order():
    try:
        data = request.get_json(silent=True) or {}
        code = str(data.get("order_code", "")).strip()
        if not code:
            return jsonify({"success": False, "message": "کد سفارش نیست"}), 400
        found = False
        with DATA_LOCK:
            db = load_data(force=True)
            for o in db.get("orders", []):
                if str(o.get("code", "")).upper() == code.upper():
                    uid = str(data.get("uid", "") or "").strip()
                    if not uid.isdigit() or len(uid) != 19:
                        return jsonify({"success": False, "message": "یوآیدی باید ۱۹ رقم باشد"}), 400
                    bl_uids = db.get("settings", {}).get("blacklist_uids") or []
                    if uid in bl_uids:
                        return jsonify({"success": False, "message": "این یوآیدی مسدود است"}), 403
                    o["uid"] = uid
                    # mark user not new after first completed info
                    uc = o.get("user_code")
                    if uc and uc in db.get("users", {}):
                        db["users"][uc]["is_new"] = False
                    o["email"] = ""
                    o["pass"] = ""
                    o["rubika"] = data.get("rubika", "")
                    o["desc"] = data.get("desc", "")
                    o["status"] = "pending"
                    if not save_data(db):
                        return jsonify({"success": False, "message": "خطا در ذخیره. دوباره بزنید"}), 500
                    found = True
                    break
        if not found:
            db = load_data(force=False)
            with DATA_LOCK:
                for o in db.get("orders", []):
                    if str(o.get("code", "")).upper() == code.upper():
                        uid = str(data.get("uid", "") or "").strip()
                        if not uid.isdigit() or len(uid) != 19:
                            return jsonify({"success": False, "message": "یوآیدی باید ۱۹ رقم باشد"}), 400
                        o["uid"] = uid
                        o["email"] = ""
                        o["pass"] = ""
                        o["rubika"] = data.get("rubika", "")
                        o["desc"] = data.get("desc", "")
                        o["status"] = "pending"
                        save_data(db)
                        found = True
                        break
        if not found:
            return jsonify({"success": False, "message": "سفارش یافت نشد. از اول پرداخت را انجام دهید"}), 404
        try:
            send_account_msg(code)
        except Exception as se:
            print("send_account_msg error:", se)
        return jsonify({"success": True})
    except Exception as e:
        print("final_order error:", e)
        return jsonify({"success": False, "message": "خطای سرور"}), 500

def send_payment_msg(order, receipt_path=None):
    if not GROUP_ID:
        print("GROUP_ID not set - cannot send payment")
        return
    is_mod = str(order.get('product_type') or '') == 'mod'
    if is_mod:
        plan = order.get('mod_plan') or '-'
        text = (
            f"🎮 سفارش مود منو\n"
            f"🔢 {order.get('code')}\n"
            f"👤 {order.get('user_code') or '-'}\n"
            f"📱 روبیکا: {order.get('mod_rubika') or '-'}\n"
            f"⏱ پلن: {plan} روزه\n"
            f"🛡️ ضد بن: {'بله' if order.get('antiban') else 'خیر'}\n"
            f"💰 {order.get('final_price', 0):,} تومان\n"
            f"📝 {order.get('mod_desc') or '-'}\n"
            f"کارت مبدا: {order.get('sender_card') or '-'}\n"
            f"ساعت: {order.get('sent_time') or '-'}"
        )
    else:
        text = (
            f"💳 پرداخت جدید\n"
            f"🔢 {order.get('code')}\n"
            f"👤 {order.get('user_code') or '-'}\n\n"
            f"💎 {order.get('cp', 0):,} CP\n"
            f"💰 {order.get('final_price', 0):,} تومان\n"
            f"کارت مبدا: {order.get('sender_card') or '-'}\n"
            f"مبلغ: {order.get('sent_amount') or '-'}\n"
            f"ساعت: {order.get('sent_time') or '-'}"
        )
    async def _send():
        try:
            if receipt_path and os.path.exists(receipt_path):
                with open(receipt_path, "rb") as photo:
                    await bot_app.bot.send_photo(chat_id=GROUP_ID, photo=photo, caption=text)
            else:
                await bot_app.bot.send_message(chat_id=GROUP_ID, text=text)
        except Exception as e:
            print("telegram send payment failed:", e)
            await bot_app.bot.send_message(chat_id=GROUP_ID, text=text)
    send_telegram_safe(_send())

def send_account_msg(code):
    db = load_data()
    order = next((o for o in db.get("orders", []) if o.get("code") == code), None)
    if not order:
        return
    uid = order.get("uid") or order.get("email") or "-"
    text = (
        f"👤 اطلاعات اکانت / UID\n"
        f"🔢 `{order['code']}`\n"
        f"👤 `{order.get('user_code')}`\n\n"
        f"🆔 UID: `{uid}`\n"
        f"📱 روبیکا: {order.get('rubika') or '-'}\n"
        f"📝 {order.get('desc') or '-'}\n"
        f"💎 CP: {order.get('cp', 0)}"
    )
    kb = [[InlineKeyboardButton("✅ تایید", callback_data=f"ok_{order['id']}"),
           InlineKeyboardButton("❌ رد", callback_data=f"no_{order['id']}")]]
    async def _send():
        await bot_app.bot.send_message(chat_id=GROUP_ID, text=text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
    send_telegram_safe(_send())

# ==================== ADMIN ====================
def get_main_menu(db=None):
    if db is None:
        db = load_data()
    s = db.get("settings", {})
    is_open = s.get("registration_open", True)
    ref_enabled = s.get("referral_enabled", True)
    return [
        [InlineKeyboardButton("📦 سفارشات", callback_data="menu_orders"),
         InlineKeyboardButton("📊 آمار", callback_data="menu_stats")],
        [InlineKeyboardButton("👥 کاربران", callback_data="menu_users"),
         InlineKeyboardButton("📱 دستگاه‌ها", callback_data="menu_devices")],
        [InlineKeyboardButton("💬 نظرات", callback_data="menu_reviews"),
         InlineKeyboardButton("🛠️ کامنت ادمین", callback_data="menu_admin_comment")],
        [InlineKeyboardButton("📝 متن‌ها", callback_data="menu_texts")],
        [InlineKeyboardButton("💰 قیمت‌ها", callback_data="menu_prices")],
        [InlineKeyboardButton("🎮 مود منو", callback_data="menu_mod")],
        [InlineKeyboardButton("⏳ کد تایم‌دار", callback_data="menu_timed_coupon")],
        [InlineKeyboardButton("🎁 رفرال: روشن" if ref_enabled else "🎁 رفرال: خاموش", callback_data="menu_referral")],
        [InlineKeyboardButton("💳 کارت", callback_data="menu_card")],
        [InlineKeyboardButton("🟢 سایت باز است" if is_open else "🔴 سایت بسته است", callback_data="menu_toggle_reg")],
        [InlineKeyboardButton("🛠 وضعیت سیستم", callback_data="menu_sys"),
         InlineKeyboardButton("📦 JSONBin", callback_data="menu_jsonbin")],
        [InlineKeyboardButton("🚫 بلک‌لیست", callback_data="menu_blacklist"),
         InlineKeyboardButton("🛟 پشتیبانی سایت", callback_data="menu_support_acc")],
    ]

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    USER_STATES.pop(ADMIN_ID, None)
    await update.message.reply_text("🎮 **پنل مدیریت فونیکس چیت**", reply_markup=InlineKeyboardMarkup(get_main_menu()), parse_mode="Markdown")

async def button_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data or ""

    if data.startswith("rev_ok_") or data.startswith("rev_no_"):
        rev_id = data.split("_")[-1]
        new_status = "approved" if data.startswith("rev_ok_") else "rejected"
        found = False
        saved = False
        try:
            with DATA_LOCK:
                db = load_data(force=True)
                for r in db.get("reviews", []):
                    if str(r.get("id", "")).upper() == str(rev_id).upper():
                        r["status"] = new_status
                        if isinstance(r.get("avatar"), str) and len(r.get("avatar") or "") > 8000:
                            r["avatar"] = ""
                        found = True
                        break
                # if remote missed it, try memory cache merge
                if not found and _CACHE.get("data"):
                    for r in (_CACHE["data"].get("reviews") or []):
                        if str(r.get("id", "")).upper() == str(rev_id).upper():
                            r = dict(r)
                            r["status"] = new_status
                            if isinstance(r.get("avatar"), str) and len(r.get("avatar") or "") > 8000:
                                r["avatar"] = ""
                            db.setdefault("reviews", []).append(r)
                            found = True
                            break
                if found:
                    saved = save_data(db)
            if found and saved:
                await query.answer("✅ ثبت شد", show_alert=True)
                try:
                    await query.edit_message_text(
                        ("✅ نظر تایید شد و در سایت نمایش داده می‌شود" if new_status == "approved"
                         else "❌ نظر رد شد") + f"\nآیدی: {rev_id}"
                    )
                except Exception:
                    pass
            elif found and not saved:
                await query.answer("❌ ذخیره JSONBin ناموفق — کلید یا حجم دیتا را چک کن", show_alert=True)
            else:
                await query.answer("❌ نظر پیدا نشد", show_alert=True)
        except Exception as e:
            print("rev_ok error:", e)
            await query.answer("❌ خطا در تایید نظر", show_alert=True)
        return

    if data.startswith("rep_ok_") or data.startswith("rep_no_"):
        parts = data.split("_")
        try:
            review_id, reply_id = parts[2], parts[3]
            new_status = "approved" if data.startswith("rep_ok_") else "rejected"
            with DATA_LOCK:
                db = load_data()
                for r in db.get("reviews", []):
                    if str(r.get("id")) == str(review_id):
                        for rep in r.get("replies", []):
                            if str(rep.get("id")) == str(reply_id):
                                rep["status"] = new_status
                                break
                        break
                save_data(db)
            await query.answer("✅ ثبت شد", show_alert=True)
            try:
                await query.edit_message_text("✅ پاسخ ثبت شد")
            except Exception:
                pass
        except Exception as e:
            print("rep approve error:", e)
            try:
                await query.answer("❌ خطا", show_alert=True)
            except Exception:
                pass
        return

    await query.answer()
    db = load_data()
    s = db.get("settings", {})

    try:
        if data == "back":
            USER_STATES.pop(ADMIN_ID, None)
            await query.edit_message_text("🎮 **پنل مدیریت**", reply_markup=InlineKeyboardMarkup(get_main_menu(db)), parse_mode="Markdown")

        elif data == "menu_toggle_reg":
            s["registration_open"] = not s.get("registration_open", True)
            with DATA_LOCK:
                db["settings"] = s
                save_data(db)
            status = "🟢 سایت باز شد" if s["registration_open"] else "🔴 سایت بسته شد"
            await query.edit_message_text(
                f"{status}\n\n🎮 **پنل مدیریت**",
                reply_markup=InlineKeyboardMarkup(get_main_menu(db)),
                parse_mode="Markdown"
            )

        elif data == "menu_referral":
            enabled = s.get("referral_enabled", True)
            kb = [
                [InlineKeyboardButton("🙈 خاموش کردن" if enabled else "🎁 روشن کردن", callback_data="ref_toggle")],
                [InlineKeyboardButton("💰 تغییر پاداش", callback_data="ref_reward")],
                [InlineKeyboardButton("📝 توضیحات", callback_data="ref_desc")],
                [InlineKeyboardButton("📅 سقف رفرال روزانه", callback_data="ref_daily_limit")],
                [InlineKeyboardButton("🔢 حداکثر نظر روزانه", callback_data="set_max_reviews")],
                [InlineKeyboardButton("🔙 بازگشت", callback_data="back")]
            ]
            await query.edit_message_text(
                f"🎁 وضعیت رفرال: {'روشن ✅' if enabled else 'خاموش ❌'}\nپاداش: {s.get('referral_reward', 25000):,} تومان",
                reply_markup=InlineKeyboardMarkup(kb)
            )

        elif data == "ref_toggle":
            s["referral_enabled"] = not s.get("referral_enabled", True)
            with DATA_LOCK:
                db["settings"] = s
                save_data(db)
            enabled = s["referral_enabled"]
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

        elif data == "ref_daily_limit":
            USER_STATES[ADMIN_ID] = {"state": "waiting_ref_daily"}
            await query.edit_message_text(f"سقف فعلی: {s.get('referral_daily_limit', 10)}\nعدد جدید را بفرست:")
        elif data == "ref_reward":
            USER_STATES[ADMIN_ID] = {"state": "waiting_ref_reward"}
            await query.edit_message_text("مبلغ پاداش رفرال (تومان):")

        elif data == "ref_desc":
            USER_STATES[ADMIN_ID] = {"state": "waiting_ref_desc"}
            await query.edit_message_text("توضیحات بخش رفرال:")

        elif data == "set_max_reviews":
            USER_STATES[ADMIN_ID] = {"state": "waiting_max_reviews"}
            await query.edit_message_text("حداکثر تعداد نظر روزانه هر کاربر:")

        elif data == "menu_admin_comment":
            USER_STATES[ADMIN_ID] = {"state": "waiting_admin_reply_id"}
            await query.edit_message_text("آیدی نظر را بفرست (از بخش نظرات کپی کن):")

        elif data == "menu_reviews":
            reviews = db.get("reviews", [])
            pending = len([r for r in reviews if r.get("status") == "pending"])
            approved = len([r for r in reviews if r.get("status") == "approved"])
            text = f"💬 **نظرات**\n\nدر انتظار: {pending}\nتایید شده: {approved}\nکل: {len(reviews)}"
            kb = []
            for r in reviews[-12:][::-1]:
                icon = "⏳" if r.get("status") == "pending" else ("✅" if r.get("status") == "approved" else "❌")
                kb.append([InlineKeyboardButton(f"{icon} {r.get('name', '')[:12]} - {r.get('stars', 5)}★", callback_data=f"viewrev_{r['id']}")])
            kb.append([InlineKeyboardButton("🔙 بازگشت", callback_data="back")])
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

        elif data.startswith("viewrev_"):
            rev_id = data.replace("viewrev_", "")
            rev = next((r for r in db.get("reviews", []) if r["id"] == rev_id), None)
            if not rev:
                await query.answer("یافت نشد")
                return
            text = f"💬 **نظر**\n\n👤 {rev.get('name')}\n⭐ {rev.get('stars', 5)}/5\n📝 {rev.get('text')}\n📅 {rev.get('date')}\nوضعیت: {rev.get('status')}"
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
            reviews = db.get("reviews", [])
            pending = len([r for r in reviews if r.get("status") == "pending"])
            approved = len([r for r in reviews if r.get("status") == "approved"])
            text = f"💬 **نظرات**\n\nدر انتظار: {pending}\nتایید شده: {approved}\nکل: {len(reviews)}"
            kb = [[InlineKeyboardButton("🔙 بازگشت", callback_data="back")]]
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")


        elif data == "menu_mod":
            kb = [
                [InlineKeyboardButton(f"۱۵ روزه: {s.get('mod_price_15', 350000):,}", callback_data="mod_p15")],
                [InlineKeyboardButton(f"۳۰ روزه: {s.get('mod_price_30', 500000):,}", callback_data="mod_p30")],
                [InlineKeyboardButton(f"ضد بن مود: {s.get('mod_price_antiban', 50000):,}", callback_data="mod_pantiban")],
                [InlineKeyboardButton("🖼 مدیریت عکس‌ها", callback_data="mod_photos")],
                [InlineKeyboardButton("🔙", callback_data="back")]
            ]
            await query.edit_message_text("🎮 تنظیمات مود منو (اندروید/آیفون)", reply_markup=InlineKeyboardMarkup(kb))

        elif data == "mod_p15":
            USER_STATES[ADMIN_ID] = {"state": "waiting_mod_price_15"}
            await query.edit_message_text("قیمت پلن ۱۵ روزه (تومان):")
        elif data == "mod_p30":
            USER_STATES[ADMIN_ID] = {"state": "waiting_mod_price_30"}
            await query.edit_message_text("قیمت پلن ۳۰ روزه (تومان):")
        elif data == "mod_pantiban":
            USER_STATES[ADMIN_ID] = {"state": "waiting_mod_price_antiban"}
            await query.edit_message_text("قیمت ضد بن مود منو (تومان):")

        elif data == "mod_photos":
            features = [
                ("esp_enable", "ESP - فعال‌سازی"),
                ("esp_box", "ESP - باکس"),
                ("esp_name", "ESP - نام"),
                ("esp_distance", "ESP - فاصله"),
                ("esp_health", "ESP - نوار جان"),
                ("esp_count", "ESP - تعداد دشمن"),
                ("esp_snap", "ESP - خط هدایت"),
                ("aim_aimbot", "AIM - ایم‌بات"),
                ("aim_bullet", "AIM - ردیابی گلوله"),
                ("aim_fov", "AIM - FOV"),
                ("aim_bone", "AIM - نقطه هدف"),
                ("radar_enable", "رادار - فعال"),
                ("radar_range", "رادار - برد"),
                ("mem_recoil", "Memory - بدون لگد"),
                ("mem_spread", "Memory - بدون پخش"),
                ("mem_speed", "Memory - سرعت"),
                ("mem_jump", "Memory - پرش"),
                ("skin_main", "اسکین"),
            ]
            kb = []
            imgs = db.get("mod_images", {})
            for key, label in features:
                mark = "✅" if imgs.get(key) else "⬜"
                kb.append([InlineKeyboardButton(f"{mark} {label}", callback_data=f"modimg_{key}")])
            kb.append([InlineKeyboardButton("🔙", callback_data="menu_mod")])
            await query.edit_message_text("عکس کدام گزینه را ست می‌کنی؟", reply_markup=InlineKeyboardMarkup(kb))

        elif data.startswith("modimg_"):
            key = data.replace("modimg_", "", 1)
            USER_STATES[ADMIN_ID] = {"state": "waiting_mod_photo", "photo_key": key}
            await query.edit_message_text(f"عکس این گزینه را همین الان بفرست:\n`{key}`\n\n(فقط یک عکس)", parse_mode="Markdown")


        elif data == "menu_timed_coupon":
            code = s.get("timed_coupon_code") or "ندارد"
            pct = s.get("timed_coupon_percent", 0)
            exp = s.get("timed_coupon_expire", 0)
            exp_str = datetime.fromtimestamp(exp).strftime("%H:%M") if exp > time.time() else "منقضی"
            text = f"⏳ **کد تایم‌دار**\n\nکد: `{code}`\nدرصد: {pct}%\nانقضا: {exp_str}"
            kb = [
                [InlineKeyboardButton("➕ ساخت / تغییر", callback_data="timed_set")],
                [InlineKeyboardButton("❌ حذف", callback_data="timed_del")],
                [InlineKeyboardButton("🔙", callback_data="back")]
            ]
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

        elif data == "timed_set":
            USER_STATES[ADMIN_ID] = {"state": "waiting_timed_code"}
            await query.edit_message_text("کد تخفیف جدید را بفرست:")

        elif data == "timed_del":
            s["timed_coupon_code"] = ""
            s["timed_coupon_percent"] = 0
            s["timed_coupon_expire"] = 0
            with DATA_LOCK:
                db["settings"] = s
                save_data(db)
            await query.answer("حذف شد")
            await query.edit_message_text("🎮 **پنل مدیریت**", reply_markup=InlineKeyboardMarkup(get_main_menu(db)), parse_mode="Markdown")

        elif data == "menu_users":
            users = db.get("users", {})
            if not users:
                await query.edit_message_text("کاربری نیست.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙", callback_data="back")]]))
                return
            text = "👥 **کاربران**\n\n"
            kb = []
            for code, u in list(users.items())[-20:]:
                text += f"`{code}` | {u.get('name', '')} | {u.get('balance', 0):,}\n"
                kb.append([InlineKeyboardButton(code, callback_data=f"user_{code}")])
            kb.append([InlineKeyboardButton("🔙", callback_data="back")])
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

        elif data.startswith("user_"):
            code = data.replace("user_", "")
            user = db.get("users", {}).get(code)
            if not user:
                await query.answer("یافت نشد")
                return
            text = f"👤 `{code}`\nنام: {user.get('name', '-')}\nروبیکا: {user.get('rubika', '-')}\n💰 {user.get('balance', 0):,}\n🎁 رفرال: {user.get('referral_count', 0)}\nوضعیت: {'🚫 تعلیق' if user.get('suspended') else '✅ فعال'}"
            kb = [
                [InlineKeyboardButton("➕ موجودی", callback_data=f"bal_add_{code}"),
                 InlineKeyboardButton("➖ موجودی", callback_data=f"bal_sub_{code}")],
                [InlineKeyboardButton("🚫 تعلیق/رفع", callback_data=f"suspend_{code}")],
                [InlineKeyboardButton("🔙", callback_data="menu_users")]
            ]
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

        elif data.startswith("bal_add_"):
            USER_STATES[ADMIN_ID] = {"state": "waiting_balance_add", "code": data.replace("bal_add_", "")}
            await query.edit_message_text("مبلغ افزایش:")

        elif data.startswith("bal_sub_"):
            USER_STATES[ADMIN_ID] = {"state": "waiting_balance_sub", "code": data.replace("bal_sub_", "")}
            await query.edit_message_text("مبلغ کسر:")

        elif data.startswith("suspend_"):
            code = data.replace("suspend_", "")
            if code in db["users"]:
                db["users"][code]["suspended"] = not db["users"][code].get("suspended", False)
                with DATA_LOCK:
                    save_data(db)
            user = db["users"].get(code, {})
            text = f"👤 `{code}`\nنام: {user.get('name', '-')}\n💰 {user.get('balance', 0):,}\nوضعیت: {'🚫 تعلیق' if user.get('suspended') else '✅ فعال'}"
            kb = [
                [InlineKeyboardButton("➕ موجودی", callback_data=f"bal_add_{code}"),
                 InlineKeyboardButton("➖ موجودی", callback_data=f"bal_sub_{code}")],
                [InlineKeyboardButton("🚫 تعلیق/رفع", callback_data=f"suspend_{code}")],
                [InlineKeyboardButton("🔙", callback_data="menu_users")]
            ]
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

        
        
        elif data == "menu_devices":
            users = db.get("users", {}) or {}
            # group by fingerprint (or ip if no fp)
            devices = {}
            for code, u in users.items():
                fp = (u.get("fingerprint") or "").strip()
                ip = (u.get("ip") or "").strip()
                key = fp if fp else (f"ip:{ip}" if ip else f"user:{code}")
                devices.setdefault(key, []).append(code)
            blocked_fp = set(s.get("blocked_fingerprints") or [])
            blocked_ips = set(s.get("blocked_ips") or [])
            if not devices:
                await query.edit_message_text("دستگاهی ثبت نشده.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙", callback_data="back")]]))
                return
            # sort newest-ish by listing all
            text = "📱 دستگاه‌های ثبت‌شده\n(هر خط یک دستگاه)\n\n"
            kb = []
            items = list(devices.items())[-25:]
            for idx, (key, codes) in enumerate(items):
                u0 = users.get(codes[0], {})
                short = (key[:14] + "…") if len(key) > 15 else key
                flag = ""
                if key in blocked_fp or (key.startswith("ip:") and key[3:] in blocked_ips):
                    flag = " 🔒"
                sus = any(users.get(c, {}).get("suspended") for c in codes)
                if sus:
                    flag += " 🚫"
                text += f"{idx+1}. `{short}` | اکانت: {', '.join(codes)}{flag}\n"
                # callback key must be short - use index into stored list in USER_STATES
                kb.append([InlineKeyboardButton(f"{idx+1}) {codes[0]}{flag}", callback_data=f"dev_i_{idx}")])
            USER_STATES[ADMIN_ID] = {"state": "device_list", "items": items}
            kb.append([InlineKeyboardButton("🔙", callback_data="back")])
            if len(text) > 3500:
                text = text[:3500] + "\n…"
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

        elif data.startswith("dev_i_"):
            try:
                idx = int(data.replace("dev_i_", ""))
            except Exception:
                await query.answer("خطا")
                return
            st = USER_STATES.get(ADMIN_ID) or {}
            items = st.get("items") or []
            if idx < 0 or idx >= len(items):
                await query.answer("لیست منقضی شده؛ دوباره دستگاه‌ها را باز کن", show_alert=True)
                return
            key, codes = items[idx]
            users = db.get("users", {}) or {}
            blocked_fp = s.get("blocked_fingerprints") or []
            blocked_ips = s.get("blocked_ips") or []
            lines = [f"📱 جزئیات دستگاه #{idx+1}", f"کلید: `{key[:40]}`", ""]
            for c in codes:
                u = users.get(c, {})
                lines.append(
                    f"• `{c}` | {u.get('name','-')}\n"
                    f"  روبیکا: {u.get('rubika','-')}\n"
                    f"  IP: `{u.get('ip','-')}`\n"
                    f"  ساخته: {u.get('created_at','-')}\n"
                    f"  ورود: {u.get('last_login','-')}\n"
                    f"  وضعیت: {'🚫 تعلیق' if u.get('suspended') else '✅ فعال'}"
                    + (" | ⏳ تأیید" if u.get('pending_approval') else "")
                )
            is_perm = key in blocked_fp or (key.startswith("ip:") and key[3:] in blocked_ips)
            lines.append("")
            lines.append("🔒 بلاک دائمی دستگاه: " + ("بله" if is_perm else "خیر"))
            text = "\n".join(lines)
            if len(text) > 3500:
                text = text[:3500]
            kb = [
                [InlineKeyboardButton("♻️ ریست دستگاه (اجازه اکانت جدید)", callback_data=f"dev_reset_{idx}")],
                [InlineKeyboardButton("🚫 تعلیق همه اکانت‌های این دستگاه", callback_data=f"dev_sus_{idx}")],
                [InlineKeyboardButton("🔒 مسدود دائمی دستگاه", callback_data=f"dev_perm_{idx}")],
                [InlineKeyboardButton("✅ رفع مسدود دائمی", callback_data=f"dev_unperm_{idx}")],
                [InlineKeyboardButton("🔙 لیست دستگاه‌ها", callback_data="menu_devices")],
            ]
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

        elif data.startswith("dev_reset_"):
            idx = int(data.replace("dev_reset_", ""))
            st = USER_STATES.get(ADMIN_ID) or {}
            items = st.get("items") or []
            if idx < 0 or idx >= len(items):
                await query.answer("لیست منقضی", show_alert=True)
                return
            key, codes = items[idx]
            users = db.get("users", {}) or {}
            for c in codes:
                u = users.get(c)
                if not u:
                    continue
                # clear fingerprint so device can register a new account
                u["fingerprint"] = ""
                u["_fp_reset"] = True
                # free IP 24h lock for one new signup
                if u.get("ip") and not str(u.get("ip")).startswith("reset:"):
                    u["ip"] = "reset:" + str(u.get("ip"))
                users[c] = u
            # also remove from permanent blocks if present
            bf = s.get("blocked_fingerprints") or []
            bi = s.get("blocked_ips") or []
            if key in bf:
                bf = [x for x in bf if x != key]
                s["blocked_fingerprints"] = bf
            if key.startswith("ip:"):
                ip = key[3:]
                bi = [x for x in bi if x != ip]
                s["blocked_ips"] = bi
            db["users"] = users
            db["settings"] = s
            with DATA_LOCK:
                save_data(db)
            # clear login fails soft
            for k in list(LOGIN_FAILS.keys()):
                if key[:12] in k:
                    LOGIN_FAILS.pop(k, None)
            await query.answer("ریست شد ✅", show_alert=True)
            await query.edit_message_text(
                f"♻️ دستگاه ریست شد.\nاکانت‌های قبلی: {', '.join(codes)}\nالان می‌تواند دوباره ثبت‌نام کند (با آیدی جدید).",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 دستگاه‌ها", callback_data="menu_devices")]])
            )

        elif data.startswith("dev_sus_"):
            idx = int(data.replace("dev_sus_", ""))
            st = USER_STATES.get(ADMIN_ID) or {}
            items = st.get("items") or []
            if idx < 0 or idx >= len(items):
                await query.answer("لیست منقضی", show_alert=True)
                return
            key, codes = items[idx]
            users = db.get("users", {}) or {}
            for c in codes:
                if c in users:
                    users[c]["suspended"] = True
                    users[c]["suspend_reason"] = "تعلیق دستگاه توسط ادمین"
            db["users"] = users
            with DATA_LOCK:
                save_data(db)
            await query.answer("تعلیق شد", show_alert=True)
            await query.edit_message_text(
                f"🚫 همه اکانت‌های این دستگاه تعلیق شدند:\n{', '.join(codes)}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙", callback_data="menu_devices")]])
            )

        elif data.startswith("dev_perm_"):
            idx = int(data.replace("dev_perm_", ""))
            st = USER_STATES.get(ADMIN_ID) or {}
            items = st.get("items") or []
            if idx < 0 or idx >= len(items):
                await query.answer("لیست منقضی", show_alert=True)
                return
            key, codes = items[idx]
            users = db.get("users", {}) or {}
            bf = list(s.get("blocked_fingerprints") or [])
            bi = list(s.get("blocked_ips") or [])
            if key.startswith("ip:"):
                ip = key[3:]
                if ip and ip not in bi:
                    bi.append(ip)
            else:
                if key and key not in bf:
                    bf.append(key)
            for c in codes:
                if c in users:
                    users[c]["suspended"] = True
                    users[c]["suspend_reason"] = "مسدود دائمی دستگاه"
            s["blocked_fingerprints"] = bf
            s["blocked_ips"] = bi
            db["settings"] = s
            db["users"] = users
            with DATA_LOCK:
                save_data(db)
            await query.answer("مسدود دائمی شد", show_alert=True)
            await query.edit_message_text(
                f"🔒 دستگاه برای همیشه مسدود شد و اکانت‌ها تعلیق شدند.\n{', '.join(codes)}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙", callback_data="menu_devices")]])
            )

        elif data.startswith("dev_unperm_"):
            idx = int(data.replace("dev_unperm_", ""))
            st = USER_STATES.get(ADMIN_ID) or {}
            items = st.get("items") or []
            if idx < 0 or idx >= len(items):
                await query.answer("لیست منقضی", show_alert=True)
                return
            key, codes = items[idx]
            bf = list(s.get("blocked_fingerprints") or [])
            bi = list(s.get("blocked_ips") or [])
            if key.startswith("ip:"):
                ip = key[3:]
                bi = [x for x in bi if x != ip]
            else:
                bf = [x for x in bf if x != key]
            s["blocked_fingerprints"] = bf
            s["blocked_ips"] = bi
            db["settings"] = s
            with DATA_LOCK:
                save_data(db)
            await query.answer("رفع مسدود دائمی", show_alert=True)
            await query.edit_message_text(
                "✅ مسدود دائمی دستگاه برداشته شد.\n(برای اجازه ثبت‌نام جدید از ریست دستگاه هم استفاده کن)",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙", callback_data="menu_devices")]])
            )


        elif data == "menu_sys":
            orders = db.get("orders", [])
            users = db.get("users", {})
            text = (
                "🛠 وضعیت سیستم\n\n"
                f"کاربران: {len(users)}\n"
                f"سفارشات: {len(orders)}\n"
                f"نظرات: {len(db.get('reviews', []))}\n"
                f"سایت: {'باز' if s.get('registration_open', True) else 'بسته'}\n"
                f"رفرال: {'روشن' if s.get('referral_enabled', True) else 'خاموش'}\n"
                f"سقف رفرال روزانه: {s.get('referral_daily_limit', 10)}\n"
                f"پشتیبانی سایت: `{s.get('support_user_code') or 'تنظیم نشده'}`"
            )
            kb = [
                [InlineKeyboardButton("🧪 تست ذخیره", callback_data="sys_test_save")],
                [InlineKeyboardButton("🔙", callback_data="back")]
            ]
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

        elif data == "sys_test_save":
            ok = save_data(load_data(force=True))
            await query.answer("موفق ✅" if ok else "ناموفق ❌", show_alert=True)

        elif data == "menu_jsonbin":
            bin_id = os.environ.get("JSONBIN_ID") or ""
            api_key = os.environ.get("JSONBIN_KEY") or ""
            read_ok = write_ok = False
            status = "?"
            size_est = 0
            try:
                r = requests.get(
                    f"https://api.jsonbin.io/v3/b/{bin_id}/latest",
                    headers={"X-Master-Key": api_key},
                    timeout=12
                )
                status = str(r.status_code)
                read_ok = r.status_code == 200
                if read_ok:
                    rec = r.json().get("record") or {}
                    size_est = len(json.dumps(rec, ensure_ascii=False).encode("utf-8"))
                    write_ok = save_data(rec)
            except Exception as e:
                status = str(e)[:80]
            text = (
                "📦 JSONBin\n\n"
                f"Bin ID: `{bin_id[:8]}...`\n"
                f"Key: `{(api_key[:6]+'...') if api_key else '—'}`\n"
                f"خواندن: {'✅' if read_ok else '❌'} ({status})\n"
                f"نوشتن: {'✅' if write_ok else '❌'}\n"
                f"حجم تقریبی دیتا: {size_est/1024:.1f} KB\n\n"
                "⚠️ تغییر Bin/Key فقط از Environment رندر"
            )
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙", callback_data="back")]]), parse_mode="Markdown")

        elif data == "menu_blacklist":
            codes = s.get("blacklist_codes") or []
            uids = s.get("blacklist_uids") or []
            text = f"🚫 بلک‌لیست\nآیدی سایت: {len(codes)}\nUID: {len(uids)}"
            kb = [
                [InlineKeyboardButton("➕ بلاک آیدی سایت", callback_data="bl_add_code")],
                [InlineKeyboardButton("➕ بلاک UID", callback_data="bl_add_uid")],
                [InlineKeyboardButton("📋 نمایش", callback_data="bl_list")],
                [InlineKeyboardButton("🔙", callback_data="back")]
            ]
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))

        elif data == "bl_add_code":
            USER_STATES[ADMIN_ID] = {"state": "waiting_bl_code"}
            await query.edit_message_text("آیدی سایت برای بلاک:")
        elif data == "bl_add_uid":
            USER_STATES[ADMIN_ID] = {"state": "waiting_bl_uid"}
            await query.edit_message_text("UID ۱۹ رقمی برای بلاک:")
        elif data == "bl_list":
            codes = s.get("blacklist_codes") or []
            uids = s.get("blacklist_uids") or []
            text = "آیدی‌ها:\n" + ("\n".join(codes[-30:]) or "—") + "\n\nUIDها:\n" + ("\n".join(uids[-30:]) or "—")
            await query.edit_message_text(text[:3500], reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙", callback_data="menu_blacklist")]]))

        elif data == "menu_support_acc":
            cur = s.get("support_user_code") or "تنظیم نشده"
            USER_STATES[ADMIN_ID] = {"state": "waiting_support_code"}
            await query.edit_message_text(f"آیدی سایت اکانت پشتیبانی فعلی: `{cur}`\n\nآیدی جدید را بفرست:", parse_mode="Markdown")

        elif data == "menu_stats":
            orders = db.get("orders", [])
            today = datetime.now().strftime("%Y-%m-%d")
            today_orders = [o for o in orders if str(o.get("date","")).startswith(today)]
            text = (
                f"📊 آمار\n\n"
                f"کاربران: {len(db.get('users', {}))}\n"
                f"سفارشات کل: {len(orders)}\n"
                f"تایید شده: {len([o for o in orders if o.get('status') == 'accepted'])}\n"
                f"درآمد کل: {sum(o.get('final_price', 0) for o in orders if o.get('status') == 'accepted'):,}\n"
                f"نظرات: {len(db.get('reviews', []))}\n\n"
                f"امروز: {len(today_orders)} سفارش\n"
                f"درآمد امروز: {sum(o.get('final_price', 0) for o in today_orders if o.get('status')=='accepted'):,}"
            )
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙", callback_data="back")]]))

        elif data == "menu_texts":
            kb = [
                [InlineKeyboardButton("خوش‌آمد ۱", callback_data="txt_welcome_text1"),
                 InlineKeyboardButton("خوش‌آمد ۲", callback_data="txt_welcome_text2")],
                [InlineKeyboardButton("درباره ما", callback_data="txt_about_text")],
                [InlineKeyboardButton("پیام بستن سایت", callback_data="txt_closed_message")],
                [InlineKeyboardButton("🔙", callback_data="back")]
            ]
            await query.edit_message_text("کدام متن؟", reply_markup=InlineKeyboardMarkup(kb))

        elif data.startswith("txt_"):
            key = data.replace("txt_", "")
            USER_STATES[ADMIN_ID] = {"state": f"waiting_text_{key}"}
            await query.edit_message_text("متن جدید را بفرست:")

        elif data == "menu_prices":
            pkgs = s.get("custom_packages") or []
            pkg_lines = "\n".join([f"{'🔥' if p.get('discount') else '•'} {p.get('cp',0):,} CP = {p.get('price',0):,}" for p in pkgs]) or "خالی"
            kb = [
                [InlineKeyboardButton("نرخ هر ۱۰۰۰ (عادی)", callback_data="var_price")],
                [InlineKeyboardButton("آنتی‌بن + فوری", callback_data="extras_price")],
                [InlineKeyboardButton("📦 پکیج‌های تخفیف/قیمت", callback_data="menu_packages")],
                [InlineKeyboardButton("🔙", callback_data="back")]
            ]
            await query.edit_message_text(
                f"قیمت فعلی:\nهر ۱۰۰۰: {s.get('price_per_1000', 25000):,}\nآنتی‌بن: {s.get('price_antiban', 50000):,}\nفوری: {s.get('price_fast', 20000):,}\n\nپکیج‌ها:\n{pkg_lines}",
                reply_markup=InlineKeyboardMarkup(kb)
            )

        elif data == "menu_packages":
            pkgs = s.get("custom_packages") or []
            kb = []
            for i, p in enumerate(pkgs):
                flag = "🔥" if p.get("discount") else "•"
                kb.append([InlineKeyboardButton(f"{flag} {p.get('cp',0):,} = {p.get('price',0):,}", callback_data=f"pkg_edit_{i}")])
            kb.append([InlineKeyboardButton("➕ افزودن پکیج", callback_data="pkg_add")])
            kb.append([InlineKeyboardButton("🔙", callback_data="menu_prices")])
            await query.edit_message_text("پکیج‌ها (برای دکمه‌های تخفیف‌خورده روی سایت):", reply_markup=InlineKeyboardMarkup(kb))

        elif data == "pkg_add":
            USER_STATES[ADMIN_ID] = {"state": "waiting_pkg_cp"}
            await query.edit_message_text("مقدار سی‌پی پکیج را بفرست (مثلاً 20000):")

        elif data.startswith("pkg_edit_"):
            idx = int(data.split("_")[-1])
            pkgs = s.get("custom_packages") or []
            if idx < 0 or idx >= len(pkgs):
                await query.answer("نامعتبر")
                return
            p = pkgs[idx]
            kb = [
                [InlineKeyboardButton("✏️ تغییر قیمت", callback_data=f"pkg_price_{idx}")],
                [InlineKeyboardButton("🔥 تخفیف روشن/خاموش", callback_data=f"pkg_disc_{idx}")],
                [InlineKeyboardButton("🗑 حذف", callback_data=f"pkg_del_{idx}")],
                [InlineKeyboardButton("🔙", callback_data="menu_packages")]
            ]
            await query.edit_message_text(
                f"پکیج {p.get('cp',0):,} CP\nقیمت: {p.get('price',0):,}\nتخفیف: {'بله' if p.get('discount') else 'خیر'}",
                reply_markup=InlineKeyboardMarkup(kb)
            )

        elif data.startswith("pkg_price_"):
            idx = int(data.split("_")[-1])
            USER_STATES[ADMIN_ID] = {"state": "waiting_pkg_price", "idx": idx}
            await query.edit_message_text("قیمت جدید این پکیج (تومان):")

        elif data.startswith("pkg_disc_"):
            idx = int(data.split("_")[-1])
            pkgs = s.get("custom_packages") or []
            if 0 <= idx < len(pkgs):
                pkgs[idx]["discount"] = not bool(pkgs[idx].get("discount"))
                s["custom_packages"] = pkgs
                with DATA_LOCK:
                    db["settings"] = s
                    save_data(db)
            await query.answer("ثبت شد")
            # refresh
            p = pkgs[idx]
            kb = [
                [InlineKeyboardButton("✏️ تغییر قیمت", callback_data=f"pkg_price_{idx}")],
                [InlineKeyboardButton("🔥 تخفیف روشن/خاموش", callback_data=f"pkg_disc_{idx}")],
                [InlineKeyboardButton("🗑 حذف", callback_data=f"pkg_del_{idx}")],
                [InlineKeyboardButton("🔙", callback_data="menu_packages")]
            ]
            await query.edit_message_text(
                f"پکیج {p.get('cp',0):,} CP\nقیمت: {p.get('price',0):,}\nتخفیف: {'بله' if p.get('discount') else 'خیر'}",
                reply_markup=InlineKeyboardMarkup(kb)
            )

        elif data.startswith("pkg_del_"):
            idx = int(data.split("_")[-1])
            pkgs = s.get("custom_packages") or []
            if 0 <= idx < len(pkgs):
                pkgs.pop(idx)
                s["custom_packages"] = pkgs
                with DATA_LOCK:
                    db["settings"] = s
                    save_data(db)
            await query.answer("حذف شد")
            kb = [[InlineKeyboardButton("🔙", callback_data="menu_prices")]]
            await query.edit_message_text("حذف شد.", reply_markup=InlineKeyboardMarkup(kb))


        elif data == "var_price":
            USER_STATES[ADMIN_ID] = {"state": "waiting_price_var"}
            await query.edit_message_text("نرخ جدید هر ۱۰۰۰ سی‌پی:")

        elif data == "extras_price":
            USER_STATES[ADMIN_ID] = {"state": "waiting_price_antiban"}
            await query.edit_message_text("قیمت آنتی‌بن:")

        elif data == "menu_card":
            USER_STATES[ADMIN_ID] = {"state": "waiting_card"}
            await query.edit_message_text("شماره کارت - نام صاحب کارت\nمثال:\n6219... - یوسف موسوی")

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
                text = f"🔢 `{order.get('code')}`\n👤 {order.get('user_code')}\n💎 {order.get('cp'):,} CP\n💰 {order.get('final_price', 0):,}\nوضعیت: {order.get('status')}"
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
            with DATA_LOCK:
                save_data(db)
            await query.answer("ثبت شد")
            await query.edit_message_text("🎮 **پنل مدیریت**", reply_markup=InlineKeyboardMarkup(get_main_menu(db)), parse_mode="Markdown")

    except Exception as e:
        print("button_handler error:", e)

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
            USER_STATES.pop(ADMIN_ID, None)
            await update.message.reply_text(f"✅ {amount:,} تومان اضافه شد.", reply_markup=InlineKeyboardMarkup(get_main_menu(db)))
            return

        elif state == "waiting_balance_sub":
            code = st["code"]
            amount = int(text)
            if code in db["users"]:
                db["users"][code]["balance"] = max(0, db["users"][code].get("balance", 0) - amount)
                save_data(db)
            USER_STATES.pop(ADMIN_ID, None)
            await update.message.reply_text(f"✅ {amount:,} تومان کسر شد.", reply_markup=InlineKeyboardMarkup(get_main_menu(db)))
            return

        elif state == "waiting_ref_daily":
            s["referral_daily_limit"] = int(text)
            db["settings"] = s
            save_data(db)
            USER_STATES.pop(ADMIN_ID, None)
            await update.message.reply_text("✅ سقف رفرال روزانه ذخیره شد.", reply_markup=InlineKeyboardMarkup(get_main_menu(db)))
            return
        elif state == "waiting_bl_code":
            code = text.strip().upper()
            lst = s.get("blacklist_codes") or []
            if code not in lst:
                lst.append(code)
            s["blacklist_codes"] = lst
            db["settings"] = s
            save_data(db)
            USER_STATES.pop(ADMIN_ID, None)
            await update.message.reply_text("✅ بلاک شد.", reply_markup=InlineKeyboardMarkup(get_main_menu(db)))
            return
        elif state == "waiting_bl_uid":
            uid = text.strip()
            if not uid.isdigit() or len(uid) != 19:
                await update.message.reply_text("UID باید ۱۹ رقم باشد")
                return
            lst = s.get("blacklist_uids") or []
            if uid not in lst:
                lst.append(uid)
            s["blacklist_uids"] = lst
            db["settings"] = s
            save_data(db)
            USER_STATES.pop(ADMIN_ID, None)
            await update.message.reply_text("✅ UID بلاک شد.", reply_markup=InlineKeyboardMarkup(get_main_menu(db)))
            return
        elif state == "waiting_support_code":
            s["support_user_code"] = text.strip().upper()
            db["settings"] = s
            save_data(db)
            USER_STATES.pop(ADMIN_ID, None)
            await update.message.reply_text("✅ اکانت پشتیبانی تنظیم شد.", reply_markup=InlineKeyboardMarkup(get_main_menu(db)))
            return
        elif state == "waiting_ref_reward":
            s["referral_reward"] = int(text)
            db["settings"] = s
            save_data(db)
            USER_STATES.pop(ADMIN_ID, None)
            await update.message.reply_text("✅ ذخیره شد.", reply_markup=InlineKeyboardMarkup(get_main_menu(db)))
            return

        elif state == "waiting_ref_desc":
            s["referral_description"] = text
            db["settings"] = s
            save_data(db)
            USER_STATES.pop(ADMIN_ID, None)
            await update.message.reply_text("✅ ذخیره شد.", reply_markup=InlineKeyboardMarkup(get_main_menu(db)))
            return

        elif state == "waiting_max_reviews":
            s["max_reviews_per_day"] = int(text)
            db["settings"] = s
            save_data(db)
            USER_STATES.pop(ADMIN_ID, None)
            await update.message.reply_text("✅ ذخیره شد.", reply_markup=InlineKeyboardMarkup(get_main_menu(db)))
            return

        elif state == "waiting_price_var":
            s["price_per_1000"] = int(text)
            db["settings"] = s
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
            db["settings"] = s
            save_data(db)
            USER_STATES.pop(ADMIN_ID, None)
            await update.message.reply_text("✅ ذخیره شد.", reply_markup=InlineKeyboardMarkup(get_main_menu(db)))
            return

        elif state == "waiting_card":
            parts = text.split("-")
            s["card_number"] = parts[0].strip()
            s["card_holder"] = parts[1].strip() if len(parts) > 1 else ""
            db["settings"] = s
            save_data(db)
            USER_STATES.pop(ADMIN_ID, None)
            await update.message.reply_text("✅ ذخیره شد.", reply_markup=InlineKeyboardMarkup(get_main_menu(db)))
            return

        elif state.startswith("waiting_text_"):
            key = state.replace("waiting_text_", "")
            if key == "closed_message":
                s["closed_message"] = text
                db["settings"] = s
            else:
                db.setdefault("texts", {})[key] = text
            save_data(db)
            USER_STATES.pop(ADMIN_ID, None)
            await update.message.reply_text("✅ ذخیره شد.", reply_markup=InlineKeyboardMarkup(get_main_menu(db)))
            return

        elif state == "waiting_admin_reply_id":
            st["review_id"] = text.strip()
            st["state"] = "waiting_admin_reply_text"
            await update.message.reply_text("متن پاسخ ادمین را بفرست:")
            return

        elif state == "waiting_admin_reply_text":
            review_id = st.get("review_id")
            with DATA_LOCK:
                db = load_data()
                for r in db.get("reviews", []):
                    if r.get("id") == review_id:
                        r.setdefault("replies", []).append({
                            "id": make_code(5),
                            "name": "پشتیبانی فونیکس",
                            "text": text,
                            "is_admin": True,
                            "status": "approved",
                            "date": datetime.now().strftime("%Y-%m-%d %H:%M")
                        })
                        save_data(db)
                        break
            USER_STATES.pop(ADMIN_ID, None)
            await update.message.reply_text("✅ پاسخ ادمین ثبت شد.", reply_markup=InlineKeyboardMarkup(get_main_menu(db)))
            return

        elif state == "waiting_timed_code":
            st["code"] = text.upper()
            st["state"] = "waiting_timed_percent"
            await update.message.reply_text("چند درصد تخفیف؟ (فقط عدد):")
            return

        elif state == "waiting_timed_percent":
            st["percent"] = int(text)
            st["state"] = "waiting_timed_time"
            await update.message.reply_text("چند دقیقه اعتبار داشته باشد؟")
            return

        elif state == "waiting_timed_time":
            mins = int(text)
            s["timed_coupon_code"] = st["code"]
            s["timed_coupon_percent"] = st["percent"]
            s["timed_coupon_expire"] = time.time() + (mins * 60)
            db["settings"] = s
            save_data(db)
            USER_STATES.pop(ADMIN_ID, None)
            await update.message.reply_text(f"✅ کد `{st['code']}` برای {mins} دقیقه فعال شد.", reply_markup=InlineKeyboardMarkup(get_main_menu(db)), parse_mode="Markdown")
            return

    except ValueError:
        await update.message.reply_text("❌ عدد معتبر وارد کنید.")
    except Exception as e:
        print("handle_text error:", e)
        await update.message.reply_text("❌ خطا رخ داد.")


async def handle_photo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    st = USER_STATES.get(ADMIN_ID) or {}
    if st.get("state") != "waiting_mod_photo":
        return
    key = st.get("photo_key")
    if not key or not update.message.photo:
        return
    try:
        photo = update.message.photo[-1]
        file = await bot_app.bot.get_file(photo.file_id)
        # store telegram file path reference (served via proxy)
        file_url = file.file_path  # relative path
        with DATA_LOCK:
            db = load_data()
            db.setdefault("mod_images", {})[key] = {
                "file_id": photo.file_id,
                "file_path": file_url
            }
            save_data(db)
        USER_STATES.pop(ADMIN_ID, None)
        await update.message.reply_text(f"✅ عکس `{key}` ذخیره شد.", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(get_main_menu(db)))
    except Exception as e:
        print("handle_photo error:", e)
        await update.message.reply_text("❌ خطا در ذخیره عکس")


@app_web.route("/api/mod_photo/<key>")
def mod_photo_proxy(key):
    """Proxy mod feature image - refreshes Telegram file path via file_id"""
    try:
        from flask import Response
        db = load_data()
        info = (db.get("mod_images") or {}).get(key)
        if not info:
            return "Not found", 404
        if isinstance(info, str):
            if info.startswith("http"):
                r = requests.get(info, timeout=20)
                if r.status_code == 200:
                    return Response(r.content, mimetype=r.headers.get("Content-Type", "image/jpeg"))
            return "Not found", 404
        if not BOT_TOKEN:
            return "No token", 500
        file_id = info.get("file_id") or ""
        if not file_id:
            return "Not found", 404
        # Always resolve fresh path (Telegram paths expire)
        meta = requests.get(
            f"https://api.telegram.org/bot{BOT_TOKEN}/getFile",
            params={"file_id": file_id},
            timeout=15
        ).json()
        if not meta.get("ok"):
            print("getFile fail", meta)
            return "Telegram getFile failed", 502
        file_path = meta["result"].get("file_path") or ""
        if not file_path:
            return "No path", 502
        # cache fresh path
        try:
            with DATA_LOCK:
                db2 = load_data()
                if key in db2.get("mod_images", {}):
                    db2["mod_images"][key]["file_path"] = file_path
                    save_data(db2)
        except Exception:
            pass
        url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
        r = requests.get(url, timeout=25)
        if r.status_code != 200:
            print("download fail", r.status_code)
            return "Fetch failed", 502
        return Response(
            r.content,
            mimetype=r.headers.get("Content-Type", "image/jpeg"),
            headers={"Cache-Control": "public, max-age=3600"}
        )
    except Exception as e:
        print("mod_photo_proxy:", e)
        return "Error", 500



def run_flask():
    port = int(os.environ.get("PORT", 5000))
    # threaded=True so one slow JSONBin/Telegram call cannot freeze all logins
    app_web.run(host="0.0.0.0", port=port, debug=False, use_reloader=False, threaded=True)

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
        bot_app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
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
