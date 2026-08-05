"""学食Webサイトからメニュー情報を取得する。"""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import cast
from urllib.parse import urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup, Tag

from cafeteria_app.config import (
    CACHE_FILE,
    FALLBACK_FILE,
    MENU_URL,
    NUTRIENT_COLS,
    STANDARD_FILE,
    TOP_URL,
)

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/150 Safari/537.36"
    )
}

CATEGORY_LABELS = [
    "主菜",
    "副菜",
    "麺類",
    "丼・カレー",
    "デザート",
    "バランスセット",
]


def fetch_html(url: str, session: requests.Session | None = None) -> str:
    """URLからHTMLを取得する。"""
    client = session or requests.Session()
    res = client.get(url, headers=REQUEST_HEADERS, timeout=20)
    res.raise_for_status()
    res.encoding = res.apparent_encoding
    return res.text


def extract_detail_links(html: str, base_url: str) -> list[str]:
    """HTML内のdetail.phpへのリンクを重複なしで取り出す。"""
    soup = BeautifulSoup(html, "html.parser")
    links: list[str] = []

    for tag in soup.select('a[href*="detail.php"]'):
        href = tag.get("href")
        if isinstance(href, str):
            links.append(urljoin(base_url, href))

    # JavaScriptや属性内に文字列として記載される場合も拾う。
    pattern = r"detail\.php\?[^\"'<>\s]+"
    for href in re.findall(pattern, html):
        href = href.replace("&amp;", "&")
        links.append(urljoin(base_url, href))

    return list(dict.fromkeys(links))


