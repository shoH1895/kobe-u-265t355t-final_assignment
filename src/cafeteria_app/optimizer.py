"""昼食・夕食の組み合わせ探索と栄養評価を行う。"""

from __future__ import annotations

from itertools import combinations, product
from typing import Iterable, TypedDict

import pandas as pd

from cafeteria_app.config import NUTRIENT_COLS, SCORE_WEIGHTS


class MenuResult(TypedDict):
    """組み合わせ探索結果。"""

    names: list[str]
    total: dict[str, float]
    score: float


class PriceComparisonResult(TypedDict):
    """価格上限ごとの昼食候補の比較結果。"""

    price_max: int
    names: list[str]
    price: float
    margin: float
    score: float
    improvement_rate: float


def calc_total_nutrition(menu_data: pd.DataFrame) -> dict[str, float]:
    """選択されたメニューの価格と栄養価を合計する。"""
    ans = {col: float(menu_data[col].sum()) for col in NUTRIENT_COLS}
    ans["price"] = float(menu_data["price"].sum())
    return ans


def calc_nutrition_score(
    total: dict[str, float],
    target: dict[str, float],
) -> float:
    """目標栄養量との差を無次元化し、重み付き誤差を計算する。

    脂質と食塩は、目標値を超えた場合の罰則を大きくする。
    """
    score = 0.0
    upper_limit_cols = {"fat", "salt"}

    for col in NUTRIENT_COLS:
        target_val = max(float(target[col]), 1e-9)
        diff_rate = (float(total[col]) - target_val) / target_val
        weight = SCORE_WEIGHTS[col]

        if col in upper_limit_cols and diff_rate <= 0:
            score += weight * 0.25 * diff_rate**2
        elif col in upper_limit_cols:
            score += weight * 4.0 * diff_rate**2
        else:
            score += weight * diff_rate**2

    return float(score)


def _valid_lunch_combination(menu_data: pd.DataFrame) -> bool:
    """昼食として成立するカテゴリ構成かを判定する。

    主菜を選ぶ場合はライスなどの主食を必須とする。丼・カレー、麺類、
    バランスセットは単独で主食を含む料理として扱い、別の主食や主菜とは
    組み合わせない。
    """
    category_count = menu_data["category"].value_counts().to_dict()

    main_count = category_count.get("主菜", 0)
    staple_count = category_count.get("主食", 0)
    bowl_count = category_count.get("丼・カレー", 0)
    noodle_count = category_count.get("麺類", 0)
    balance_count = category_count.get("バランスセット", 0)

    if main_count > 1 or staple_count > 1:
        return False
    if bowl_count > 1 or noodle_count > 1 or balance_count > 1:
        return False

    complete_count = main_count + bowl_count + noodle_count + balance_count
    if complete_count != 1:
        return False

    if main_count == 1:
        return staple_count == 1

    # 丼・カレー、麺類、バランスセットには別の主食・主菜を付けない。
    return staple_count == 0 and main_count == 0


def search_best_lunch(
    menu_data: pd.DataFrame,
    recommended_name: str,
    price_min: int,
    price_max: int,
    target: dict[str, float],
    top_n: int = 3,
    max_extra_items: int = 3,
) -> list[MenuResult]:
    """指定されたおすすめメニューを必ず含む昼食候補を探索する。"""
    anchor = menu_data[menu_data["name"] == recommended_name]
    if anchor.empty:
        return []

    # 探索数を抑えるため、追加候補は価格が高すぎないものを優先して最大30件に絞る。
    extra_menu = menu_data[menu_data["name"] != recommended_name].copy()
    extra_menu = extra_menu[extra_menu["price"] <= price_max]
    extra_menu = extra_menu.sort_values(["category", "price"]).head(30)

    ans: list[MenuResult] = []
    anchor_index = int(anchor.index[0])
    extra_indices = [int(i) for i in extra_menu.index]

    for n_extra in range(max_extra_items + 1):
        for extra_index in combinations(extra_indices, n_extra):
            selected_index = [anchor_index, *extra_index]
            selected = menu_data.loc[selected_index]

            if not _valid_lunch_combination(selected):
                continue

            total = calc_total_nutrition(selected)
            if not (price_min <= total["price"] <= price_max):
                continue

            score = calc_nutrition_score(total, target)
            ans.append(
                {
                    "names": selected["name"].tolist(),
                    "total": total,
                    "score": score,
                }
            )

    ans.sort(key=lambda x: float(x["score"]))
    return ans[:top_n]


