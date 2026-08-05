"""価格上限と昼食提案結果の関係を検証し、レポート用の図を作成する。"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib import font_manager
import pandas as pd

REPORT_DIR = Path(__file__).resolve().parent
ROOT_DIR = REPORT_DIR.parent
SRC_DIR = ROOT_DIR / "src"
sys.path.insert(0, str(SRC_DIR))

from cafeteria_app.config import DEFAULT_DAILY_TARGET, DEFAULT_LUNCH_RATE
from cafeteria_app.optimizer import search_best_lunch


def set_japanese_font() -> None:
    """利用可能な日本語フォントをMatplotlibへ設定する。"""
    font_candidates = [
        "Noto Sans CJK JP",
        "Noto Sans JP",
        "Yu Gothic",
        "Meiryo",
        "MS Gothic",
    ]
    available = {font.name for font in font_manager.fontManager.ttflist}

    for font_name in font_candidates:
        if font_name in available:
            plt.rcParams["font.family"] = font_name
            break

    plt.rcParams["axes.unicode_minus"] = False


def make_verification_data() -> pd.DataFrame:
    """価格上限ごとの最良候補、実価格、余裕、評価値を計算する。"""
    fallback = pd.read_csv(ROOT_DIR / "data" / "fallback_menu.csv")
    standard = pd.read_csv(
        ROOT_DIR / "data" / "standard_menu.csv",
        encoding="utf-8-sig",
    )
    menu_data = pd.concat([fallback, standard], ignore_index=True)
    lunch_target = {
        col: value * DEFAULT_LUNCH_RATE
        for col, value in DEFAULT_DAILY_TARGET.items()
    }

    ans: list[dict[str, object]] = []
    for price_max in [500, 550, 600, 650, 700]:
        result = search_best_lunch(
            menu_data=menu_data,
            recommended_name="豚肉の生姜焼き",
            price_min=400,
            price_max=price_max,
            target=lunch_target,
            top_n=1,
        )[0]
        price = int(round(result["total"]["price"]))
        ans.append(
            {
                "price_max": price_max,
                "price": price,
                "margin": price_max - price,
                "score": float(result["score"]),
                "menu": "＋".join(result["names"]),
            }
        )

    return pd.DataFrame(ans)


def save_figure(result_data: pd.DataFrame) -> None:
    """検証結果を2段のグラフとしてPDFへ保存する。"""
    set_japanese_font()
    xpos = list(range(len(result_data)))

    fig, axes = plt.subplots(
        2,
        1,
        figsize=(7.2, 5.2),
        gridspec_kw={"height_ratios": [1.15, 1.0]},
    )

    ax = axes[0]
    ax.plot(xpos, result_data["score"], marker="o")
    ax.set_xticks(xpos, [str(value) for value in result_data["price_max"]])
    ax.set_ylabel("栄養評価値 S\n（小さいほど目標に近い）")
    ax.set_title("価格上限を変えたときの提案結果")
    ax.grid(axis="y", alpha=0.3)

    for i, row in result_data.iterrows():
        ax.annotate(
            f"{row['score']:.3f}",
            (i, row["score"]),
            xytext=(0, 7),
            textcoords="offset points",
            ha="center",
            fontsize=8,
        )

    ax = axes[1]
    ax.bar(xpos, result_data["price"], label="実際の提案価格")
    ax.bar(
        xpos,
        result_data["margin"],
        bottom=result_data["price"],
        label="価格上限までの余裕",
    )
    ax.set_xticks(xpos, [str(value) for value in result_data["price_max"]])
    ax.set_xlabel("設定した上限価格 [円]")
    ax.set_ylabel("価格 [円]")
    ax.legend(loc="upper left", ncols=2, fontsize=8)
    ax.grid(axis="y", alpha=0.3)

    for i, row in result_data.iterrows():
        ax.text(
            i,
            row["price"] - 18,
            f"{int(row['price'])}円",
            ha="center",
            va="top",
            fontsize=8,
        )
        ax.text(
            i,
            row["price"] + row["margin"] / 2,
            f"余裕{int(row['margin'])}円",
            ha="center",
            va="center",
            fontsize=7,
        )

    fig.tight_layout()
    fig.savefig(REPORT_DIR / "price_range_verification.pdf", bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    """検証データとレポート用の図を作成する。"""
    result_data = make_verification_data()
    result_data.to_csv(
        REPORT_DIR / "price_range_verification.csv",
        index=False,
        encoding="utf-8-sig",
    )
    save_figure(result_data)


if __name__ == "__main__":
    main()
