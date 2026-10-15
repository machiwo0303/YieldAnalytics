import pandas as pd
import sys

def generate_prompt(csv_file, target_count=None, output_file="prompt_output.txt"):
    df = pd.read_csv(csv_file)

    # MonthlyPick 列が Y の銘柄だけ（今月の買い時）
    if "MonthlyPick" not in df.columns:
        print("MonthlyPick 列がありません。新しい yield_filtered_output.csv を指定してください。")
        return

    df_pick = df[df["MonthlyPick"] == "Y"].copy()

    # Y が1件もない場合は終了
    if df_pick.empty:
        print("MonthlyPick=Y の銘柄がありません。処理を終了します。")
        return

    # 件数を指定した場合のみ、CSVの並び順（優先度順）で上位だけ使う
    selected = df_pick if target_count is None else df_pick.head(target_count)

    df_selected = selected.copy()

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
（抽出条件：MonthlyPick=Y、{len(df_selected)}銘柄）

対象銘柄一覧（セクター順）：
{companies_text}

参照する URL 一覧：
{urls_text}

NotebookLM に問い合わせるプロンプト：

各銘柄について以下を出力し、長期投資の観点から総合分析してください。
（景気敏感だからと減点は不要です）

除外判断は以下の順番で行ってください：
① 長期投資の観点から今後の成長が見込みにくい企業は除外する
② 最新の年間配当予想が、前期の年間配当実績と比較して「1円でも減少（減配）」している企業は、今後大きな成長が見込めない場合は除外する
③ 利回りが3%以下の企業は、今後大きな成長が見込めない場合のみ除外する  
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
　
次に、portfolio_result_all.csv の現在所有の評価額（＝現在株価 × 現在保有株数）に対して、 まず各銘柄について「10000円分の買い足し（11000円までは許容）」を基本としつつ、 以下の評価ランク別の上限額になるように買い足し数量を調整してください。
● 評価A：買い足し後の評価額が 100,000円以内（105,000円までは許容） ● 評価B：買い足し後の評価額が 60,000円以内（62,000円までは許容） ● 評価C：買い足し後の評価額が 20,000円以内（11,000円までは許容）
※買い足し数量（株数）は、上記の**「追加購入10,000円（最大11,000円）」と「買い足し後評価額の上限（許容値含む）」のどちらも超えない最大の整数（小数点切り捨て）**としてください。 ※売却は不要のため、現在評価額がすでに上限を超えている場合は買い足し数量を0とし、マイナス調整は行わない
最後に、
除外されず「買い」と判断した銘柄の【証券コードのみ】と、
今回計算した「買い足し数量 × 現在株価」の合計金額（＝今回購入する合計金額）を一覧でまとめて出力してください。

また、Excelの項目書き出し用に証券コードを下記のように表形式に出力もお願いします。
※数量0の場合は出力不要

|証券コード|買い足し数量|明日の日付|
"""

    # 保存
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(prompt)

    print(f"プロンプトを {output_file} に保存しました（UTF-8）")

if __name__ == "__main__":
    csv_file = sys.argv[1]
    # 銘柄数の指定は任意（省略時は MonthlyPick=Y をすべて対象にする）
    target_count = int(sys.argv[2]) if len(sys.argv) > 2 else None
    print(generate_prompt(csv_file, target_count))
