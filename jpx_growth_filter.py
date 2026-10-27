"""
成長実験用の絞り込み（低配当・財務健全・成長重視）

高配当用の jpx_yield_filter.py とは別の流れです。
  入力 : output_financial_dividend_merged.csv（jpx_screening_fetch.py の出力）
  出力 : growth_filtered_output.csv

使い方:
  python jpx_growth_filter.py [yield_max=0.025] [pick_n=3] [list_max=30]
    yield_max : 現在の配当利回りの上限（0.025 = 2.5%未満）
    pick_n    : 「今回の候補」(Pick=Y) の件数
    list_max  : 一覧に残す最大件数

流れ:
  ① ネット接続なしの条件（配当・財務の健全性）で絞る
  ② 残った銘柄だけ、現在の利回りと株式分割の有無を取得して「利回りが低い」ものを残す
  ③ 割安度（Valuation = 現在の利回り ÷ 直近2年の平均利回り）が VALUATION_MIN 以上の銘柄を、
     GrowthScore の高い順に並べ、上位 pick_n 件に Pick=Y
     （GrowthScore = ROE・売上成長・自己資本比率の順位平均は、参考として列に出します）

株式分割（直近1年）があった銘柄について:
  分割の前後で、配当と株価・EPSの基準がずれると、利回りや配当性向が実際より高く見えます。
  そのため、分割があった銘柄は「利回り」「配当性向」の条件で落とさず、SplitFlag=Split を付けて残します
  （高配当側の jpx_yield_filter.py と同じ考え方）。該当した理由は Note 列に書きます。
  最終的に買うかどうかは、Yahoo!ファイナンス等で実際の配当・利回りを確認して決めてください。
"""
import sys

import numpy as np
import pandas as pd
import yfinance as yf

import jpx_yield_filter as yfl  # 利回り・株価・セクター取得、規模区分を流用

# ============================
# 条件（まずはこの値で試し、結果を見て調整してください）
# ============================
PAYOUT_MAX = 0.25                 # 配当性向の上限（直近の完了年の配当 ÷ EPS）
EQUITY_RATIO_MIN = 0.50           # 自己資本比率の下限
ROE_MIN = 0.10                    # ROE の下限
REVENUE_CAGR_MIN = 0.05           # 売上の年平均成長率の下限（取得できた年数で計算）
MARKET_CAP_MIN = 30_000_000_000   # 時価総額の下限（300億円）
PAID_YEARS = 3                    # 直近の完了年のうち、すべて有配であるべき年数
VALUATION_MIN = 1.0               # 今回の候補にする割安度の下限（現在利回り ÷ 直近2年の平均利回り。1.0以上＝平均より割安）


def build_candidates(df):
    """① ネット接続なしで絞る。銘柄ごとに指標を計算して返す。"""
    rows = []
    for symbol, g in df.groupby("Symbol"):
        g = g.sort_values("Year")
        last = g.iloc[-1]

        # 配当：当年は途中なので、完了年（最新年を除く）で見る
        divs = g["Dividend"].fillna(0).tolist()[:-1]
        recent = divs[-PAID_YEARS:]
        if len(recent) < PAID_YEARS or not all(d > 0 for d in recent):
            continue  # 無配の年がある（配当は出している銘柄に限る）

        eps = last["EPS"]
        if pd.isna(eps) or eps <= 0:
            continue
        payout = divs[-1] / eps
        if payout <= 0:
            continue
        # 配当性向が上限を超える銘柄も、ここでは落とさない（株式分割で見かけ上高い可能性があるため）。
        # 分割がなければ、②で除外する。

        # 財務：値のある年だけを使う
        fin = g.dropna(subset=["Revenue"])
        if len(fin) < 3:
            continue
        equity_ratio = fin["EquityRatio"].iloc[-1]
        if pd.isna(equity_ratio) or equity_ratio < EQUITY_RATIO_MIN:
            continue

        ocf = fin["OperatingCF"].tolist()[-3:]
        if any(pd.isna(x) or x <= 0 for x in ocf):
            continue  # 営業CFが直近3期のどれかでマイナス・不明

        roe = last["ROE"]
        if pd.isna(roe) or roe < ROE_MIN:
            continue

        rev = fin["Revenue"].tolist()
        if rev[0] <= 0 or rev[-1] <= 0:
            continue
        cagr = (rev[-1] / rev[0]) ** (1 / (len(rev) - 1)) - 1
        if cagr < REVENUE_CAGR_MIN:
            continue

        market_cap = last["MarketCap"]
        if pd.isna(market_cap) or market_cap < MARKET_CAP_MIN:
            continue

        rows.append({
            "Symbol": symbol,
            "Company": last["Company"],
            "ROE": roe,
            "EquityRatio": equity_ratio,
            "PayoutRatio": payout,
            "PayoutOver": payout > PAYOUT_MAX,
            "RevenueCAGR": cagr,
            "MarketCap": market_cap,
        })
    return pd.DataFrame(rows)


