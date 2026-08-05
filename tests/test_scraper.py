from pathlib import Path

from cafeteria_app.scraper import extract_detail_links, parse_detail_html


def test_extract_detail_links() -> None:
    html = '<a href="detail.php?c=1&t=2">A</a><a href="detail.php?c=1&t=2">A</a>'
    ans = extract_detail_links(html, "https://example.com/sp/")
    assert ans == ["https://example.com/sp/detail.php?c=1&t=2"]


def test_parse_detail_html() -> None:
    html = Path("tests/fixtures/detail.html").read_text(encoding="utf-8")
    ans = parse_detail_html(html, "https://example.com/detail.php", True)

    assert ans["name"] == "豚肉の生姜焼き"
    assert ans["price"] == 341
    assert ans["energy"] == 246.0
    assert ans["protein"] == 20.0
    assert ans["category"] == "主菜"
    assert ans["is_recommended"] is True


def test_parse_detail_html_uses_given_category() -> None:
    html = Path("tests/fixtures/detail.html").read_text(encoding="utf-8")
    ans = parse_detail_html(
        html,
        "https://example.com/detail.php",
        False,
        "副菜",
    )

    assert ans["category"] == "副菜"


def test_merge_standard_menu_adds_rice_and_miso_soup() -> None:
    import pandas as pd

    from cafeteria_app.scraper import merge_standard_menu

    live_data = pd.DataFrame(
        [
            {
                "name": "おすすめ主菜",
                "category": "主菜",
                "price": 300,
                "energy": 250,
                "protein": 20,
                "fat": 10,
                "carbohydrate": 15,
                "salt": 1.0,
                "calcium": 40,
                "vegetable": 50,
                "iron": 1.0,
                "is_recommended": True,
                "detail_url": "https://example.com/main",
                "updated_at": "2026-08-04",
            }
        ]
    )

    ans, added_count = merge_standard_menu(live_data)
    names = set(ans["name"])

    assert "ライス（小）" in names
    assert "味噌汁" in names
    assert added_count >= 2


def test_standard_noodles_are_loaded_in_summer() -> None:
    from cafeteria_app.scraper import load_standard_menu

    menu_data = load_standard_menu(month=8)
    names = set(menu_data["name"])

    assert "かけうどん" in names
    assert "かけそば" in names
    assert "温玉ぶっかけうどん" in names
    assert "冷やしうどん" in names
    assert "冷やしそば" in names


def test_cold_noodles_are_hidden_outside_summer() -> None:
    from cafeteria_app.scraper import load_standard_menu

    menu_data = load_standard_menu(month=1)
    names = set(menu_data["name"])

    assert "かけうどん" in names
    assert "かけそば" in names
    assert "温玉ぶっかけうどん" in names
    assert "冷やしうどん" not in names
    assert "冷やしそば" not in names
