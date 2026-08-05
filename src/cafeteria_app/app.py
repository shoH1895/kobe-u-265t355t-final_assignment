"""Streamlitによる画面表示。"""

from __future__ import annotations

import io
from pathlib import Path

import pandas as pd
import streamlit as st
from matplotlib.figure import Figure

from cafeteria_app.chart import make_balance_figure, make_price_comparison_figure
from cafeteria_app.config import (
    DEFAULT_BREAKFAST_RATE,
    DEFAULT_DAILY_TARGET,
    DEFAULT_LUNCH_RATE,
    DINNER_FILE,
    NUTRIENT_COLS,
    NUTRIENT_LABELS,
)
from cafeteria_app.optimizer import (
    calc_remaining_target,
    calc_total_nutrition,
    compare_lunch_price_ranges,
    search_best_dinner,
    search_best_lunch,
)
from cafeteria_app.scraper import fetch_menu_data


@st.cache_data(ttl=1800, show_spinner=False)
def load_live_menu() -> tuple[pd.DataFrame, str]:
    """メニューデータを読み込み、30分間キャッシュする。"""
    return fetch_menu_data()


def load_dinner_data(file_path: Path = DINNER_FILE) -> pd.DataFrame:
    """夕食候補CSVを読み込む。"""
    return pd.read_csv(file_path)


def show_target_input() -> dict[str, float]:
    """サイドバーに目標栄養量の入力欄を表示する。"""
    st.sidebar.header("1日の目標値")
    ans: dict[str, float] = {}
    for col in NUTRIENT_COLS:
        ans[col] = float(
            st.sidebar.number_input(
                NUTRIENT_LABELS[col],
                min_value=0.1,
                value=float(DEFAULT_DAILY_TARGET[col]),
                step=1.0,
            )
        )
    return ans


def show_total_table(total: dict[str, float], target: dict[str, float]) -> None:
    rows = []
    for col in NUTRIENT_COLS:
        rows.append(
            {
                "栄養素": NUTRIENT_LABELS[col],
                "合計": round(total[col], 2),
                "目標": round(target[col], 2),
                "達成率[%]": round(100 * total[col] / max(target[col], 1e-9), 1),
            }
        )
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)


def show_pdf_download(fig: Figure, file_name: str) -> None:
    buf = io.BytesIO()
    fig.savefig(buf, format="pdf", bbox_inches="tight")
    st.download_button(
        "グラフをPDFで保存",
        data=buf.getvalue(),
        file_name=file_name,
        mime="application/pdf",
    )


def show_lunch_mode(menu_data: pd.DataFrame, daily_target: dict[str, float]) -> None:
    st.header("昼ご飯を食べる前：おすすめ組み合わせ")
    st.write("その日のおすすめメニューを必ず1品含む組み合わせを探索します。")

    col1, col2, col3 = st.columns(3)
    with col1:
        price_min = int(
            st.number_input("最低金額 [円]", min_value=0, value=400, step=50)
        )
    with col2:
        price_max = int(
            st.number_input("最高金額 [円]", min_value=0, value=700, step=50)
        )
    with col3:
        price_step = int(
            st.number_input(
                "比較する価格間隔 [円]",
                min_value=50,
                value=50,
                step=50,
            )
        )

    lunch_rate = st.slider("昼食に割り当てる目標割合", 0.25, 0.50, DEFAULT_LUNCH_RATE, 0.05)
    lunch_target = {col: daily_target[col] * lunch_rate for col in NUTRIENT_COLS}

    recommended = menu_data[menu_data["is_recommended"] == True]["name"].tolist()  # noqa: E712
    if not recommended:
        st.warning("おすすめメニューを取得できなかったため、先頭メニューを候補にします。")
        recommended = menu_data["name"].head(4).tolist()

    if st.button("昼食候補を計算", type="primary"):
        if price_min > price_max:
            st.error("最高金額は最低金額以上にしてください。")
            return

        comparison_count = (price_max - price_min) // price_step + 1
        if comparison_count > 25:
            st.error("比較点が多すぎます。価格間隔を大きくしてください。")
            return

        with st.spinner("昼食候補と価格上限ごとの比較を計算しています..."):
            for recommend_name in recommended:
                st.subheader(recommend_name)
                ans = search_best_lunch(
                    menu_data,
                    recommend_name,
                    price_min,
                    price_max,
                    lunch_target,
                    top_n=1,
                )
                if not ans:
                    st.info("この価格帯では条件を満たす組み合わせが見つかりませんでした。")
                    continue

                result = ans[0]
                total = result["total"]
                st.write(" ＋ ".join(result["names"]))
                st.write(
                    f"合計金額：{total['price']:.0f}円　"
                    f"評価値：{result['score']:.3f}"
                )
                show_total_table(total, lunch_target)
                fig = make_balance_figure(
                    total,
                    lunch_target,
                    f"昼食の栄養バランス：{recommend_name}",
                )
                st.pyplot(fig)
                show_pdf_download(fig, f"lunch_{recommend_name}.pdf")

                comparison = compare_lunch_price_ranges(
                    menu_data=menu_data,
                    recommended_name=recommend_name,
                    price_min=price_min,
                    price_max=price_max,
                    price_step=price_step,
                    target=lunch_target,
                )

                if comparison:
                    with st.expander("価格上限ごとの提案比較", expanded=True):
                        st.caption(
                            "最低金額を固定し、上限金額を段階的に変更した結果です。"
                            "栄養評価値は小さいほど目標値に近く、改善率は最初に"
                            "候補が見つかった価格上限を基準にしています。"
                        )
                        comparison_rows = [
                            {
                                "上限価格 [円]": item["price_max"],
                                "提案メニュー": " ＋ ".join(item["names"]),
                                "実価格 [円]": round(item["price"]),
                                "予算の余裕 [円]": round(item["margin"]),
                                "栄養評価値": round(item["score"], 3),
                                "基準からの改善率 [%]": round(
                                    item["improvement_rate"],
                                    1,
                                ),
                            }
                            for item in comparison
                        ]
                        st.dataframe(
                            pd.DataFrame(comparison_rows),
                            hide_index=True,
                            use_container_width=True,
                        )

                        comparison_fig = make_price_comparison_figure(
                            comparison,
                            f"価格上限別の提案比較：{recommend_name}",
                        )
                        st.pyplot(comparison_fig)
                        show_pdf_download(
                            comparison_fig,
                            f"price_comparison_{recommend_name}.pdf",
                        )

                st.divider()


