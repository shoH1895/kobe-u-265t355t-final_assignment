# 学食メニュー栄養管理・食事提案アプリ

[![CI](https://github.com/USER_NAME/REPOSITORY_NAME/actions/workflows/ci.yml/badge.svg)](https://github.com/USER_NAME/REPOSITORY_NAME/actions/workflows/ci.yml)

## 目的

神戸大学生協LANS BOX食堂のWebサイトから、起動時にメニュー名・価格・栄養価を取得し、次の2つを行うアプリです。

- 昼食前：その日のおすすめメニューごとに、指定価格帯で栄養バランスが良い組み合わせを提示する
- 昼食後：実際に食べた昼食を入力し、不足しやすい栄養を補う晩ご飯の組み合わせを提示する

栄養値は食事選びの参考情報であり、医療・栄養指導を目的とするものではありません。

## 主な機能

- `requests`と`BeautifulSoup`による学食Webサイトの取得・解析
- JavaScript表示のメニューに対応するための`Playwright`フォールバック
- `pandas.DataFrame`によるメニュー情報の整理
- 組み合わせ全探索と栄養誤差スコアによる候補順位付け
- `Streamlit`による入力画面と結果表示
- `Matplotlib`による栄養達成率グラフと価格上限別の比較グラフ
- PDF形式のベクター画像出力
- `pytest`による単体テストとGitHub ActionsによるCI

## インストール

Python 3.11以上と`uv`を使用します。

```bash
uv sync --dev
uv run playwright install chromium
```

## 実行方法

```bash
uv run cafeteria-app
```

表示されたローカルURLをブラウザで開いてください。Windowsでは、初回に`setup_windows.bat`、2回目以降は`run_app.bat`を実行することもできます。

## 使い方

1. 起動時に「まだ食べていない」または「すでに食べた」を選びます。
2. 昼食前モードでは、最低金額・最高金額・比較間隔を入力して候補を計算します。価格上限ごとの提案メニュー、実価格、予算の余裕、栄養評価値を表とグラフで比較できます。
3. 昼食後モードでは、昼に食べたメニューを複数選択して晩ご飯を計算します。
4. 目標栄養量はサイドバーから変更できます。
5. 表示したグラフはPDF形式で保存できます。

## 開発環境

```bash
uv run pytest -q
uv run mypy src/
```

## データ取得について

Webサイトの構造変更や通信障害がある場合、リアルタイム更新に失敗することがあります。過去に取得した`data/menu_cache.csv`がある場合はそれを使用し、キャッシュもない場合は`data/fallback_menu.csv`の予備データを使用します。

夕食候補は`data/dinner_menu.csv`に保存してあります。料理や栄養値を変更したい場合は、このCSVを編集してください。

## ディレクトリ構成

```text
src/cafeteria_app/
├── app.py          # Streamlit画面
├── chart.py        # Matplotlibグラフ
├── config.py       # 目標値・URL・列名
├── optimizer.py    # 組み合わせ探索
└── scraper.py      # Webサイト取得

data/
└── dinner_menu.csv

tests/
├── test_optimizer.py
└── test_scraper.py
```

## AIの使用

設計、コードのたたき台、テスト項目の整理にOpenAIのChatGPTを使用しました。生成されたコードは、処理を関数単位に分割し、授業で扱ったPython、pandas、Matplotlib、Web API、型ヒント、テスト、CIの内容に合わせて確認・修正しています。

## ライセンス

MIT License

## 定番メニューの補完

学食サイトの当日一覧にライスや味噌汁が表示されない場合があるため、
`data/standard_menu.csv` の定番商品を取得結果へ追加します。
同名の商品をWebサイトから取得できた場合は、Webサイトの値を優先します。

昼食候補のカテゴリ条件は次の通りです。

- 主菜を含む候補には、ライスなどの主食を必ず1品含める
- 丼・カレー、麺類、バランスセットには、別の主食や主菜を追加しない
- 副菜や味噌汁は、価格帯と栄養評価に応じて追加する

## グラフの日本語表示

Windowsではメイリオまたは游ゴシック、LinuxではNoto Sans CJK JPなどを
自動検出してMatplotlibへ設定します。日本語ラベルを画像・PDFの両方で表示できます。

## 麺類の定番メニュー

`data/standard_menu.csv` には、Webサイトの当日一覧に表示されない場合に備え、
次の麺類を定番メニューとして登録しています。

- 通年：かけうどん、かけそば、温玉ぶっかけうどん
- 夏季（6～9月）：冷やしうどん、冷やしそば

CSVの `season` 列が `all` の商品は通年、`summer` の商品は6～9月だけ
アプリへ追加されます。同名の商品をLANS BOX食堂のWebサイトから取得できた場合は、
Webサイト側の価格・栄養価を優先します。
