"""アプリ内で使用する目標値と列名を定義する。"""

from __future__ import annotations

from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"
CACHE_FILE = DATA_DIR / "menu_cache.csv"
DINNER_FILE = DATA_DIR / "dinner_menu.csv"
FALLBACK_FILE = DATA_DIR / "fallback_menu.csv"
STANDARD_FILE = DATA_DIR / "standard_menu.csv"

BASE_URL = "https://west2-univ.jp/sp/"
TOP_URL = f"{BASE_URL}index.php?t=677156"
MENU_URL = f"{BASE_URL}menu.php?t=677156"

NUTRIENT_COLS = [
    "energy",
    "protein",
    "fat",
    "carbohydrate",
    "salt",
    "calcium",
    "vegetable",
    "iron",
]

NUTRIENT_LABELS = {
    "energy": "エネルギー [kcal]",
    "protein": "たんぱく質 [g]",
    "fat": "脂質 [g]",
    "carbohydrate": "炭水化物 [g]",
    "salt": "食塩相当量 [g]",
    "calcium": "カルシウム [mg]",
    "vegetable": "野菜量 [g]",
    "iron": "鉄 [mg]",
}

# 本アプリ内の初期値。利用者が画面上で変更できる。
DEFAULT_DAILY_TARGET = {
    "energy": 2200.0,
    "protein": 65.0,
    "fat": 60.0,
    "carbohydrate": 300.0,
    "salt": 7.5,
    "calcium": 700.0,
    "vegetable": 350.0,
    "iron": 10.5,
}

# 昼食は1日目標の約35%を目安とする。
DEFAULT_LUNCH_RATE = 0.35

# 夕食提案では、朝食で1日目標の約25%を摂ったと仮定する。
DEFAULT_BREAKFAST_RATE = 0.25

SCORE_WEIGHTS = {
    "energy": 2.0,
    "protein": 2.5,
    "fat": 1.5,
    "carbohydrate": 1.5,
    "salt": 3.0,
    "calcium": 1.0,
    "vegetable": 2.0,
    "iron": 1.0,
}
