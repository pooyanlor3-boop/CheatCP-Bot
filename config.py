# -*- coding: utf-8 -*-
# PhoenixCheat Bot - Config File
# Reads from Environment Variables (Render) or defaults

import os

# ==========================================
# BOT SETTINGS
# ==========================================

# Bot Token - از Environment Variables خونده می‌شه
# ⚠️ توی Render باید BOT_TOKEN رو تنظیم کنی
# ⚠️ برای تست محلی، از فایل .env استفاده کن
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Admin User ID (خودت)
ADMIN_ID = int(os.getenv("ADMIN_ID", "8113206201"))

# Group Chat ID - از Environment Variables خونده می‌شه
# می‌تونی از توی ربات هم تغییرش بدی (توی data.json ذخیره می‌شه)
GROUP_ID = int(os.getenv("GROUP_ID", "-1004335107809"))

# ==========================================
# PROXY SETTINGS
# ==========================================

# True = Proxy ON | False = Direct
USE_PROXY = os.getenv("USE_PROXY", "False").lower() == "true"

# Proxy Type: socks5 or socks4
PROXY_TYPE = os.getenv("PROXY_TYPE", "socks5")

# Proxy Host
PROXY_HOST = os.getenv("PROXY_HOST", "127.0.0.1")

# Proxy Port
PROXY_PORT = int(os.getenv("PROXY_PORT", "12334"))

# ==========================================
# GENERAL SETTINGS
# ==========================================

# Report interval in minutes (default 6 hours)
REPORT_INTERVAL = int(os.getenv("REPORT_INTERVAL", "360"))

# Report enabled
REPORT_ENABLED = os.getenv("REPORT_ENABLED", "True").lower() == "true"

# User code prefix
CODE_PREFIX = os.getenv("CODE_PREFIX", "CP")

# Max CP allowed
MAX_CP = int(os.getenv("MAX_CP", "100000"))

# CP suggestions
CP_OPTIONS = [10000, 20000, 50000, 80000, 100000]

# Support ID
SUPPORT_ID = os.getenv("SUPPORT_ID", "@My_HINATA")

# Channel ID
CHANNEL_ID = os.getenv("CHANNEL_ID", "Rubika.ir/PhoenixCheat")

# Trust Channel ID
TRUST_ID = os.getenv("TRUST_ID", "Rubika.ir/PhoenixCheatTrust")

# Telegram ID
TELEGRAM_ID = os.getenv("TELEGRAM_ID", "t.me/Phoenix1Cheat")

# ==========================================
# WEBSITE TEXTS
# ==========================================

# Welcome text
WELCOME_TEXT = os.getenv("WELCOME_TEXT", "به PhoenixCheat خوش اومدی!")

# About text
ABOUT_TEXT = os.getenv("ABOUT_TEXT", "ما یه تیم حرفه‌ای از گیمرهای کالاف دیوتی هستیم")