"""Matplotlib charts for nutrition and price comparison.

Chart text is intentionally written in ASCII/English so that the figures render
correctly even in Linux/Codespaces environments without Japanese fonts.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
from matplotlib.figure import Figure

from cafeteria_app.config import NUTRIENT_COLS
from cafeteria_app.optimizer import PriceComparisonResult


CHART_LABELS = {
    "energy": "Energy",
    "protein": "Protein",
    "fat": "Fat",
    "carbohydrate": "Carbs",
    "salt": "Salt",
    "calcium": "Calcium",
    "vegetable": "Vegetables",
    "iron": "Iron",
}


def make_balance_figure(
    total: dict[str, float],
    target: dict[str, float],
    title: str,
) -> Figure:
    """Plot nutrient achievement rates against the target values.

    The ``title`` argument is retained for API compatibility, but an English
    title is used to avoid missing-glyph problems in environments without a
    Japanese font.
    """
    del title

    rates = [100 * total[col] / max(target[col], 1e-9) for col in NUTRIENT_COLS]
    labels = [CHART_LABELS[col] for col in NUTRIENT_COLS]

    fig, ax = plt.subplots(figsize=(9, 4.8))
    x = list(range(len(labels)))
    ax.bar(x, rates)
    ax.axhline(100, linestyle="--", label="Target 100%")
    ax.set_xticks(x, labels, rotation=35, ha="right")
    ax.set_ylabel("Achievement rate [%]")
    ax.set_title("Nutrient achievement rate")
    ax.legend()
    fig.tight_layout()
    return fig


def make_price_comparison_figure(
    result_data: list[PriceComparisonResult],
    title: str,
) -> Figure:
    """Plot nutrition score and remaining budget for each price limit."""
    del title

    if not result_data:
        raise ValueError("comparison result is empty")

    xpos = list(range(len(result_data)))
    price_labels = [str(result["price_max"]) for result in result_data]
    scores = [float(result["score"]) for result in result_data]
    prices = [float(result["price"]) for result in result_data]
    margins = [float(result["margin"]) for result in result_data]

    fig, axes = plt.subplots(
        2,
        1,
        figsize=(9, 6.5),
        gridspec_kw={"height_ratios": [1.1, 1.0]},
    )

    upper = axes[0]
    upper.plot(xpos, scores, marker="o")
    upper.set_xticks(xpos, price_labels)
    upper.set_ylabel("Nutrition score\n(lower is better)")
    upper.set_title("Recommendation comparison by price limit")
    upper.grid(axis="y", alpha=0.3)

    for i, score in enumerate(scores):
        upper.annotate(
            f"{score:.3f}",
            (i, score),
            xytext=(0, 7),
            textcoords="offset points",
            ha="center",
            fontsize=8,
        )

    lower = axes[1]
    lower.bar(xpos, prices, label="Recommended meal price")
    lower.bar(xpos, margins, bottom=prices, label="Remaining budget")
    lower.set_xticks(xpos, price_labels)
    lower.set_xlabel("Price limit [JPY]")
    lower.set_ylabel("Price [JPY]")
    lower.grid(axis="y", alpha=0.3)
    lower.legend()

    for i, (price, margin) in enumerate(zip(prices, margins, strict=True)):
        lower.text(
            i,
            price - 12,
            f"JPY {price:.0f}",
            ha="center",
            va="top",
            fontsize=8,
        )
        if margin > 0:
            lower.text(
                i,
                price + margin / 2,
                f"+{margin:.0f}",
                ha="center",
                va="center",
                fontsize=7,
            )

    fig.tight_layout()
    return fig
