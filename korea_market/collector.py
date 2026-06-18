"""
Korea Market Data Collector
- RiccoRank 거래대금 TOP300
- 네이버 금융 신고가
- 네이버 금융 상한가
"""

import requests
import json
import time
import sqlite3
import random
from datetime import datetime, date
from bs4 import BeautifulSoup
from db import get_conn, init_db

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
    "Accept": "application/json, text/html, */*",
    "Referer": "https://finance.naver.com/",
}

# ── 섹터 매핑 (ticker prefix / 업종코드 기반 간이 분류) ───────────────────────
SECTOR_KEYWORDS = {
    "반도체": ["삼성전자", "SK하이닉스", "마이크론", "DB하이텍", "원익IPS", "HPSP", "리노공업", "ISC",
               "하나마이크론", "네패스", "이오테크닉스", "피에스케이", "테크윙", "한미반도체", "에스앤에스텍"],
    "2차전지": ["LG에너지솔루션", "삼성SDI", "SK이노베이션", "에코프로", "에코프로비엠", "포스코퓨처엠",
                "엘앤에프", "천보", "동화기업", "코스모신소재", "솔루스첨단소재"],
    "바이오/제약": ["삼성바이오로직스", "셀트리온", "한미약품", "유한양행", "종근당", "대웅제약", "HLB",
                   "알테오젠", "리가켐바이오", "오스코텍", "한올바이오파마"],
    "AI/소프트웨어": ["카카오", "네이버", "더존비즈온", "이스트소프트", "솔트룩스", "뤼이드", "코난테크놀로지"],
    "자동차": ["현대차", "기아", "현대모비스", "한온시스템", "HL만도", "현대위아", "성우하이텍"],
    "금융": ["KB금융", "신한지주", "하나금융지주", "우리금융지주", "메리츠금융지주", "삼성화재", "DB손해보험"],
    "건설/부동산": ["삼성물산", "현대건설", "GS건설", "대우건설", "HDC현대산업개발", "DL이앤씨"],
    "방산/우주": ["한화에어로스페이스", "LIG넥스원", "한국항공우주", "현대로템", "빅텍", "퍼스텍"],
    "조선/해운": ["HD한국조선해양", "삼성중공업", "한화오션", "HMM", "팬오션"],
    "철강/화학": ["POSCO홀딩스", "현대제철", "LG화학", "롯데케미칼", "금호석유", "한화솔루션"],
    "소비재/유통": ["삼성생활", "LG생활건강", "아모레퍼시픽", "이마트", "롯데쇼핑", "신세계"],
    "통신": ["SK텔레콤", "KT", "LG유플러스"],
    "에너지": ["한국전력", "SK이노베이션", "GS", "에쓰오일", "HD현대", "한국가스공사"],
    "반도체장비": ["원익IPS", "이오테크닉스", "PSK", "테크윙", "에스티아이", "케이씨텍", "유진테크"],
}


def classify_sector(name: str) -> str:
    """종목명으로 섹터 분류"""
    for sector, keywords in SECTOR_KEYWORDS.items():
        for kw in keywords:
            if kw in name:
                return sector
    return "기타"


# ── RiccoRank 거래대금 TOP300 ──────────────────────────────────────────────────