def compare_lunch_price_ranges(
    menu_data: pd.DataFrame,
    recommended_name: str,
    price_min: int,
    price_max: int,
    price_step: int,
    target: dict[str, float],
) -> list[PriceComparisonResult]:
    """価格上限を段階的に変え、各上限での最良候補を比較する。

    最低金額は固定し、上限金額だけを ``price_step`` 円ずつ増やす。
    条件を満たす候補が存在しない上限金額は結果から除外する。
    """
    if price_min > price_max:
        return []
    if price_step <= 0:
        raise ValueError("price_stepは1以上にしてください")

    price_limits = list(range(price_min, price_max + 1, price_step))
    if not price_limits or price_limits[-1] != price_max:
        price_limits.append(price_max)

    ans: list[PriceComparisonResult] = []
    for limit in price_limits:
        result = search_best_lunch(
            menu_data=menu_data,
            recommended_name=recommended_name,
            price_min=price_min,
            price_max=limit,
            target=target,
            top_n=1,
        )
        if not result:
            continue

        best = result[0]
        price = float(best["total"]["price"])
        ans.append(
            {
                "price_max": int(limit),
                "names": best["names"],
                "price": price,
                "margin": float(limit - price),
                "score": float(best["score"]),
                "improvement_rate": 0.0,
            }
        )

    if not ans:
        return ans

    base_score = float(ans[0]["score"])
    for result in ans:
        if base_score <= 1e-12:
            result["improvement_rate"] = 0.0
        else:
            result["improvement_rate"] = float(
                100 * (base_score - float(result["score"])) / base_score
            )

    return ans


def calc_remaining_target(
    daily_target: dict[str, float],
    lunch_total: dict[str, float],
    breakfast_rate: float,
) -> dict[str, float]:
    """朝食分を仮定し、夕食で補いたい栄養量を計算する。"""
    ans: dict[str, float] = {}
    for col in NUTRIENT_COLS:
        breakfast = daily_target[col] * breakfast_rate
        ans[col] = max(daily_target[col] - breakfast - lunch_total[col], 0.0)
    return ans


def _to_result(menu_data: pd.DataFrame, target: dict[str, float]) -> MenuResult:
    total = calc_total_nutrition(menu_data)
    return {
        "names": menu_data["name"].tolist(),
        "total": total,
        "score": calc_nutrition_score(total, target),
    }


def search_best_dinner(
    dinner_data: pd.DataFrame,
    target: dict[str, float],
    price_max: int = 1200,
    top_n: int = 3,
) -> list[MenuResult]:
    """主食・主菜・副菜を各1品含む夕食候補を全探索する。"""
    rice = dinner_data[dinner_data["category"] == "主食"]
    main = dinner_data[dinner_data["category"] == "主菜"]
    side = dinner_data[dinner_data["category"] == "副菜"]
    soup = dinner_data[dinner_data["category"] == "汁物"]

    ans: list[MenuResult] = []
    soup_options: Iterable[int | None] = [None, *[int(i) for i in soup.index]]

    for rice_i, main_i, side_i, soup_i in product(
        [int(i) for i in rice.index],
        [int(i) for i in main.index],
        [int(i) for i in side.index],
        soup_options,
    ):
        selected_index = [rice_i, main_i, side_i]
        if soup_i is not None:
            selected_index.append(soup_i)

        selected = dinner_data.loc[selected_index]
        if float(selected["price"].sum()) > price_max:
            continue

        ans.append(_to_result(selected, target))

    ans.sort(key=lambda x: float(x["score"]))
    return ans[:top_n]
