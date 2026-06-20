"""
Korea Market Data Collector - pykrx 기반
- KRX 공식 데이터 (로그인 불필요, GitHub Actions 정상 작동)
- 거래대금 TOP300
- 52주 신고가
- 상한가
"""

import os
import sqlite3
import time
from datetime import datetime, date
from pykrx import stock as krx
from db import get_conn, init_db

def classify_sector(sector_name: str) -> str:
    """KRX 업종명 → 간결한 섹터명"""
    mapping = {
        "반도체": "반도체",
        "IT": "AI/소프트웨어",
        "소프트웨어": "AI/소프트웨어",
        "전기": "2차전지",
        "배터리": "2차전지",
        "제약": "바이오/제약",
        "바이오": "바이오/제약",
        "의약": "바이오/제약",
        "자동차": "자동차",
        "은행": "금융",
        "증권": "금융",
        "보험": "금융",
        "건설": "건설/부동산",
        "방산": "방산/우주",
        "항공": "방산/우주",
        "조선": "조선/해운",
        "해운": "조선/해운",
        "철강": "철강/화학",
        "화학": "철강/화학",
        "유통": "소비재/유통",
        "음식": "소비재/유통",
        "통신": "통신",
        "에너지": "에너지",
        "전력": "에너지",
    }
    for key, val in mapping.items():
        if key in sector_name:
            return val
    return "기타"


def get_date_str(target_date: str) -> str:
    """YYYY-MM-DD → YYYYMMDD"""
    return target_date.replace("-", "")


def fetch_volume_top300(target_date: str) -> list[dict]:
    """pykrx로 거래대금 TOP300 수집"""
    print(f"[pykrx] Fetching volume TOP300 for {target_date}...")
    d = get_date_str(target_date)
    results = []

    for market in ["KOSPI", "KOSDAQ"]:
        try:
            df = krx.get_market_ohlcv_by_ticker(d, market=market)
            df = df[df["거래대금"] > 0].copy()
            
            # 섹터 정보
            try:
                sector_df = krx.get_market_ticker_name(d, market=market)
            except:
                sector_df = {}

            for ticker in df.index:
                row = df.loc[ticker]
                name = krx.get_market_ticker_name(ticker)
                results.append({
                    "rank": 0,
                    "ticker": ticker,
                    "name": name if isinstance(name, str) else str(name),
                    "market": market,
                    "sector": "기타",
                    "close": float(row.get("종가", 0)),
                    "change_pct": float(row.get("등락률", 0)),
                    "volume": int(row.get("거래량", 0)),
                    "amount": float(row.get("거래대금", 0)) / 1e8,
                    "market_cap": 0,
                })
        except Exception as e:
            print(f"[pykrx] {market} error: {e}")

    # 섹터 일괄 조회
    try:
        sector_map = {}
        for market in ["KOSPI", "KOSDAQ"]:
            try:
                industries = krx.get_market_sector_classifications(d, market=market)
                for _, row in industries.iterrows():
                    sector_map[row.get("티커", "")] = classify_sector(row.get("업종명", "기타"))
            except:
                pass
        for r in results:
            if r["ticker"] in sector_map:
                r["sector"] = sector_map[r["ticker"]]
    except Exception as e:
        print(f"[pykrx] sector map error: {e}")

    # 거래대금 기준 정렬 + TOP300
    results.sort(key=lambda x: x["amount"], reverse=True)
    for i, r in enumerate(results[:300], 1):
        r["rank"] = i

    print(f"[pykrx] Fetched {len(results[:300])} volume items")
    return results[:300]


def fetch_high_price(target_date: str) -> list[dict]:
    """52주 신고가 종목 수집"""
    print(f"[pykrx] Fetching 52w high for {target_date}...")
    d = get_date_str(target_date)
    results = []

    for market in ["KOSPI", "KOSDAQ"]:
        try:
            df = krx.get_market_ohlcv_by_ticker(d, market=market)
            
            # 52주 고가 조회
            from datetime import timedelta
            start = (datetime.strptime(target_date, "%Y-%m-%d") - timedelta(days=365)).strftime("%Y%m%d")
            
            for ticker in df.index:
                try:
                    hist = krx.get_market_ohlcv_by_date(start, d, ticker)
                    if hist.empty:
                        continue
                    high_52w = hist["고가"].max()
                    today_high = df.loc[ticker, "고가"]
                    today_close = df.loc[ticker, "종가"]
                    change_pct = df.loc[ticker, "등락률"]
                    
                    if today_high >= high_52w * 0.99:  # 52주 신고가 근접
                        name = krx.get_market_ticker_name(ticker)
                        results.append({
                            "ticker": ticker,
                            "name": name if isinstance(name, str) else str(name),
                            "market": market,
                            "sector": "기타",
                            "close": float(today_close),
                            "change_pct": float(change_pct),
                            "high_52w": float(high_52w),
                        })
                except:
                    continue
        except Exception as e:
            print(f"[pykrx] high {market} error: {e}")

    print(f"[pykrx] Fetched {len(results)} high-price stocks")
    return results


