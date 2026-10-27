"""
成長実験用の NotebookLM プロンプト生成

jpx_growth_filter.py の出力（growth_filtered_output.csv）から、Pick=Y の銘柄だけを取り出し、
NotebookLM に貼り付ける「URL一覧」と「選定基準つきプロンプト」を作ります。

使い方:
  python makeprompt_growth.py growth_filtered_output.csv [出力ファイル名]
"""
import sys

import pandas as pd


def fmt_pct(v):
    return f"{v:.2%}" if pd.notna(v) else "不明"


def fmt_ratio(v):
    return f"{v:.2f}" if pd.notna(v) else "不明"


def generate_prompt(csv_file, output_file="growth_prompt_output.txt"):
    try:
        df = pd.read_csv(csv_file)
    except pd.errors.EmptyDataError:
        print("CSVにデータがありません。処理を終了します。")
        return

    if "Pick" not in df.columns:
        print("Pick 列がありません。jpx_growth_filter.py の出力を指定してください。")
        return

    df_pick = df[df["Pick"] == "Y"].copy()
    if df_pick.empty:
        print("Pick=Y の銘柄がありません。処理を終了します。")
        return

    df_pick = df_pick.sort_values("SectorJP")

    # URL リスト（Yahoo!ファイナンス：業績・企業情報・配当・ニュース）
    url_list = []
    for _, row in df_pick.iterrows():
        sym = row["Symbol"]
        url_list.append(
            f"https://finance.yahoo.co.jp/quote/{sym}/financials\n"
            f"https://finance.yahoo.co.jp/quote/{sym}/profile\n"
            f"https://finance.yahoo.co.jp/quote/{sym}/dividend\n"
            f"https://finance.yahoo.co.jp/quote/{sym}/news\n"
        )
    urls_text = "\n".join(url_list)

    # 銘柄一覧（セクター・利回り・割安度・分割の有無つき）
    company_list = []
    for _, row in df_pick.iterrows():
        split = "／直近1年に株式分割あり" if row.get("SplitFlag") == "Split" else ""
        company_list.append(
            f"{row['Symbol']}（{row['SectorJP']} / 利回り: {fmt_pct(row['DividendYield'])}"
            f" / 2年平均利回り: {fmt_pct(row.get('AvgYield2Y'))}"
            f" / 割安度: {fmt_ratio(row.get('Valuation'))} / 株価: {row['CurrentPrice']}円{split}）"
        )
    companies_text = "\n".join(company_list)

    prompt = f"""
以下の銘柄について、URL 一覧を NotebookLM に貼り付けて解析してください。
（抽出条件：Pick=Y、{len(df_pick)}銘柄）

対象銘柄一覧（セクター順）：
{companies_text}

参照する URL 一覧：
{urls_text}

NotebookLM に問い合わせるプロンプト：

これは、低配当・財務健全・成長重視の銘柄を、2年程度の中期でキャピタルゲインを狙って少額で買う実験の、最終判定です（配当を目的とした高配当株の判定ではありません）。
各銘柄について、参照した資料（URL）に書かれている情報だけを根拠に、次の選定基準で評価してください。
資料に書かれていないことは推測せず、「不明」と書いてください。

【選定基準】
① 今後の成長見込み：売上・利益の成長が今後も続く根拠があるか（事業の強み、市場の成長、業績予想）
② 株価が安くなっている理由：現在の株価が平均より割安に見えるため、その理由が次の「悪い理由」でないか
　・減配、配当方針の後退
　・業績の悪化、成長の鈍化、業績予想の下方修正
　・財務の悪化、不祥事、事業の構造的な問題
　※ 市場全体の下落や、一時的な要因（為替、特殊要因など）による株価の下落は、問題なしとしてください
③ 財務の健全性：自己資本比率、営業キャッシュフロー、有利子負債の状況
④ 配当：減配がないか、配当を続ける余力があるか
　※ 直近1年に株式分割があった銘柄は、分割の前後で配当や利回りの基準がずれて、実際より高く見えることがあります。分割の影響を調整して確認してください

【出力形式】（銘柄ごと）
【銘柄コード】
・セクター
・成長見込み：◎〇△×（根拠を一言）
・株価が安い理由：（資料から読み取れる範囲で）
・その理由は悪い理由か：〇（問題なし）／×（悪い理由）／不明
・財務健全性：◎〇△×
・減配・配当方針の懸念：なし／あり（内容）
・最終判定：買い／見送り（理由を一言）

最後に、「買い」と判定した銘柄の【証券コードのみ】を一覧で出力してください。
※ 判定は参考情報です。最終的な売買の判断は、自分で資料を確認して行います。
"""

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(prompt)

    print(f"プロンプトを {output_file} に保存しました（UTF-8）")


if __name__ == "__main__":
    csv_file = sys.argv[1] if len(sys.argv) > 1 else "growth_filtered_output.csv"
    out_file = sys.argv[2] if len(sys.argv) > 2 else "growth_prompt_output.txt"
    generate_prompt(csv_file, out_file)
