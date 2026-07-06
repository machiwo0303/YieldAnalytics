import pandas as pd
import random
import sys

def generate_prompt(csv_file, max_total, output_file="prompt_output.txt"):
    df = pd.read_csv(csv_file)

    # ☆ の銘柄だけ
    df_star = df[df["BuySignal"] == "☆"].copy()

    # ランダム順に並べ替え
    df_star = df_star.sample(frac=1).reset_index(drop=True)

    selected = []
    total_cost = 0

    # 1銘柄ずつ追加し、合計金額が max_total を超えたらストップ
    for _, row in df_star.iterrows():
        price = row["CurrentPrice"]

        if total_cost + price > max_total:
            break

        selected.append(row)
        total_cost += price

        if len(selected) >= 17:
            break

    df_selected = pd.DataFrame(selected)

    # セクター順に並び替え
    df_selected = df_selected.sort_values("SectorJP")

    # URL リスト
    url_list = []
    for _, row in df_selected.iterrows():
        sym = row["Symbol"]
        url_list.append(
            f"https://finance.yahoo.co.jp/quote/{sym}/financials\n"
            f"https://finance.yahoo.co.jp/quote/{sym}/profile\n"
            f"https://finance.yahoo.co.jp/quote/{sym}/dividend\n"
        )
    urls_text = "\n".join(url_list)

    # 会社情報（セクター・利回り付き）
    company_list = []
    for _, row in df_selected.iterrows():
        company_list.append(
            f"{row['Symbol']}（{row['SectorJP']} / 利回り: {row['DividendYield']:.2%} / 株価: {row['CurrentPrice']}円）"
        )
    companies_text = "\n".join(company_list)

    # NotebookLM に渡すプロンプト
    prompt = f"""
以下の銘柄について、URL 一覧を NotebookLM に貼り付けて解析してください。
（抽出条件：BuySignal=☆、合計金額 ≤ {max_total}円、最大25銘柄）

最終的な合計金額：{total_cost}円

対象銘柄一覧（セクター順）：
{companies_text}

参照する URL 一覧：
{urls_text}

NotebookLM に問い合わせるプロンプト：

各銘柄について以下を出力し、長期投資の観点から総合分析してください。
（景気敏感だからと減点は不要です）

除外判断は以下の順番で行ってください：
① 長期投資の観点から今後の成長が見込みにくい企業は除外する  
② 利回りが3%以下の企業は、今後大きな成長が見込めない場合のみ除外する  
※除外した場合は、銘柄名と除外理由を必ず記載してください

【銘柄コード】
・セクター
・景気敏感株か：〇×
　※景気敏感株＝売上・利益が景気循環に連動しやすい業種（例：自動車、資本財、素材など）
・財務健全性：◎〇△×
・事業の強み：
・事業の弱み：
・増配力：〇△×
・累進配当を掲げているか：◎〇△×
・政策との相性：
・グローバル展開：
・10年以上保有の適性（成長性）：
・総合評価（A〜C）：
　※A＝長期投資に非常に適する、C＝長期投資にギリギリ適する

最後に、除外されず「買い」と判断した銘柄の【証券コードのみ】と今時点の合計金額を一覧でまとめて出力してください。

また、Excelの項目書き出し用に証券コードを下記のように表形式に出力もお願いします。
|証券コード|数量（常に1）|明日の日付|
"""

    # 保存
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(prompt)

    print(f"プロンプトを {output_file} に保存しました（UTF-8）")

if __name__ == "__main__":
    csv_file = sys.argv[1]
    max_total = int(sys.argv[2])  # ← 合計金額パラメータ
    print(generate_prompt(csv_file, max_total))
