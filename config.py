# -*- coding: utf-8 -*-
# CheatCP Bot - Config File
# Reads from Environment Variables (Render) or defaults

import os

# ==========================================
# BOT SETTINGS
# ==========================================

# Bot Token (از Environment Variables)
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Admin User ID
ADMIN_ID = int(os.getenv("ADMIN_ID", "8113206201"))

# Group Chat ID
GROUP_ID = int(os.getenv("GROUP_ID", "-1004335107809"))

# ==========================================
# PROXY SETTINGS
# ==========================================

# True = Proxy ON | False = Direct
USE_PROXY = os.getenv("USE_PROXY", "False").lower() == "true"

# Proxy Type
PROXY_TYPE = os.getenv("PROXY_TYPE", "socks5")

# Proxy Host
PROXY_HOST = os.getenv("PROXY_HOST", "127.0.0.1")

# Proxy Port
PROXY_PORT = int(os.getenv("PROXY_PORT", "12334"))

# ==========================================
# GENERAL SETTINGS
# ==========================================

# Report interval in minutes
REPORT_INTERVAL = int(os.getenv("REPORT_INTERVAL", "360"))

# Report enabled
REPORT_ENABLED = os.getenv("REPORT_ENABLED", "True").lower() == "true"

# User code prefix
CODE_PREFIX = os.getenv("CODE_PREFIX", "CP")

# Max SP allowed
MAX_SP = int(os.getenv("MAX_SP", "100000"))

# SP suggestions
SP_OPTIONS = [10000, 20000, 50000, 80000, 100000]

# Support ID
SUPPORT_ID = os.getenv("SUPPORT_ID", "@My_HINATA")