def show_dinner_mode(menu_data: pd.DataFrame, daily_target: dict[str, float]) -> None:
    st.header("昼ご飯を食べた後：晩ご飯の提案")

    menu_names = menu_data["name"].tolist()
    selected_names = st.multiselect("昼に食べたメニューを選択", menu_names)
    st.caption("選択した料理は横並びで表示されます。")
    if selected_names:
        st.info(" ＋ ".join(selected_names))

    breakfast_rate = st.slider(
        "朝食で摂取済みと仮定する割合",
        0.0,
        0.40,
        DEFAULT_BREAKFAST_RATE,
        0.05,
    )
    dinner_price_max = int(
        st.number_input("晩ご飯の上限金額 [円]", min_value=0, value=1000, step=50)
    )

    if st.button("晩ご飯候補を計算", type="primary"):
        if not selected_names:
            st.error("昼に食べたメニューを1つ以上選択してください。")
            return

        selected_lunch = menu_data[menu_data["name"].isin(selected_names)]
        lunch_total = calc_total_nutrition(selected_lunch)
        dinner_target = calc_remaining_target(daily_target, lunch_total, breakfast_rate)
        dinner_data = load_dinner_data()
        ans = search_best_dinner(dinner_data, dinner_target, dinner_price_max, top_n=3)

        st.subheader("昼食の合計")
        show_total_table(lunch_total, daily_target)

        st.subheader("おすすめ晩ご飯")
        if not ans:
            st.warning("条件を満たす晩ご飯候補がありません。上限金額を上げてください。")
            return

        breakfast_total = {col: daily_target[col] * breakfast_rate for col in NUTRIENT_COLS}
        for i, result in enumerate(ans, start=1):
            total = result["total"]
            st.markdown(f"### 第{i}候補")
            st.write(" ＋ ".join(result["names"]))
            st.write(f"合計金額：{total['price']:.0f}円　評価値：{result['score']:.3f}")

            daily_total = {
                col: breakfast_total[col] + lunch_total[col] + total[col]
                for col in NUTRIENT_COLS
            }
            show_total_table(daily_total, daily_target)
            fig = make_balance_figure(daily_total, daily_target, f"1日の予測栄養バランス：第{i}候補")
            st.pyplot(fig)
            show_pdf_download(fig, f"dinner_candidate_{i}.pdf")


def main() -> None:
    st.set_page_config(page_title="学食栄養管理アプリ", layout="wide")
    st.title("学食メニュー栄養管理・食事提案アプリ")
    st.caption("栄養値は食事選びの参考情報です。医療・栄養指導を目的とするものではありません。")

    if st.sidebar.button("学食メニューを再取得"):
        load_live_menu.clear()

    daily_target = show_target_input()

    try:
        with st.spinner("学食サイトからメニューを取得しています..."):
            menu_data, message = load_live_menu()
        st.success(message)
    except RuntimeError as exc:
        st.error(str(exc))
        st.stop()

    with st.expander("取得したメニューを確認"):
        show_cols = ["name", "category", "price", *NUTRIENT_COLS, "is_recommended"]
        st.dataframe(menu_data[show_cols], hide_index=True, use_container_width=True)

    if "mode" not in st.session_state:
        st.session_state.mode = "未選択"

    if st.session_state.mode == "未選択":
        st.subheader("今日の昼ご飯をすでに食べましたか？")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("まだ食べていない", use_container_width=True):
                st.session_state.mode = "食べる前"
                st.rerun()
        with col2:
            if st.button("すでに食べた", use_container_width=True):
                st.session_state.mode = "食べた後"
                st.rerun()
        return

    if st.button("最初の選択に戻る"):
        st.session_state.mode = "未選択"
        st.rerun()

    if st.session_state.mode == "食べる前":
        show_lunch_mode(menu_data, daily_target)
    else:
        show_dinner_mode(menu_data, daily_target)


if __name__ == "__main__":
    main()