def fetch_upper_limit(target_date: str) -> list[dict]:
    """상한가 종목 수집"""
    print(f"[pykrx] Fetching upper limit for {target_date}...")
    d = get_date_str(target_date)
    results = []

    for market in ["KOSPI", "KOSDAQ"]:
        try:
            df = krx.get_market_ohlcv_by_ticker(d, market=market)
            upper = df[df["등락률"] >= 29.0]
            
            for ticker in upper.index:
                name = krx.get_market_ticker_name(ticker)
                results.append({
                    "ticker": ticker,
                    "name": name if isinstance(name, str) else str(name),
                    "market": market,
                    "sector": "기타",
                    "close": float(upper.loc[ticker, "종가"]),
                })
        except Exception as e:
            print(f"[pykrx] upper {market} error: {e}")

    print(f"[pykrx] Fetched {len(results)} upper-limit stocks")
    return results


def log_collection(conn, date_str, source, status, count=0, message=""):
    conn.execute("""
        INSERT INTO collection_log (date, source, status, count, message)
        VALUES (?,?,?,?,?)
    """, (date_str, source, status, count, message))
    conn.commit()


def save_trading_volume(conn, date_str, items):
    c = conn.cursor()
    count = 0
    for item in items:
        try:
            c.execute("""
                INSERT OR REPLACE INTO trading_volume
                (date, rank, ticker, name, market, sector, close, change_pct, volume, amount, market_cap)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """, (date_str, item["rank"], item["ticker"], item["name"],
                  item["market"], item["sector"], item["close"], item["change_pct"],
                  item["volume"], item["amount"], item["market_cap"]))
            count += 1
        except Exception as e:
            pass
    conn.commit()
    log_collection(conn, date_str, "pykrx_volume", "success", count)
    print(f"[DB] Saved {count} volume records")


def save_high_price(conn, date_str, items):
    c = conn.cursor()
    count = 0
    for item in items:
        try:
            c.execute("""
                INSERT OR REPLACE INTO high_price
                (date, ticker, name, market, sector, close, change_pct, high_52w)
                VALUES (?,?,?,?,?,?,?,?)
            """, (date_str, item["ticker"], item["name"], item["market"],
                  item["sector"], item["close"], item["change_pct"], item["high_52w"]))
            count += 1
        except:
            pass
    conn.commit()
    log_collection(conn, date_str, "pykrx_high", "success", count)
    print(f"[DB] Saved {count} high-price records")


def save_upper_limit(conn, date_str, items):
    c = conn.cursor()
    count = 0
    for item in items:
        try:
            c.execute("""
                INSERT OR REPLACE INTO upper_limit
                (date, ticker, name, market, sector, close)
                VALUES (?,?,?,?,?,?)
            """, (date_str, item["ticker"], item["name"],
                  item["market"], item["sector"], item["close"]))
            count += 1
        except:
            pass
    conn.commit()
    log_collection(conn, date_str, "pykrx_upper", "success", count)
    print(f"[DB] Saved {count} upper-limit records")


def collect_all(target_date: str = None) -> dict:
    if target_date is None:
        target_date = date.today().strftime("%Y-%m-%d")

    print(f"\n{'='*60}")
    print(f"  Korea Market Data Collection: {target_date}")
    print(f"{'='*60}\n")

    init_db()
    conn = get_conn()

    volume_data = fetch_volume_top300(target_date)
    save_trading_volume(conn, target_date, volume_data)

    upper_data = fetch_upper_limit(target_date)
    save_upper_limit(conn, target_date, upper_data)

    # 신고가는 시간이 오래 걸리므로 간소화
    high_data = []
    try:
        high_data = fetch_high_price(target_date)
        save_high_price(conn, target_date, high_data)
    except Exception as e:
        print(f"[High] Skip due to: {e}")
        log_collection(conn, target_date, "pykrx_high", "skip", 0, str(e))

    conn.close()
    return {
        "date": target_date,
        "volume_count": len(volume_data),
        "high_count": len(high_data),
        "upper_count": len(upper_data),
    }


if __name__ == "__main__":
    result = collect_all()
    print(f"\n[Done] {result}")
