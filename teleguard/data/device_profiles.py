"""
TeleGuard Device Profiles
=========================
Single source of truth for Android device spoofing.

Every Telethon client created in TeleGuard (bot auth, webapp auth, session
import) calls get_random_device() from here.  Keeping it in one place means:
  - No more "PC 64bit" login notifications
  - Consistent device fingerprint across all code paths
  - Easy to update when new flagship devices release

Usage
-----
Standard (Telethon keyword args):
    from teleguard.data.device_profiles import get_random_device
    client = TelegramClient(session, api_id, api_hash, **get_random_device())

Legacy (model/system/version dict):
    from teleguard.data.device_profiles import get_random_device_legacy
    d = get_random_device_legacy()
    client = TelegramClient(session, api_id, api_hash,
                            device_model=d["model"],
                            system_version=d["system"],
                            app_version=d["version"])
"""

import random
from typing import Dict, List, Tuple

APP_VERSION   = "10.14.5"
LANG_CODE     = "en"
SYSTEM_LANG   = "en-US"

# ─── Device pool ─────────────────────────────────────────────────────────────
# Format: (device_model, system_version, weight)
# Weight controls how often a device is picked — flagship 2023/2024 models
# are weighted higher because they're the most common in the real world.
# This makes sessions look natural instead of always using the same device.