def fetch_ricco_top300(target_date: str) -> list[dict]:
    """
    RiccoRank API에서 거래대금 TOP300 수집
    target_date: YYYY-MM-DD
    """
    print(f"[Ricco] Fetching TOP300 for {target_date}...")
    results = []

    # RiccoRank는 인증 없이 접근 가능한 공개 API
    url = "https://riccorank.com/api/volume"
    params = {
        "date": target_date.replace("-", ""),  # YYYYMMDD
        "market": "ALL",
        "limit": 300,
    }

    try:
        resp = requests.get(url, params=params, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        items = data.get("data", data.get("items", data if isinstance(data, list) else []))
        for i, item in enumerate(items[:300], 1):
            sector = classify_sector(item.get("name", item.get("종목명", "")))
            results.append({
                "rank": i,
                "ticker": str(item.get("ticker", item.get("code", item.get("종목코드", "")))).zfill(6),
                "name": item.get("name", item.get("종목명", "")),
                "market": item.get("market", item.get("시장", "KOSPI")),
                "sector": sector,
                "close": float(item.get("close", item.get("종가", 0)) or 0),
                "change_pct": float(item.get("change_pct", item.get("등락률", 0)) or 0),
                "volume": int(item.get("volume", item.get("거래량", 0)) or 0),
                "amount": float(item.get("amount", item.get("거래대금", 0)) or 0) / 1e8,  # → 억원
                "market_cap": float(item.get("market_cap", item.get("시가총액", 0)) or 0) / 1e8,
            })
        print(f"[Ricco] Fetched {len(results)} items")
        return results

    except Exception as e:
        print(f"[Ricco] API failed: {e}, trying alternative...")
        return fetch_ricco_alternative(target_date)


def fetch_ricco_alternative(target_date: str) -> list[dict]:
    """대안: 네이버 금융 거래대금 상위 종목 수집"""
    results = []
    markets = [("KOSPI", "0"), ("KOSDAQ", "1")]

    for market_name, market_code in markets:
        for page in range(1, 6):  # 최대 5페이지 (페이지당 30개)
            url = f"https://finance.naver.com/sise/sise_quant.naver"
            params = {"sosok": market_code, "page": page}
            try:
                resp = requests.get(url, params=params, headers=HEADERS, timeout=10)
                soup = BeautifulSoup(resp.text, "lxml")
                table = soup.find("table", class_="type_2")
                if not table:
                    break
                rows = table.find_all("tr")[2:]
                for row in rows:
                    cols = row.find_all("td")
                    if len(cols) < 9:
                        continue
                    try:
                        name_tag = cols[1].find("a")
                        if not name_tag:
                            continue
                        name = name_tag.text.strip()
                        href = name_tag.get("href", "")
                        ticker = href.split("code=")[-1][:6] if "code=" in href else ""
                        close = float(cols[2].text.strip().replace(",", "") or 0)
                        change_pct_text = cols[4].text.strip().replace(",", "").replace("%", "")
                        change_pct = float(change_pct_text) if change_pct_text else 0
                        volume_text = cols[5].text.strip().replace(",", "")
                        volume = int(volume_text) if volume_text else 0
                        amount_text = cols[6].text.strip().replace(",", "")
                        amount = float(amount_text) if amount_text else 0  # 이미 억원 단위

                        results.append({
                            "rank": len(results) + 1,
                            "ticker": ticker,
                            "name": name,
                            "market": market_name,
                            "sector": classify_sector(name),
                            "close": close,
                            "change_pct": change_pct,
                            "volume": volume,
                            "amount": amount,
                            "market_cap": 0,
                        })
                    except (ValueError, IndexError):
                        continue
                time.sleep(0.3)
            except Exception as e:
                print(f"[Naver Volume] page {page} error: {e}")
                break

        if len(results) >= 300:
            break

    # 거래대금 기준 재정렬
    results.sort(key=lambda x: x["amount"], reverse=True)
    for i, r in enumerate(results[:300], 1):
        r["rank"] = i
    print(f"[Alt] Fetched {len(results[:300])} volume items")
    return results[:300]


# ── 네이버 금융 신고가 ───────────────────────────────────────────────────────

def fetch_naver_high_price(target_date: str) -> list[dict]:
    """네이버 금융 신고가 종목 수집"""
    print(f"[Naver High] Fetching 52w high for {target_date}...")
    results = []

    for page in range(1, 11):
        url = "https://finance.naver.com/sise/sise_high_price.naver"
        params = {"page": page}
        try:
            resp = requests.get(url, params=params, headers=HEADERS, timeout=10)
            soup = BeautifulSoup(resp.text, "lxml")
            table = soup.find("table", class_="type_2")
            if not table:
                break

            rows = table.find_all("tr")[2:]
            page_has_data = False
            for row in rows:
                cols = row.find_all("td")
                if len(cols) < 6:
                    continue
                try:
                    name_tag = cols[0].find("a")
                    if not name_tag:
                        continue
                    name = name_tag.text.strip()
                    href = name_tag.get("href", "")
                    ticker = href.split("code=")[-1][:6] if "code=" in href else ""
                    close = float(cols[1].text.strip().replace(",", "") or 0)
                    change_pct_text = cols[2].text.strip().replace(",", "").replace("%", "")
                    change_pct = float(change_pct_text) if change_pct_text else 0
                    high_52w_text = cols[4].text.strip().replace(",", "")
                    high_52w = float(high_52w_text) if high_52w_text else 0

                    results.append({
                        "ticker": ticker,
                        "name": name,
                        "market": "KOSPI",
                        "sector": classify_sector(name),
                        "close": close,
                        "change_pct": change_pct,
                        "high_52w": high_52w,
                    })
                    page_has_data = True
                except (ValueError, IndexError):
                    continue

            if not page_has_data:
                break
            time.sleep(0.3)
        except Exception as e:
            print(f"[Naver High] page {page} error: {e}")
            break

    # KOSDAQ 신고가도 수집
    for page in range(1, 6):
        url = "https://finance.naver.com/sise/sise_high_price.naver"
        params = {"sosok": "1", "page": page}
        try:
            resp = requests.get(url, params=params, headers=HEADERS, timeout=10)
            soup = BeautifulSoup(resp.text, "lxml")
            table = soup.find("table", class_="type_2")
            if not table:
                break
            rows = table.find_all("tr")[2:]
            for row in rows:
                cols = row.find_all("td")
                if len(cols) < 4:
                    continue
                try:
                    name_tag = cols[0].find("a")
                    if not name_tag:
                        continue
                    name = name_tag.text.strip()
                    href = name_tag.get("href", "")
                    ticker = href.split("code=")[-1][:6] if "code=" in href else ""
                    close = float(cols[1].text.strip().replace(",", "") or 0)
                    results.append({
                        "ticker": ticker,
                        "name": name,
                        "market": "KOSDAQ",
                        "sector": classify_sector(name),
                        "close": close,
                        "change_pct": 0,
                        "high_52w": close,
                    })
                except (ValueError, IndexError):
                    continue
            time.sleep(0.3)
        except Exception as e:
            break

    print(f"[Naver High] Fetched {len(results)} high-price stocks")
    return results


# ── 네이버 금융 상한가 ───────────────────────────────────────────────────────

def fetch_naver_upper_limit(target_date: str) -> list[dict]:
    """네이버 금융 상한가 종목 수집"""
    print(f"[Naver Upper] Fetching upper limit for {target_date}...")
    results = []

    for sosok, market_name in [("0", "KOSPI"), ("1", "KOSDAQ")]:
        url = "https://finance.naver.com/sise/sise_upper.naver"
        params = {"sosok": sosok}
        try:
            resp = requests.get(url, params=params, headers=HEADERS, timeout=10)
            soup = BeautifulSoup(resp.text, "lxml")
            table = soup.find("table", class_="type_2")
            if not table:
                continue
            rows = table.find_all("tr")[2:]
            for row in rows:
                cols = row.find_all("td")
                if len(cols) < 4:
                    continue
                try:
                    name_tag = cols[0].find("a")
                    if not name_tag:
                        continue
                    name = name_tag.text.strip()
                    href = name_tag.get("href", "")
                    ticker = href.split("code=")[-1][:6] if "code=" in href else ""
                    close = float(cols[1].text.strip().replace(",", "") or 0)
                    results.append({
                        "ticker": ticker,
                        "name": name,
                        "market": market_name,
                        "sector": classify_sector(name),
                        "close": close,
                    })
                except (ValueError, IndexError):
                    continue
            time.sleep(0.3)
        except Exception as e:
            print(f"[Naver Upper] {market_name} error: {e}")

    print(f"[Naver Upper] Fetched {len(results)} upper-limit stocks")
    return results


# ── DB 저장 ──────────────────────────────────────────────────────────────────

def save_trading_volume(conn: sqlite3.Connection, date_str: str, items: list[dict]):
    c = conn.cursor()
    count = 0
    for item in items:
        try:
            c.execute("""
                INSERT OR REPLACE INTO trading_volume
                (date, rank, ticker, name, market, sector, close, change_pct, volume, amount, market_cap)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """, (
                date_str, item["rank"], item["ticker"], item["name"],
                item["market"], item["sector"], item["close"], item["change_pct"],
                item["volume"], item["amount"], item["market_cap"],
            ))
            count += 1
        except Exception as e:
            print(f"[DB] volume insert error: {e}")
    conn.commit()
    log_collection(conn, date_str, "ricco_volume", "success", count)
    print(f"[DB] Saved {count} volume records")


def save_high_price(conn: sqlite3.Connection, date_str: str, items: list[dict]):
    c = conn.cursor()
    count = 0
    for item in items:
        try:
            c.execute("""
                INSERT OR REPLACE INTO high_price
                (date, ticker, name, market, sector, close, change_pct, high_52w)
                VALUES (?,?,?,?,?,?,?,?)
            """, (
                date_str, item["ticker"], item["name"], item["market"],
                item["sector"], item["close"], item["change_pct"], item["high_52w"],
            ))
            count += 1
        except Exception as e:
            print(f"[DB] high_price insert error: {e}")
    conn.commit()
    log_collection(conn, date_str, "naver_high", "success", count)
    print(f"[DB] Saved {count} high-price records")


def save_upper_limit(conn: sqlite3.Connection, date_str: str, items: list[dict]):
    c = conn.cursor()
    count = 0
    for item in items:
        try:
            c.execute("""
                INSERT OR REPLACE INTO upper_limit
                (date, ticker, name, market, sector, close)
                VALUES (?,?,?,?,?,?)
            """, (
                date_str, item["ticker"], item["name"],
                item["market"], item["sector"], item["close"],
            ))
            count += 1
        except Exception as e:
            print(f"[DB] upper_limit insert error: {e}")
    conn.commit()
    log_collection(conn, date_str, "naver_upper", "success", count)
    print(f"[DB] Saved {count} upper-limit records")


def log_collection(conn, date_str, source, status, count=0, message=""):
    conn.execute("""
        INSERT INTO collection_log (date, source, status, count, message)
        VALUES (?,?,?,?,?)
    """, (date_str, source, status, count, message))
    conn.commit()


# ── 메인 수집 함수 ────────────────────────────────────────────────────────────

def collect_all(target_date: str = None) -> dict:
    """
    전체 데이터 수집 및 DB 저장
    target_date: YYYY-MM-DD (기본값: 오늘)
    """
    if target_date is None:
        target_date = date.today().strftime("%Y-%m-%d")

    print(f"\n{'='*60}")
    print(f"  Korea Market Data Collection: {target_date}")
    print(f"{'='*60}\n")

    init_db()
    conn = get_conn()

    # 1. 거래대금 TOP300
    volume_data = fetch_ricco_top300(target_date)
    if not volume_data:
        volume_data = fetch_ricco_alternative(target_date)
    save_trading_volume(conn, target_date, volume_data)

    # 2. 신고가
    high_data = fetch_naver_high_price(target_date)
    save_high_price(conn, target_date, high_data)

    # 3. 상한가
    upper_data = fetch_naver_upper_limit(target_date)
    save_upper_limit(conn, target_date, upper_data)

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