def extract_rendered_menu_info(url: str) -> dict[str, str]:
    """JavaScript実行後の画面から詳細URLとカテゴリを取得する。

    戻り値は ``{詳細URL: カテゴリ}`` の辞書とする。サイト側のDOM構造が
    一部変わった場合でも、各リンクより前に現れるカテゴリ見出しを探す。
    PlaywrightまたはChromiumを利用できない場合は空辞書を返す。
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {}

    script = """
    elements => {
        const labels = ['主菜', '副菜', '麺類', '丼・カレー', 'デザート', 'バランスセット'];
        const allElements = Array.from(document.querySelectorAll('body *'));

        function normalize(text) {
            return (text || '').replace(/\\s+/g, ' ').trim();
        }

        function findCategory(anchor) {
            const index = allElements.indexOf(anchor);
            for (let i = index - 1; i >= 0; i--) {
                const element = allElements[i];
                const text = normalize(element.textContent);

                // 見出し自体、または「主菜 Main dish」のような表記だけを採用する。
                for (const label of labels) {
                    if (text === label || text.startsWith(label + ' ')) {
                        return label;
                    }
                }
            }
            return '';
        }

        return elements.map(anchor => ({
            url: anchor.href,
            category: findCategory(anchor),
        }));
    }
    """

    try:
        with sync_playwright() as play:
            browser = play.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="networkidle", timeout=30_000)
            page.wait_for_timeout(1000)
            items = page.locator('a[href*="detail.php"]').evaluate_all(script)
            browser.close()

        ans: dict[str, str] = {}
        for item in items:
            detail_url = str(item.get("url", ""))
            category = str(item.get("category", ""))
            if detail_url:
                ans[detail_url] = category
        return ans
    except Exception:
        return {}


def extract_rendered_detail_links(url: str) -> list[str]:
    """互換用に、描画後の詳細リンクだけを返す。"""
    return list(extract_rendered_menu_info(url))


def _first_number(text: str) -> float:
    match = re.search(r"-?\d+(?:\.\d+)?", text.replace(",", ""))
    if match is None:
        return 0.0
    return float(match.group())


def _parse_price(text: str, name: str) -> int:
    """複数サイズ表記を含む価格から、料理名に対応する価格を選ぶ。"""
    size_patterns = {
        "小": r"小\s*(\d+)円",
        "中": r"中\s*(\d+)円",
        "大": r"大\s*(\d+)円",
    }
    for size, pattern in size_patterns.items():
        if size in name:
            match = re.search(pattern, text)
            if match is not None:
                return int(match.group(1))

    match = re.search(r"(\d+)\s*円", text.replace(",", ""))
    if match is None:
        return 0
    return int(match.group(1))


def _find_menu_title(soup: BeautifulSoup) -> Tag:
    """店舗名ではなく、栄養情報の直前にある料理名の見出しを返す。"""
    price_text = soup.find(string=re.compile(r"組価\s*\(税込\)|Price\s*\(incl\.\s*tax\)"))
    if price_text is not None and price_text.parent is not None:
        title = price_text.parent.find_previous("h1")
        if isinstance(title, Tag):
            return title

    titles = soup.find_all("h1")
    if titles:
        return titles[-1]

    raise ValueError("メニュー名を取得できませんでした")


def _extract_japanese_name(title: Tag) -> str:
    """料理名見出しから日本語名を取り出す。"""
    title_parts = list(title.stripped_strings)
    if len(title_parts) >= 2:
        return title_parts[0]

    title_text = title.get_text(" ", strip=True)

    # 英訳が別要素になっていない場合は、最初の英字の直前までを日本語名とする。
    match = re.match(r"(.+?)(?=[A-Za-z])", title_text)
    if match is not None:
        name = match.group(1).strip()
        if name:
            return name

    return title_text


def _find_value_text(soup: BeautifulSoup, label_pattern: str) -> str:
    """ラベルを含む要素全体の文字列を返す。"""
    label = soup.find(string=re.compile(label_pattern))
    if label is None:
        return ""

    parent = label.parent
    if isinstance(parent, Tag):
        # 多くの場合、ラベルと数値は同じli要素内にある。
        item = parent.find_parent("li")
        if isinstance(item, Tag):
            return item.get_text(" ", strip=True)
        return parent.get_text(" ", strip=True)

    return str(label)


def infer_category(name: str, price: int, energy: float) -> str:
    """料理名と栄養価からカテゴリを補完する。"""
    if "バランス" in name:
        return "バランスセット"
    if any(word in name for word in ["丼", "カレー", "ハヤシ"]):
        return "丼・カレー"
    if any(word in name for word in ["麺", "うどん", "そば", "ラーメン", "パスタ"]):
        return "麺類"
    if any(word in name for word in ["ライス", "ごはん", "ご飯", "パン"]):
        return "主食"
    if any(word in name for word in ["汁", "スープ", "シチュー"]):
        return "汁物"
    if any(word in name for word in ["プリン", "ゼリー", "ヨーグルト", "ケーキ", "デザート"]):
        return "デザート"
    if price <= 180 or energy <= 180:
        return "副菜"
    return "主菜"


def parse_detail_html(
    html: str,
    detail_url: str = "",
    is_recommended: bool = False,
    category: str = "",
) -> dict[str, object]:
    """メニュー詳細ページのHTMLを1行分の辞書へ変換する。"""
    soup = BeautifulSoup(html, "html.parser")
    title = _find_menu_title(soup)
    name = _extract_japanese_name(title)

    nutrient_labels = {
        "energy": r"エネルギー|Energy",
        "protein": r"タンパク質|Protein",
        "fat": r"脂質|Fat",
        "carbohydrate": r"炭水化物|Carbohydrates",
        "salt": r"食塩相当量|Salt",
        "calcium": r"カルシウム|Calcium",
        "vegetable": r"野菜量|Veg",
        "iron": r"鉄|Iron",
    }

    price_text = _find_value_text(soup, r"組価\s*\(税込\)|Price\s*\(incl\.\s*tax\)")
    price = _parse_price(price_text, name)

    row: dict[str, object] = {
        "name": name,
        "price": price,
        "category": category,
        "is_recommended": is_recommended,
        "detail_url": detail_url,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }

    for col, label_pattern in nutrient_labels.items():
        value_text = _find_value_text(soup, label_pattern)
        row[col] = _first_number(value_text)

    if not category:
        energy = float(cast(float, row["energy"]))
        row["category"] = infer_category(name, price, energy)

    return row


def _fetch_one_detail(
    url: str,
    recommended_links: set[str],
    category_map: dict[str, str],
) -> dict[str, object]:
    html = fetch_html(url)
    category = category_map.get(url, "")
    return parse_detail_html(html, url, url in recommended_links, category)


def save_menu_cache(menu_data: pd.DataFrame, cache_file: Path = CACHE_FILE) -> None:
    """取得済みデータをCSVに保存する。"""
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    menu_data.to_csv(cache_file, index=False, encoding="utf-8-sig")


def load_menu_cache(cache_file: Path = CACHE_FILE) -> pd.DataFrame:
    """前回取得したキャッシュを読み込む。"""
    if not cache_file.exists():
        return pd.DataFrame()
    return pd.read_csv(cache_file)


def load_fallback_menu(file_path: Path = FALLBACK_FILE) -> pd.DataFrame:
    """リポジトリに同梱した最低限の予備データを読み込む。"""
    if not file_path.exists():
        return pd.DataFrame()
    return pd.read_csv(file_path)




def _is_available_in_month(season: object, month: int) -> bool:
    """季節区分から、指定月に提供する定番メニューかを判定する。"""
    season_name = str(season).strip().lower()

    if season_name in {"", "nan", "all", "通年"}:
        return True
    if season_name in {"summer", "夏"}:
        return month in {6, 7, 8, 9}

    return True


def load_standard_menu(
    file_path: Path = STANDARD_FILE,
    month: int | None = None,
) -> pd.DataFrame:
    """Webサイトに常時表示されない定番メニューを読み込む。

    ``season`` が ``summer`` の商品は6月から9月だけ読み込む。
    ``month`` はテスト用に指定でき、省略時は実行時の月を使う。
    """
    if not file_path.exists():
        return pd.DataFrame()

    standard_data = pd.read_csv(file_path)
    current_month = datetime.now().month if month is None else month

    if "season" in standard_data.columns:
        valid_row = standard_data["season"].map(
            lambda season: _is_available_in_month(season, current_month)
        )
        standard_data = standard_data[valid_row].copy()
        standard_data = standard_data.drop(columns="season")

    return standard_data


def merge_standard_menu(
    menu_data: pd.DataFrame,
    month: int | None = None,
) -> tuple[pd.DataFrame, int]:
    """取得メニューへライス・麺類などの定番メニューを追加する。

    同名の商品がWebサイト側から取得できた場合は、Webサイトの値を優先する。
    夏季商品の混入を防ぐため、キャッシュ内の補完商品を一度除いてから、
    実行月に提供する商品だけを追加する。
    戻り値の2要素目は、実際に追加された件数とする。
    """
    if not STANDARD_FILE.exists():
        return menu_data.copy(), 0

    all_standard_data = pd.read_csv(STANDARD_FILE)
    standard_data = load_standard_menu(STANDARD_FILE, month)
    if standard_data.empty:
        return menu_data.copy(), 0

    all_standard_names = set(all_standard_data["name"].astype(str))
    name_data = menu_data.get("name", pd.Series("", index=menu_data.index)).astype(str)
    detail_url = menu_data.get(
        "detail_url",
        pd.Series("", index=menu_data.index),
    ).astype(str)

    # Web取得値は west2-univ.jp のURLを持つ。補完データだけを取り除く。
    cached_standard = name_data.isin(all_standard_names) & ~detail_url.str.contains(
        "west2-univ.jp",
        na=False,
    )
    live_data = menu_data.loc[~cached_standard].copy()

    before_names = set(live_data.get("name", pd.Series(dtype=str)).astype(str))
    ans = pd.concat([live_data, standard_data], ignore_index=True, sort=False)
    ans = ans.drop_duplicates(subset="name", keep="first")

    for col in ["price", *NUTRIENT_COLS]:
        ans[col] = pd.to_numeric(ans[col], errors="coerce").fillna(0)

    ans["is_recommended"] = ans["is_recommended"].fillna(False).astype(bool)
    ans = ans.sort_values(
        ["is_recommended", "category", "name"],
        ascending=[False, True, True],
    ).reset_index(drop=True)

    added_count = len(set(ans["name"].astype(str)) - before_names)
    return ans, added_count


def fetch_menu_data(max_items: int = 100) -> tuple[pd.DataFrame, str]:
    """おすすめと全メニューを取得する。"""
    try:
        with requests.Session() as session:
            top_html = fetch_html(TOP_URL, session)
            menu_html = fetch_html(MENU_URL, session)

        recommended_links = set(extract_detail_links(top_html, TOP_URL))
        menu_links = extract_detail_links(menu_html, MENU_URL)

        # 描画後のDOMからURLと実際のカテゴリ見出しを取得する。
        category_map = extract_rendered_menu_info(MENU_URL)
        rendered_links = list(category_map)
        menu_links = list(dict.fromkeys([*menu_links, *rendered_links]))

        all_links = list(dict.fromkeys([*recommended_links, *menu_links]))[:max_items]

        if not all_links:
            raise ValueError("メニュー詳細ページへのリンクが見つかりませんでした")

        rows: list[dict[str, object]] = []
        with ThreadPoolExecutor(max_workers=8) as executor:
            future_map = {
                executor.submit(
                    _fetch_one_detail,
                    url,
                    recommended_links,
                    category_map,
                ): url
                for url in all_links
            }
            for future in as_completed(future_map):
                try:
                    rows.append(future.result())
                except (requests.RequestException, ValueError):
                    continue

        if not rows:
            raise ValueError("メニュー詳細情報を取得できませんでした")

        menu_data = pd.DataFrame(rows)
        for col in ["price", *NUTRIENT_COLS]:
            menu_data[col] = pd.to_numeric(menu_data[col], errors="coerce").fillna(0)

        menu_data = menu_data.drop_duplicates(subset="detail_url")
        live_count = len(menu_data)
        menu_data, added_count = merge_standard_menu(menu_data)
        save_menu_cache(menu_data)
        return (
            menu_data,
            f"Webサイトから{live_count}件を取得し、定番メニューを{added_count}件追加しました",
        )

    except (requests.RequestException, ValueError) as exc:
        cache_data = load_menu_cache()
        if not cache_data.empty:
            cache_data, _ = merge_standard_menu(cache_data)
            return cache_data, f"更新に失敗したため前回データを使用します: {exc}"

        fallback_data = load_fallback_menu()
        if not fallback_data.empty:
            fallback_data, _ = merge_standard_menu(fallback_data)
            return fallback_data, f"更新に失敗したため同梱の予備データを使用します: {exc}"

        raise RuntimeError(f"メニューデータを取得できませんでした: {exc}") from exc