def add_growth_score(df):
    """ROE・売上成長・自己資本比率の順位（0〜1）の平均を、100点満点にする。"""
    rank = lambda s: s.rank(pct=True)
    score = (rank(df["ROE"]) + rank(df["RevenueCAGR"]) + rank(df["EquityRatio"])) / 3 * 100
    return df.assign(GrowthScore=score.round(1))


def main():
    yield_max = float(sys.argv[1]) if len(sys.argv) > 1 else 0.025
    pick_n = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    list_max = int(sys.argv[3]) if len(sys.argv) > 3 else 30

    df = pd.read_csv("output_financial_dividend_merged.csv")
    cand = build_candidates(df)
    print(f"① 配当・財務の条件を満たす銘柄: {len(cand)}件 / 全{df['Symbol'].nunique()}件")
    if cand.empty:
        cand.to_csv("growth_filtered_output.csv", index=False, encoding="utf-8-sig")
        print("該当なし")
        return

    # ② 現在の利回りと分割の有無を取得する
    results, failed, kept_by_split, dropped = [], 0, 0, 0
    for _, row in cand.iterrows():
        ticker = yf.Ticker(row["Symbol"])
        dy = yfl.get_dividend_yield(ticker)
        if dy is None:
            failed += 1  # 取得できなかった銘柄は、黙って落とさず件数を表示する
            continue
        if dy <= 0:
            dropped += 1
            continue

        avg2y, _ = yfl.get_dividend_yield_2years_stats(ticker)
        valuation = (dy / avg2y) if avg2y else None  # 割安度（元ツールと同じ定義）
        split = yfl.get_split_info(ticker)  # 直近1年に分割があれば "Split"
        reasons = []
        if row["PayoutOver"]:
            reasons.append(f"配当性向が{row['PayoutRatio']:.0%}（上限{PAYOUT_MAX:.0%}超）")
        if dy >= yield_max:
            reasons.append(f"利回りが{dy:.1%}（上限{yield_max:.1%}以上）")

        if reasons and not split:
            dropped += 1
            continue  # 分割がないのに条件を外れている → 除外

        note = ""
        if reasons:  # 分割があるため、条件を外れていても残す
            kept_by_split += 1
            note = "分割で見かけ上" + "・".join(reasons) + "の可能性。要確認"

        results.append({
            **row.drop("PayoutOver").to_dict(),
            "DividendYield": dy,
            "AvgYield2Y": avg2y,
            "Valuation": valuation,
            "CurrentPrice": yfl.get_current_price(ticker),
            "SizeCategory": yfl.get_size_category(row["MarketCap"]),
            "SectorJP": yfl.get_sector(ticker),
            "SplitFlag": split,
            "Note": note,
        })
    print(
        f"② 利回り・配当性向の条件を満たす銘柄: {len(results)}件"
        f"（うち分割のため条件を外れても残した銘柄: {kept_by_split}件 / "
        f"条件を外れて除外: {dropped}件 / 利回りを取得できず除外: {failed}件）"
    )

    out = pd.DataFrame(results)
    if out.empty:
        out.to_csv("growth_filtered_output.csv", index=False, encoding="utf-8-sig")
        print("該当なし")
        return

    # ③ Valuation が下限以上の銘柄を GrowthScore 降順で並べ、上位を Pick=Y
    out = add_growth_score(out).reset_index(drop=True)
    eligible = out[out["Valuation"].notna() & (out["Valuation"] >= VALUATION_MIN)]
    pick_idx = set(eligible.sort_values(["GrowthScore", "Valuation"], ascending=False).head(pick_n).index)
    out["Pick"] = ["Y" if i in pick_idx else "" for i in out.index]
    out["_pick"] = out["Pick"] == "Y"
    out = (
        out.sort_values(["_pick", "GrowthScore", "Valuation"], ascending=[False, False, False], na_position="last")
        .drop(columns="_pick")
        .head(list_max)
        .reset_index(drop=True)
    )
    if len(eligible) < pick_n:
        print(f"※ 割安度が{VALUATION_MIN}以上の銘柄が{len(eligible)}件しかないため、候補は{len(pick_idx)}件です")

    cols = ["Symbol", "Company", "Pick", "Valuation", "GrowthScore", "CurrentPrice", "DividendYield", "AvgYield2Y",
            "ROE", "EquityRatio", "PayoutRatio", "RevenueCAGR", "MarketCap", "SizeCategory", "SectorJP",
            "SplitFlag", "Note"]
    out[cols].to_csv("growth_filtered_output.csv", index=False, encoding="utf-8-sig")

    print(f"③ 一覧: {len(out)}件 / 今回の候補(Pick=Y): {len(pick_idx)}件")
    print(out.loc[out["Pick"] == "Y", ["Symbol", "Company", "SectorJP", "Valuation", "GrowthScore", "DividendYield", "SplitFlag"]])


if __name__ == "__main__":
    main()
