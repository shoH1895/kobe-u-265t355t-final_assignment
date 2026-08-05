import pandas as pd

from cafeteria_app.optimizer import (
    calc_nutrition_score,
    compare_lunch_price_ranges,
    search_best_dinner,
    search_best_lunch,
)


def make_menu_data() -> pd.DataFrame:
    rows = [
        ["おすすめ主菜", "主菜", 300, 250, 20, 10, 15, 1.0, 40, 50, 1.0, True],
        ["ご飯", "主食", 150, 250, 4, 1, 55, 0.0, 5, 0, 0.2, False],
        ["副菜", "副菜", 100, 60, 3, 1, 8, 0.5, 60, 80, 1.5, False],
        ["みそ汁", "汁物", 60, 40, 2, 1, 5, 1.0, 40, 20, 0.5, False],
    ]
    cols = [
        "name", "category", "price", "energy", "protein", "fat",
        "carbohydrate", "salt", "calcium", "vegetable", "iron",
        "is_recommended",
    ]
    return pd.DataFrame(rows, columns=cols)


def test_closer_total_has_smaller_score() -> None:
    target = {
        "energy": 700, "protein": 25, "fat": 20, "carbohydrate": 90,
        "salt": 2.5, "calcium": 230, "vegetable": 120, "iron": 3.0,
    }
    close = target.copy()
    far = {key: value * 0.2 for key, value in target.items()}
    assert calc_nutrition_score(close, target) < calc_nutrition_score(far, target)


def test_lunch_contains_recommended_and_budget() -> None:
    menu_data = make_menu_data()
    target = {
        "energy": 650, "protein": 25, "fat": 20, "carbohydrate": 85,
        "salt": 2.5, "calcium": 220, "vegetable": 120, "iron": 3.0,
    }
    ans = search_best_lunch(menu_data, "おすすめ主菜", 450, 650, target, top_n=2)
    assert ans
    assert "おすすめ主菜" in ans[0]["names"]
    assert 450 <= ans[0]["total"]["price"] <= 650


def test_dinner_contains_required_categories() -> None:
    dinner_data = pd.read_csv("data/dinner_menu.csv")
    target = {
        "energy": 700, "protein": 30, "fat": 20, "carbohydrate": 90,
        "salt": 2.5, "calcium": 250, "vegetable": 180, "iron": 4.0,
    }
    ans = search_best_dinner(dinner_data, target, price_max=1000, top_n=1)
    assert ans
    selected = dinner_data[dinner_data["name"].isin(ans[0]["names"])]
    assert {"主食", "主菜", "副菜"}.issubset(set(selected["category"]))


def test_main_dish_lunch_always_contains_staple() -> None:
    menu_data = make_menu_data()
    target = {
        "energy": 650, "protein": 25, "fat": 20, "carbohydrate": 85,
        "salt": 2.5, "calcium": 220, "vegetable": 120, "iron": 3.0,
    }
    ans = search_best_lunch(menu_data, "おすすめ主菜", 400, 700, target, top_n=3)
    assert ans
    for result in ans:
        assert "ご飯" in result["names"]

def test_compare_lunch_price_ranges_uses_input_limits() -> None:
    menu_data = make_menu_data()
    target = {
        "energy": 650, "protein": 25, "fat": 20, "carbohydrate": 85,
        "salt": 2.5, "calcium": 220, "vegetable": 120, "iron": 3.0,
    }
    ans = compare_lunch_price_ranges(
        menu_data=menu_data,
        recommended_name="おすすめ主菜",
        price_min=400,
        price_max=575,
        price_step=50,
        target=target,
    )

    assert ans
    assert ans[-1]["price_max"] == 575
    assert ans[0]["improvement_rate"] == 0.0
    for result in ans:
        assert "おすすめ主菜" in result["names"]
        assert result["margin"] == result["price_max"] - result["price"]
        assert result["price"] <= result["price_max"]

