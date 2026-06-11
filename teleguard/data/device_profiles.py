"""
TeleGuard Device Profiles
=========================
Single source of truth for all Android device spoofing data.

All Telethon clients — bot auth, webapp auth, session login, device snooper —
import from here. This keeps device lists consistent and avoids duplicate
"PC 64bit" or outdated device strings across the codebase.

Format used by device_snooper / auth_manager:
    {"device_model": str, "system_version": str, "app_version": str}

Format used by auth_handler / session_login_handler (legacy):
    {"model": str, "system": str, "version": str}

Use get_random_device() for the standard format,
or get_random_device_legacy() for the legacy format.
"""

import random
from typing import Dict, List

APP_VERSION = "10.14.5"
LANG_CODE = "en"
SYSTEM_LANG_CODE = "en-US"

# ─── Master device list ───────────────────────────────────────────────────────
# All unique Android devices collected from device_snooper.py, auth_handler.py,
# session_login_handler.py, and backend/auth/telegram_auth_manager.py

ANDROID_DEVICES: List[Dict[str, str]] = [
    # ── Google Pixel ──────────────────────────────────────────────────────────
    {"device_model": "Pixel Fold",    "system_version": "Android 14"},
    {"device_model": "Pixel 8 Pro",   "system_version": "Android 14"},
    {"device_model": "Pixel 8",       "system_version": "Android 14"},
    {"device_model": "Pixel 7 Pro",   "system_version": "Android 14"},
    {"device_model": "Pixel 7",       "system_version": "Android 14"},
    {"device_model": "Pixel 6 Pro",   "system_version": "Android 13"},
    {"device_model": "Pixel 6",       "system_version": "Android 13"},
    {"device_model": "Pixel 5",       "system_version": "Android 12"},
    {"device_model": "Pixel 4a",      "system_version": "Android 12"},
    {"device_model": "Pixel 4 XL",    "system_version": "Android 11"},
    {"device_model": "Pixel 4",       "system_version": "Android 11"},
    {"device_model": "Pixel 3 XL",    "system_version": "Android 10"},
    {"device_model": "Pixel 3",       "system_version": "Android 10"},

    # ── Samsung Galaxy S ──────────────────────────────────────────────────────
    {"device_model": "Galaxy S24 Ultra", "system_version": "Android 14"},
    {"device_model": "Galaxy S24+",      "system_version": "Android 14"},
    {"device_model": "Galaxy S24",       "system_version": "Android 14"},
    {"device_model": "Galaxy S23 Ultra", "system_version": "Android 13"},
    {"device_model": "Galaxy S23+",      "system_version": "Android 13"},
    {"device_model": "Galaxy S23",       "system_version": "Android 13"},
    {"device_model": "SM-S908B",         "system_version": "Android 13"},
    {"device_model": "SM-S906B",         "system_version": "Android 13"},
    {"device_model": "SM-S901B",         "system_version": "Android 13"},
    {"device_model": "Galaxy S22 Ultra", "system_version": "Android 12"},
    {"device_model": "Galaxy S22+",      "system_version": "Android 12"},
    {"device_model": "Galaxy S22",       "system_version": "Android 12"},
    {"device_model": "SM-G998B",         "system_version": "Android 13"},
    {"device_model": "SM-G996B",         "system_version": "Android 12"},
    {"device_model": "Galaxy S21 Ultra", "system_version": "Android 11"},
    {"device_model": "Galaxy S21+",      "system_version": "Android 11"},
    {"device_model": "Galaxy S21",       "system_version": "Android 11"},
    {"device_model": "SM-G991B",         "system_version": "Android 12"},
    {"device_model": "SM-G981B",         "system_version": "Android 11"},
    {"device_model": "Galaxy S20 Ultra", "system_version": "Android 10"},
    {"device_model": "Galaxy S20+",      "system_version": "Android 10"},
    {"device_model": "Galaxy S20",       "system_version": "Android 10"},
    {"device_model": "Galaxy S10+",      "system_version": "Android 10"},
    {"device_model": "Galaxy S10",       "system_version": "Android 10"},
    {"device_model": "SM-G975F",         "system_version": "Android 11"},
    {"device_model": "SM-G973F",         "system_version": "Android 10"},
    {"device_model": "SM-G980F",         "system_version": "Android 11"},

    # ── Samsung Galaxy Note ───────────────────────────────────────────────────
    {"device_model": "Galaxy Note 20 Ultra", "system_version": "Android 14"},
    {"device_model": "Galaxy Note 20",       "system_version": "Android 14"},
    {"device_model": "SM-N986B",             "system_version": "Android 11"},
    {"device_model": "SM-N981B",             "system_version": "Android 12"},
    {"device_model": "SM-N975F",             "system_version": "Android 10"},

    # ── Samsung Galaxy A ──────────────────────────────────────────────────────
    {"device_model": "Galaxy A54",  "system_version": "Android 14"},
    {"device_model": "Galaxy A34",  "system_version": "Android 14"},
    {"device_model": "Galaxy A24",  "system_version": "Android 14"},
    {"device_model": "Galaxy A14",  "system_version": "Android 14"},
    {"device_model": "SM-A525F",    "system_version": "Android 12"},
    {"device_model": "SM-A715F",    "system_version": "Android 11"},
    {"device_model": "SM-A515F",    "system_version": "Android 11"},
    {"device_model": "SM-A315G",    "system_version": "Android 10"},
    {"device_model": "SM-M515F",    "system_version": "Android 11"},

    # ── Samsung Galaxy Z ──────────────────────────────────────────────────────
    {"device_model": "Galaxy Z Fold 5",  "system_version": "Android 14"},
    {"device_model": "Galaxy Z Flip 5",  "system_version": "Android 14"},
    {"device_model": "Galaxy Z Fold 4",  "system_version": "Android 13"},
    {"device_model": "Galaxy Z Flip 4",  "system_version": "Android 13"},

    # ── OnePlus ───────────────────────────────────────────────────────────────
    {"device_model": "OnePlus Open",     "system_version": "Android 14"},
    {"device_model": "OnePlus 12",       "system_version": "Android 14"},
    {"device_model": "OnePlus 11",       "system_version": "Android 13"},
    {"device_model": "OnePlus 10 Pro",   "system_version": "Android 12"},
    {"device_model": "OnePlus 10T",      "system_version": "Android 12"},
    {"device_model": "OnePlus 9 Pro",    "system_version": "Android 11"},
    {"device_model": "OnePlus 9",        "system_version": "Android 11"},
    {"device_model": "OnePlus 8 Pro",    "system_version": "Android 11"},
    {"device_model": "OnePlus 8",        "system_version": "Android 11"},
    {"device_model": "OnePlus 8T",       "system_version": "Android 11"},
    {"device_model": "OnePlus 7T Pro",   "system_version": "Android 10"},
    {"device_model": "OnePlus 7T",       "system_version": "Android 10"},
    {"device_model": "OnePlus Nord 3",   "system_version": "Android 13"},
    {"device_model": "OnePlus Nord CE 3","system_version": "Android 13"},
    {"device_model": "OnePlus Nord 2",   "system_version": "Android 12"},
    {"device_model": "OnePlus Nord",     "system_version": "Android 11"},
    {"device_model": "OnePlus Nord CE",  "system_version": "Android 11"},

    # ── Xiaomi ────────────────────────────────────────────────────────────────
    {"device_model": "Xiaomi 14",         "system_version": "Android 14"},
    {"device_model": "Xiaomi 13 Pro",     "system_version": "Android 13"},
    {"device_model": "Xiaomi 13",         "system_version": "Android 13"},
    {"device_model": "Xiaomi 12 Pro",     "system_version": "Android 12"},
    {"device_model": "Xiaomi 12",         "system_version": "Android 12"},
    {"device_model": "Xiaomi Mi 12",      "system_version": "Android 12"},
    {"device_model": "Xiaomi Mi 11",      "system_version": "Android 11"},
    {"device_model": "Xiaomi Mi 10",      "system_version": "Android 10"},
    {"device_model": "Xiaomi Mix Fold 3", "system_version": "Android 13"},

    # ── Redmi ─────────────────────────────────────────────────────────────────
    {"device_model": "Redmi Note 13 Pro", "system_version": "Android 13"},
    {"device_model": "Redmi Note 12 Pro", "system_version": "Android 12"},
    {"device_model": "Redmi Note 11 Pro", "system_version": "Android 11"},
    {"device_model": "Redmi Note 10 Pro", "system_version": "Android 11"},
    {"device_model": "Xiaomi Redmi Note 12", "system_version": "Android 12"},
    {"device_model": "Xiaomi Redmi Note 11", "system_version": "Android 11"},
    {"device_model": "Xiaomi Redmi Note 10", "system_version": "Android 11"},
    {"device_model": "Xiaomi Redmi Note 9",  "system_version": "Android 10"},
    {"device_model": "Redmi K70",         "system_version": "Android 13"},

    # ── POCO ──────────────────────────────────────────────────────────────────
    {"device_model": "POCO F5 Pro",  "system_version": "Android 13"},
    {"device_model": "POCO F4 GT",   "system_version": "Android 12"},
    {"device_model": "POCO F3",      "system_version": "Android 11"},
    {"device_model": "POCO F2 Pro",  "system_version": "Android 10"},
    {"device_model": "POCO X5 Pro",  "system_version": "Android 12"},
    {"device_model": "Xiaomi POCO F3", "system_version": "Android 11"},
    {"device_model": "Xiaomi POCO X3", "system_version": "Android 10"},
    {"device_model": "Xiaomi Black Shark 4", "system_version": "Android 11"},

    # ── Oppo ──────────────────────────────────────────────────────────────────
    {"device_model": "Oppo Find N3",     "system_version": "Android 14"},
    {"device_model": "Oppo Find X6 Pro", "system_version": "Android 14"},
    {"device_model": "Oppo Find X5 Pro", "system_version": "Android 14"},
    {"device_model": "Oppo Find X3",     "system_version": "Android 11"},
    {"device_model": "Oppo Reno 10 Pro", "system_version": "Android 14"},
    {"device_model": "Oppo A98",         "system_version": "Android 14"},
    {"device_model": "Oppo A78",         "system_version": "Android 14"},

    # ── Vivo ──────────────────────────────────────────────────────────────────
    {"device_model": "Vivo X100 Pro", "system_version": "Android 14"},
    {"device_model": "Vivo X90 Pro",  "system_version": "Android 14"},
    {"device_model": "Vivo X60 Pro",  "system_version": "Android 11"},
    {"device_model": "Vivo V29 Pro",  "system_version": "Android 14"},
    {"device_model": "Vivo Y100",     "system_version": "Android 14"},
    {"device_model": "Vivo T2 Pro",   "system_version": "Android 14"},
    {"device_model": "vivo V2135",    "system_version": "Android 13"},

    # ── Realme ────────────────────────────────────────────────────────────────
    {"device_model": "Realme GT 5",        "system_version": "Android 14"},
    {"device_model": "Realme GT Neo 5",    "system_version": "Android 14"},
    {"device_model": "Realme GT",          "system_version": "Android 11"},
    {"device_model": "Realme 11 Pro+",     "system_version": "Android 14"},
    {"device_model": "Realme C55",         "system_version": "Android 14"},
    {"device_model": "Realme Narzo 60 Pro","system_version": "Android 14"},

    # ── Huawei ────────────────────────────────────────────────────────────────
    {"device_model": "Huawei P60 Pro",    "system_version": "Android 14"},
    {"device_model": "Huawei Mate 50 Pro","system_version": "Android 14"},
    {"device_model": "Huawei Nova 11",    "system_version": "Android 14"},
    {"device_model": "Huawei P40 Pro",    "system_version": "Android 10"},

    # ── Honor ─────────────────────────────────────────────────────────────────
    {"device_model": "Honor Magic 5 Pro", "system_version": "Android 14"},
    {"device_model": "Honor Magic Vs",    "system_version": "Android 13"},
    {"device_model": "Honor 90",          "system_version": "Android 14"},
    {"device_model": "Honor X50",         "system_version": "Android 14"},

    # ── Nothing ───────────────────────────────────────────────────────────────
    {"device_model": "Nothing Phone 2", "system_version": "Android 14"},
    {"device_model": "Nothing Phone 1", "system_version": "Android 14"},

    # ── Motorola ──────────────────────────────────────────────────────────────
    {"device_model": "Motorola Edge 40 Pro", "system_version": "Android 14"},
    {"device_model": "Motorola G84",         "system_version": "Android 14"},
    {"device_model": "Motorola Edge 30",     "system_version": "Android 14"},

    # ── Sony ──────────────────────────────────────────────────────────────────
    {"device_model": "Sony Xperia 1 V",  "system_version": "Android 14"},
    {"device_model": "Sony Xperia 5 V",  "system_version": "Android 14"},
    {"device_model": "Sony Xperia 10 V", "system_version": "Android 14"},

    # ── Asus ──────────────────────────────────────────────────────────────────
    {"device_model": "Asus ROG Phone 7", "system_version": "Android 14"},
    {"device_model": "Asus Zenfone 10",  "system_version": "Android 14"},
    {"device_model": "Asus ROG Phone 6", "system_version": "Android 14"},

    # ── Fairphone ─────────────────────────────────────────────────────────────
    {"device_model": "Fairphone 5", "system_version": "Android 13"},
    {"device_model": "Fairphone 4", "system_version": "Android 13"},

    # ── TCL ───────────────────────────────────────────────────────────────────
    {"device_model": "TCL 40 SE",  "system_version": "Android 13"},
    {"device_model": "TCL 30 5G",  "system_version": "Android 12"},

    # ── Nokia ─────────────────────────────────────────────────────────────────
    {"device_model": "Nokia G60", "system_version": "Android 12"},
    {"device_model": "Nokia X30",  "system_version": "Android 12"},
]


def get_random_device() -> Dict[str, str]:
    """
    Return a random Android device profile in Telethon TelegramClient format.
    Use when creating clients: TelegramClient(..., **get_random_device())
    """
    d = random.choice(ANDROID_DEVICES)
    return {
        "device_model":    d["device_model"],
        "system_version":  d["system_version"],
        "app_version":     APP_VERSION,
        "lang_code":       LANG_CODE,
        "system_lang_code": SYSTEM_LANG_CODE,
    }


def get_random_device_legacy() -> Dict[str, str]:
    """
    Return a random device in the legacy format used by auth_handler/session_login_handler:
    {"model": ..., "system": ..., "version": ...}
    """
    d = random.choice(ANDROID_DEVICES)
    return {
        "model":   d["device_model"],
        "system":  d["system_version"],
        "version": APP_VERSION,
    }


def get_spoofed_device_params() -> Dict[str, str]:
    """Alias for get_random_device() — used by DeviceSnooper.get_spoofed_device_params()."""
    return get_random_device()