_DEVICES: List[Tuple[str, str, int]] = [
    # ── Google Pixel ─────────────────────────────────────── weight
    ("Pixel 9 Pro",          "Android 15",  6),
    ("Pixel 9",              "Android 15",  6),
    ("Pixel 8 Pro",          "Android 14",  8),
    ("Pixel 8",              "Android 14",  8),
    ("Pixel Fold",           "Android 14",  3),
    ("Pixel 7 Pro",          "Android 14",  6),
    ("Pixel 7",              "Android 14",  6),
    ("Pixel 6 Pro",          "Android 13",  4),
    ("Pixel 6",              "Android 13",  4),
    ("Pixel 5",              "Android 12",  3),
    ("Pixel 4a",             "Android 12",  2),
    ("Pixel 4 XL",           "Android 11",  2),
    ("Pixel 4",              "Android 11",  2),

    # ── Samsung Galaxy S ─────────────────────────────────
    ("Galaxy S25 Ultra",     "Android 15",  7),
    ("Galaxy S25+",          "Android 15",  6),
    ("Galaxy S25",           "Android 15",  6),
    ("Galaxy S24 Ultra",     "Android 14",  8),
    ("Galaxy S24+",          "Android 14",  7),
    ("Galaxy S24",           "Android 14",  7),
    ("Galaxy S23 Ultra",     "Android 13",  6),
    ("Galaxy S23+",          "Android 13",  5),
    ("Galaxy S23",           "Android 13",  5),
    ("SM-S908B",             "Android 13",  4),
    ("SM-S906B",             "Android 13",  3),
    ("Galaxy S22 Ultra",     "Android 12",  5),
    ("Galaxy S22+",          "Android 12",  4),
    ("Galaxy S22",           "Android 12",  4),
    ("SM-G998B",             "Android 13",  4),
    ("SM-G996B",             "Android 12",  3),
    ("SM-G991B",             "Android 12",  3),
    ("Galaxy S21 Ultra",     "Android 11",  4),
    ("Galaxy S21+",          "Android 11",  3),
    ("Galaxy S21",           "Android 11",  3),
    ("Galaxy S20 Ultra",     "Android 10",  2),
    ("Galaxy S10+",          "Android 10",  2),

    # ── Samsung Galaxy A ─────────────────────────────────
    ("Galaxy A55",           "Android 14",  5),
    ("Galaxy A35",           "Android 14",  5),
    ("Galaxy A54",           "Android 14",  4),
    ("Galaxy A34",           "Android 14",  4),
    ("Galaxy A24",           "Android 13",  3),
    ("Galaxy A14",           "Android 13",  3),
    ("SM-A525F",             "Android 12",  3),
    ("SM-A715F",             "Android 11",  2),

    # ── Samsung Galaxy Z (Fold/Flip) ──────────────────────
    ("Galaxy Z Fold 6",      "Android 14",  4),
    ("Galaxy Z Flip 6",      "Android 14",  4),
    ("Galaxy Z Fold 5",      "Android 13",  3),
    ("Galaxy Z Flip 5",      "Android 13",  3),
    ("Galaxy Z Fold 4",      "Android 12",  2),

    # ── Samsung Galaxy Note ───────────────────────────────
    ("Galaxy Note 20 Ultra", "Android 13",  2),
    ("SM-N986B",             "Android 11",  2),

    # ── OnePlus ───────────────────────────────────────────
    ("OnePlus Open",         "Android 14",  4),
    ("OnePlus 12",           "Android 14",  6),
    ("OnePlus 12R",          "Android 14",  4),
    ("OnePlus 11",           "Android 13",  5),
    ("OnePlus 10 Pro",       "Android 12",  4),
    ("OnePlus 10T",          "Android 12",  3),
    ("OnePlus 9 Pro",        "Android 12",  3),
    ("OnePlus 9",            "Android 11",  3),
    ("OnePlus 8 Pro",        "Android 11",  2),
    ("OnePlus 8T",           "Android 11",  2),
    ("OnePlus Nord 3",       "Android 13",  4),
    ("OnePlus Nord CE 3",    "Android 13",  3),
    ("OnePlus Nord 2",       "Android 12",  2),

    # ── Xiaomi ────────────────────────────────────────────
    ("Xiaomi 14 Ultra",      "Android 14",  6),
    ("Xiaomi 14",            "Android 14",  6),
    ("Xiaomi 13 Ultra",      "Android 13",  5),
    ("Xiaomi 13 Pro",        "Android 13",  5),
    ("Xiaomi 13",            "Android 13",  5),
    ("Xiaomi 12 Pro",        "Android 12",  4),
    ("Xiaomi 12",            "Android 12",  4),
    ("Xiaomi Mi 11",         "Android 11",  3),
    ("Xiaomi Mi 10",         "Android 10",  2),
    ("Xiaomi Mix Fold 3",    "Android 13",  3),

    # ── Redmi ─────────────────────────────────────────────
    ("Redmi Note 13 Pro+",   "Android 13",  5),
    ("Redmi Note 13 Pro",    "Android 13",  5),
    ("Redmi Note 12 Pro",    "Android 12",  4),
    ("Redmi Note 11 Pro",    "Android 11",  3),
    ("Redmi Note 10 Pro",    "Android 11",  3),
    ("Redmi K70 Pro",        "Android 14",  4),
    ("Redmi K70",            "Android 13",  3),

    # ── POCO ──────────────────────────────────────────────
    ("POCO F6 Pro",          "Android 14",  4),
    ("POCO F6",              "Android 14",  4),
    ("POCO F5 Pro",          "Android 13",  4),
    ("POCO F5",              "Android 13",  4),
    ("POCO F4 GT",           "Android 12",  3),
    ("POCO F3",              "Android 11",  3),
    ("POCO X6 Pro",          "Android 14",  4),
    ("POCO X5 Pro",          "Android 12",  3),

    # ── Oppo ──────────────────────────────────────────────
    ("Oppo Find N3 Flip",    "Android 14",  4),
    ("Oppo Find N3",         "Android 14",  4),
    ("Oppo Find X7 Ultra",   "Android 14",  4),
    ("Oppo Find X6 Pro",     "Android 13",  3),
    ("Oppo Find X5 Pro",     "Android 12",  3),
    ("Oppo Reno 11 Pro",     "Android 14",  4),
    ("Oppo Reno 10 Pro",     "Android 13",  3),

    # ── Vivo ──────────────────────────────────────────────
    ("Vivo X100 Ultra",      "Android 14",  4),
    ("Vivo X100 Pro",        "Android 14",  4),
    ("Vivo X100",            "Android 14",  4),
    ("Vivo X90 Pro",         "Android 13",  3),
    ("Vivo V30 Pro",         "Android 14",  4),
    ("Vivo V29 Pro",         "Android 13",  3),
    ("vivo V2135",           "Android 13",  2),

    # ── Realme ────────────────────────────────────────────
    ("Realme GT 6",          "Android 14",  4),
    ("Realme GT 5 Pro",      "Android 14",  4),
    ("Realme GT 5",          "Android 14",  3),
    ("Realme GT Neo 6",      "Android 14",  3),
    ("Realme 12 Pro+",       "Android 14",  4),
    ("Realme 11 Pro+",       "Android 13",  3),

    # ── Huawei ────────────────────────────────────────────
    ("Huawei Pura 70 Pro",   "Android 14",  3),
    ("Huawei P60 Pro",       "Android 13",  3),
    ("Huawei Mate 60 Pro",   "Android 13",  3),
    ("Huawei Mate 50 Pro",   "Android 12",  2),
    ("Huawei P40 Pro",       "Android 10",  2),

    # ── Honor ─────────────────────────────────────────────
    ("Honor Magic 6 Pro",    "Android 14",  4),
    ("Honor Magic 5 Pro",    "Android 13",  3),
    ("Honor 200 Pro",        "Android 14",  4),
    ("Honor 90",             "Android 13",  3),

    # ── Nothing ───────────────────────────────────────────
    ("Nothing Phone 2a",     "Android 14",  4),
    ("Nothing Phone 2",      "Android 14",  4),
    ("Nothing Phone 1",      "Android 13",  3),

    # ── Motorola ──────────────────────────────────────────
    ("Motorola Edge 50 Pro", "Android 14",  4),
    ("Motorola Edge 40 Pro", "Android 13",  3),
    ("Motorola Razr 50",     "Android 14",  3),

    # ── Sony ──────────────────────────────────────────────
    ("Sony Xperia 1 VI",     "Android 14",  3),
    ("Sony Xperia 5 VI",     "Android 14",  3),
    ("Sony Xperia 1 V",      "Android 13",  2),
    ("Sony Xperia 10 V",     "Android 13",  2),

    # ── Asus ──────────────────────────────────────────────
    ("Asus ROG Phone 8 Pro", "Android 14",  3),
    ("Asus ROG Phone 8",     "Android 14",  3),
    ("Asus Zenfone 11",      "Android 14",  3),
    ("Asus ROG Phone 7",     "Android 13",  2),

    # ── Fairphone / Nokia / TCL ───────────────────────────
    ("Fairphone 5",          "Android 13",  2),
    ("Nokia X30",            "Android 12",  2),
    ("TCL 40 SE",            "Android 13",  2),
]

