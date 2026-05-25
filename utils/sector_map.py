# sector_map.py
# yfinance Sector → 日本語訳（最適化版）マッピング

sector_to_jp = {
    "Consumer Cyclical": "景気敏感消費（消費循環）",
    "Consumer Defensive": "生活必需品（ディフェンシブ消費）",
    "Industrials": "資本財・産業",
    "Technology": "テクノロジー（情報技術）",
    "Basic Materials": "素材（基礎資材）",
    "Healthcare": "ヘルスケア（医療関連）",
    "Financial Services": "金融サービス",
    "Real Estate": "不動産",
    "Utilities": "公益事業（電力・ガス）",
    "Energy": "エネルギー",
    "Communication Services": "通信サービス",
}

def translate_sector(sector: str) -> str:
    """
    yfinance Sector を日本語に変換する。
    未知の Sector の場合はそのまま返す。
    """
    if sector is None:
        return "不明"
    return sector_to_jp.get(sector, sector)
