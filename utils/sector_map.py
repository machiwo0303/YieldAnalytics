# sector_map.py
# yfinance Sector → GICS 11分類（日本語訳）マッピング

sector_to_jp = {
    "Energy": "エネルギー",
    "Basic Materials": "素材",
    "Industrials": "資本財・サービス",
    "Consumer Cyclical": "一般消費財・サービス",
    "Consumer Defensive": "生活必需品",
    "Healthcare": "ヘルスケア",
    "Financial Services": "金融",
    "Technology": "情報技術",
    "Communication Services": "コミュニケーション・サービス",
    "Utilities": "公益事業",
    "Real Estate": "不動産",
}

def translate_sector(sector: str) -> str:
    """
    yfinance Sector を GICS 11分類の日本語に変換する。
    未知の Sector の場合はそのまま返す。
    """
    if sector is None:
        return "不明"
    return sector_to_jp.get(sector, sector)