# Unzip into separate lists + weights for random.choices
_models   = [d[0] for d in _DEVICES]
_versions = [d[1] for d in _DEVICES]
_weights  = [d[2] for d in _DEVICES]


# ─── Public API ──────────────────────────────────────────────────────────────

def get_random_device() -> Dict[str, str]:
    """
    Return a weighted-random Android device in Telethon TelegramClient format.

        client = TelegramClient(session, api_id, api_hash, **get_random_device())

    Flagship 2023/2024 devices are chosen more often, matching real-world
    distribution so sessions look natural.
    """
    idx = random.choices(range(len(_DEVICES)), weights=_weights, k=1)[0]
    return {
        "device_model":     _models[idx],
        "system_version":   _versions[idx],
        "app_version":      APP_VERSION,
        "lang_code":        LANG_CODE,
        "system_lang_code": SYSTEM_LANG,
    }


def get_random_device_legacy() -> Dict[str, str]:
    """
    Return a random device in the legacy {model, system, version} format
    used by auth_handler and session_login_handler.
    """
    idx = random.choices(range(len(_DEVICES)), weights=_weights, k=1)[0]
    return {
        "model":   _models[idx],
        "system":  _versions[idx],
        "version": APP_VERSION,
    }


def get_spoofed_device_params() -> Dict[str, str]:
    """Alias for get_random_device() — called by DeviceSnooper."""
    return get_random_device()


def get_device_for_android_version(min_version: int = 12) -> Dict[str, str]:
    """
    Return a device that runs at least the specified Android major version.
    Useful when you need a modern device for API compatibility.
    """
    candidates = [
        (i, w) for i, (m, v, w) in enumerate(_DEVICES)
        if _parse_android_version(v) >= min_version
    ]
    if not candidates:
        return get_random_device()
    indices, weights = zip(*candidates)
    idx = random.choices(indices, weights=weights, k=1)[0]
    return {
        "device_model":     _models[idx],
        "system_version":   _versions[idx],
        "app_version":      APP_VERSION,
        "lang_code":        LANG_CODE,
        "system_lang_code": SYSTEM_LANG,
    }


def _parse_android_version(system_version: str) -> int:
    """Extract the Android major version number from a version string."""
    try:
        return int(system_version.replace("Android ", "").split(".")[0])
    except (ValueError, AttributeError):
        return 0


# Total device count available for logging/debugging
TOTAL_DEVICES = len(_DEVICES)
