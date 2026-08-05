"""栄養バランスをMatplotlibで可視化する。"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.figure import Figure
from matplotlib.font_manager import FontProperties

from cafeteria_app.config import NUTRIENT_COLS, NUTRIENT_LABELS
from cafeteria_app.optimizer import PriceComparisonResult


@lru_cache(maxsize=1)
def get_japanese_font() -> FontProperties:
    """実行環境で利用できる日本語フォントを返す。

    Windowsでは標準搭載のメイリオ・游ゴシックを優先し、Linuxや
    CodespacesではNoto Sans CJK JPなどを探す。見つからない場合は
    Matplotlibの既定フォントを返す。
    """
    windows_dir = Path(os.environ.get("WINDIR", r"C:\Windows"))
    font_files = [
        windows_dir / "Fonts" / "meiryo.ttc",
        windows_dir / "Fonts" / "YuGothM.ttc",
        windows_dir / "Fonts" / "msgothic.ttc",
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"),
        Path("/usr/share/fonts/truetype/fonts-japanese-gothic.ttf"),
    ]

    for font_file in font_files:
        if not font_file.exists():
            continue
        try:
            font_manager.fontManager.addfont(str(font_file))
            return FontProperties(fname=str(font_file))
        except (OSError, RuntimeError, ValueError):
            continue

    font_names = [
        "Meiryo",
        "Yu Gothic",
        "YuGothic",
        "Noto Sans CJK JP",
        "IPAexGothic",
        "IPAGothic",
        "TakaoGothic",
    ]
    for font_name in font_names:
        try:
            font_path = font_manager.findfont(
                FontProperties(family=font_name),
                fallback_to_default=False,
            )
            return FontProperties(fname=font_path)
        except ValueError:
            continue

    return FontProperties()


def make_balance_figure(
    total: dict[str, float],
    target: dict[str, float],
    title: str,
) -> Figure:
    """目標値に対する達成率を棒グラフで表示する。"""
    rate = [100 * total[col] / max(target[col], 1e-9) for col in NUTRIENT_COLS]
    labels = [NUTRIENT_LABELS[col].split(" [")[0] for col in NUTRIENT_COLS]
    font_prop = get_japanese_font()

    fig, ax = plt.subplots(figsize=(9, 4.8))
    x = list(range(len(labels)))
    ax.bar(x, rate)
    ax.axhline(100, linestyle="--", label="目標 100%")
    ax.set_xticks(x, labels, rotation=35, ha="right", fontproperties=font_prop)
    ax.set_ylabel("達成率 [%]", fontproperties=font_prop)
    ax.set_title(title, fontproperties=font_prop)
    ax.tick_params(axis="y", labelsize=10)

    for tick_label in ax.get_yticklabels():
        tick_label.set_fontproperties(font_prop)

    ax.legend(prop=font_prop)
    fig.tight_layout()
    return fig


def make_price_comparison_figure(
    result_data: list[PriceComparisonResult],
    title: str,
) -> Figure:
    """価格上限ごとの栄養評価値と予算の余裕を2段の図で表示する。"""
    if not result_data:
        raise ValueError("比較結果が空です")

    font_prop = get_japanese_font()
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

    ax = axes[0]
    ax.plot(xpos, scores, marker="o")
    ax.set_xticks(xpos, price_labels, fontproperties=font_prop)
    ax.set_ylabel(
        "栄養評価値（小さいほど目標に近い）",
        fontproperties=font_prop,
    )
    ax.set_title(title, fontproperties=font_prop)
    ax.grid(axis="y", alpha=0.3)

    for i, score in enumerate(scores):
        ax.annotate(
            f"{score:.3f}",
            (i, score),
            xytext=(0, 7),
            textcoords="offset points",
            ha="center",
            fontsize=8,
            fontproperties=font_prop,
        )

    ax = axes[1]
    ax.bar(xpos, prices, label="実際の提案価格")
    ax.bar(xpos, margins, bottom=prices, label="価格上限までの余裕")
    ax.set_xticks(xpos, price_labels, fontproperties=font_prop)
    ax.set_xlabel("設定した上限価格 [円]", fontproperties=font_prop)
    ax.set_ylabel("価格 [円]", fontproperties=font_prop)
    ax.grid(axis="y", alpha=0.3)
    ax.legend(prop=font_prop)

    for i, (price, margin) in enumerate(zip(prices, margins, strict=True)):
        ax.text(
            i,
            price - 12,
            f"{price:.0f}円",
            ha="center",
            va="top",
            fontsize=8,
            fontproperties=font_prop,
        )
        if margin > 0:
            ax.text(
                i,
                price + margin / 2,
                f"余裕{margin:.0f}円",
                ha="center",
                va="center",
                fontsize=7,
                fontproperties=font_prop,
            )

    for ax in axes:
        for tick_label in [*ax.get_xticklabels(), *ax.get_yticklabels()]:
            tick_label.set_fontproperties(font_prop)

    fig.tight_layout()
    return fig
