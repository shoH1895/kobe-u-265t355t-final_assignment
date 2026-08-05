import warnings

from cafeteria_app.chart import make_balance_figure, make_price_comparison_figure
from cafeteria_app.config import DEFAULT_DAILY_TARGET


def test_japanese_chart_has_no_missing_glyph_warning() -> None:
    total = DEFAULT_DAILY_TARGET.copy()

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        fig = make_balance_figure(total, DEFAULT_DAILY_TARGET, "栄養バランス")
        fig.canvas.draw()

    messages = [str(item.message) for item in caught]
    assert not any("Glyph" in message and "missing" in message for message in messages)

def test_price_comparison_chart_has_no_missing_glyph_warning() -> None:
    result_data = [
        {
            "price_max": 500,
            "names": ["主菜", "ライス"],
            "price": 480.0,
            "margin": 20.0,
            "score": 2.0,
            "improvement_rate": 0.0,
        },
        {
            "price_max": 600,
            "names": ["主菜", "ライス", "副菜"],
            "price": 580.0,
            "margin": 20.0,
            "score": 1.4,
            "improvement_rate": 30.0,
        },
    ]

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        fig = make_price_comparison_figure(result_data, "価格上限別の提案比較")
        fig.canvas.draw()

    messages = [str(item.message) for item in caught]
    assert not any("Glyph" in message and "missing" in message for message in messages)

