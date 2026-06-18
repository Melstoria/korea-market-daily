"""
Korea Market Analysis Engine
- 섹터별 거래대금/신고가/상한가 집계
- 전일 대비 변화율
- 섹터 강도 점수 (Sector Strength Score)
- 주도섹터 자동 선정
- 순환매 탐지
"""

import sqlite3
import json
import math
from datetime import datetime, timedelta, date
from db import get_conn


# ── 섹터 강도 점수 알고리즘 ──────────────────────────────────────────────────
#
# 섹터 강도 점수 = 거래대금 점수(40%) + 신고가 점수(30%) + 상한가 점수(20%) + 모멘텀 점수(10%)
#
# 각 지표는 섹터 내 최대값 기준으로 0~100 정규화

def normalize(val, max_val):
    if max_val == 0:
        return 0
    return min(100.0, (val / max_val) * 100)


def calculate_sector_score(amount, high_cnt, upper_cnt, avg_change,
                            max_amount, max_high, max_upper):
    amount_score = normalize(amount, max_amount) * 0.40
    high_score = normalize(high_cnt, max_high) * 0.30
    upper_score = normalize(upper_cnt, max_upper) * 0.20
    momentum = max(0, min(10, avg_change)) * 1.0  # 0~10%
    return round(amount_score + high_score + upper_score + momentum, 2)


def aggregate_sectors(conn: sqlite3.Connection, date_str: str) -> list[dict]:
    """날짜의 섹터별 집계 계산 및 sector_daily 저장"""
    c = conn.cursor()

    # 거래대금 섹터 집계
    c.execute("""
        SELECT sector,
               SUM(amount)       AS total_amount,
               COUNT(*)          AS stock_count,
               AVG(change_pct)   AS avg_change
        FROM trading_volume
        WHERE date = ?
        GROUP BY sector
    """, (date_str,))
    volume_rows = {r["sector"]: dict(r) for r in c.fetchall()}

    # 신고가 섹터 집계
    c.execute("""
        SELECT sector, COUNT(*) AS cnt
        FROM high_price WHERE date = ?
        GROUP BY sector
    """, (date_str,))
    high_rows = {r["sector"]: r["cnt"] for r in c.fetchall()}

    # 상한가 섹터 집계
    c.execute("""
        SELECT sector, COUNT(*) AS cnt
        FROM upper_limit WHERE date = ?
        GROUP BY sector
    """, (date_str,))
    upper_rows = {r["sector"]: r["cnt"] for r in c.fetchall()}

    # 모든 섹터 합집합
    all_sectors = set(list(volume_rows.keys()) + list(high_rows.keys()) + list(upper_rows.keys()))

    sectors = []
    for sector in all_sectors:
        v = volume_rows.get(sector, {})
        sectors.append({
            "sector": sector,
            "total_amount": v.get("total_amount", 0) or 0,
            "stock_count": v.get("stock_count", 0) or 0,
            "high_count": high_rows.get(sector, 0),
            "upper_count": upper_rows.get(sector, 0),
            "avg_change_pct": v.get("avg_change", 0) or 0,
        })

    if not sectors:
        return []

    # 정규화 기준값
    max_amount = max(s["total_amount"] for s in sectors) or 1
    max_high = max(s["high_count"] for s in sectors) or 1
    max_upper = max(s["upper_count"] for s in sectors) or 1

    for s in sectors:
        s["sector_score"] = calculate_sector_score(
            s["total_amount"], s["high_count"], s["upper_count"], s["avg_change_pct"],
            max_amount, max_high, max_upper
        )

    # DB 저장
    for s in sectors:
        conn.execute("""
            INSERT OR REPLACE INTO sector_daily
            (date, sector, total_amount, stock_count, high_count, upper_count, avg_change_pct, sector_score)
            VALUES (?,?,?,?,?,?,?,?)
        """, (
            date_str, s["sector"], s["total_amount"], s["stock_count"],
            s["high_count"], s["upper_count"], s["avg_change_pct"], s["sector_score"]
        ))
    conn.commit()

    return sorted(sectors, key=lambda x: x["sector_score"], reverse=True)


def get_prev_trading_date(conn: sqlite3.Connection, current_date: str) -> str | None:
    """이전 영업일 찾기"""
    c = conn.cursor()
    c.execute("""
        SELECT DISTINCT date FROM sector_daily
        WHERE date < ?
        ORDER BY date DESC
        LIMIT 1
    """, (current_date,))
    row = c.fetchone()
    return row["date"] if row else None


def calc_change_rates(conn: sqlite3.Connection, date_str: str, prev_date: str) -> dict:
    """전일 대비 섹터 거래대금/신고가 변화율 계산"""
    c = conn.cursor()

    # 현재
    c.execute("SELECT * FROM sector_daily WHERE date=?", (date_str,))
    today = {r["sector"]: dict(r) for r in c.fetchall()}

    # 전일
    c.execute("SELECT * FROM sector_daily WHERE date=?", (prev_date,))
    prev = {r["sector"]: dict(r) for r in c.fetchall()}

    changes = {}
    all_secs = set(list(today.keys()) + list(prev.keys()))
    for sec in all_secs:
        t = today.get(sec, {})
        p = prev.get(sec, {})

        ta = t.get("total_amount", 0) or 0
        pa = p.get("total_amount", 0) or 0
        th = t.get("high_count", 0) or 0
        ph = p.get("high_count", 0) or 0

        changes[sec] = {
            "amount_change_pct": ((ta - pa) / pa * 100) if pa else (100 if ta else 0),
            "high_change_pct": ((th - ph) / ph * 100) if ph else (100 if th else 0),
            "today_score": t.get("sector_score", 0) or 0,
            "prev_score": p.get("sector_score", 0) or 0,
        }

    return changes


# ── 순환매 탐지 ───────────────────────────────────────────────────────────────

def detect_rotation(conn: sqlite3.Connection, date_str: str) -> dict:
    """
    순환매 탐지 로직
    - 최근 5일 섹터 강도 점수 변화 분석
    - 이전 주도섹터가 하락하고 새 섹터가 부상하면 순환매 신호
    """
    c = conn.cursor()

    # 최근 5거래일 데이터
    c.execute("""
        SELECT date, sector, sector_score, total_amount
        FROM sector_daily
        WHERE date <= ?
        ORDER BY date DESC
        LIMIT 60
    """, (date_str,))
    rows = c.fetchall()

    if not rows:
        return {"signal": "데이터 부족", "detail": ""}

    # 날짜별로 정리
    from collections import defaultdict
    date_data = defaultdict(dict)
    dates = []
    for r in rows:
        date_data[r["date"]][r["sector"]] = r["sector_score"]
        if r["date"] not in dates:
            dates.append(r["date"])

    dates = sorted(dates, reverse=True)[:5]

    if len(dates) < 2:
        return {"signal": "관망", "detail": "비교 데이터 부족 (2영업일 미만)"}

    today_scores = date_data[dates[0]]
    prev_scores = date_data[dates[1]]

    # 상승 섹터 vs 하락 섹터
    rising = []
    falling = []
    for sec, score in today_scores.items():
        prev = prev_scores.get(sec, 0)
        change = score - prev
        if change >= 5:
            rising.append((sec, change))
        elif change <= -5:
            falling.append((sec, change))

    rising.sort(key=lambda x: x[1], reverse=True)
    falling.sort(key=lambda x: x[1])

    # 신호 판단
    if not rising and not falling:
        signal = "중립 — 섹터 간 강도 변화 미미"
    elif rising and falling:
        # 진성 순환매: 주도섹터 교체
        if dates[1] in date_data:
            top_yesterday = max(prev_scores.items(), key=lambda x: x[1])[0] if prev_scores else ""
            top_today = max(today_scores.items(), key=lambda x: x[1])[0] if today_scores else ""
            if top_yesterday != top_today:
                signal = f"⚡ 순환매 포착 — {top_yesterday} → {top_today}"
            else:
                rising_names = ", ".join([r[0] for r in rising[:2]])
                signal = f"🔄 부분 순환매 — {rising_names} 부상"
        else:
            signal = "순환매 감지"
    elif rising:
        rising_names = ", ".join([r[0] for r in rising[:2]])
        signal = f"📈 섹터 집중 — {rising_names} 강화"
    else:
        falling_names = ", ".join([f[0] for f in falling[:2]])
        signal = f"📉 섹터 약화 — {falling_names} 매도 압력"

    detail_parts = []
    if rising:
        detail_parts.append("부상: " + ", ".join(f"{s}(+{c:.1f}p)" for s, c in rising[:3]))
    if falling:
        detail_parts.append("약화: " + ", ".join(f"{s}({c:.1f}p)" for s, c in falling[:3]))

    return {"signal": signal, "detail": " / ".join(detail_parts)}


def select_leading_sectors(sectors: list[dict], top_n: int = 5) -> list[dict]:
    """주도섹터 선정 (섹터 강도 점수 TOP N)"""
    filtered = [s for s in sectors if s["sector"] != "기타"]
    return sorted(filtered, key=lambda x: x["sector_score"], reverse=True)[:top_n]


def get_market_summary(sectors: list[dict], high_total: int, upper_total: int,
                       rotation: dict) -> str:
    """시장 총평 자동 생성"""
    if not sectors:
        return "데이터 없음"

    top3 = [s["sector"] for s in sectors[:3] if s["sector"] != "기타"]
    total_amount = sum(s["total_amount"] for s in sectors)

    if upper_total >= 30:
        tone = "강세장 — 광범위한 매수세"
    elif upper_total >= 15:
        tone = "온건한 상승세"
    elif upper_total >= 5:
        tone = "선별적 강세"
    else:
        tone = "관망/조정 국면"

    leading = "·".join(top3) if top3 else "없음"
    return (
        f"{tone}. 주도섹터: {leading}. "
        f"총 거래대금 {total_amount:,.0f}억원, "
        f"상한가 {upper_total}개·신고가 {high_total}개. "
        f"{rotation['signal']}."
    )


def run_analysis(target_date: str = None) -> dict:
    """전체 분석 실행"""
    if target_date is None:
        target_date = date.today().strftime("%Y-%m-%d")

    print(f"\n[Analysis] Running for {target_date}")
    conn = get_conn()

    # 섹터 집계
    sectors = aggregate_sectors(conn, target_date)
    if not sectors:
        print("[Analysis] No data found for this date")
        conn.close()
        return {}

    # 전일 비교
    prev_date = get_prev_trading_date(conn, target_date)
    changes = calc_change_rates(conn, target_date, prev_date) if prev_date else {}

    # 주도섹터
    leading = select_leading_sectors(sectors)

    # 순환매
    rotation = detect_rotation(conn, target_date)

    # 신고가/상한가 총계
    c = conn.cursor()
    c.execute("SELECT COUNT(*) AS cnt FROM high_price WHERE date=?", (target_date,))
    high_total = c.fetchone()["cnt"]
    c.execute("SELECT COUNT(*) AS cnt FROM upper_limit WHERE date=?", (target_date,))
    upper_total = c.fetchone()["cnt"]

    # 시장 총평
    summary = get_market_summary(sectors, high_total, upper_total, rotation)

    # sector_leadership 저장
    top_sectors_json = json.dumps(
        [{"sector": s["sector"], "score": s["sector_score"], "amount": s["total_amount"]}
         for s in leading],
        ensure_ascii=False
    )
    conn.execute("""
        INSERT OR REPLACE INTO sector_leadership
        (date, top_sectors, rotation_signal, market_summary)
        VALUES (?,?,?,?)
    """, (target_date, top_sectors_json, rotation["signal"], summary))
    conn.commit()

    # 거래대금 TOP10 종목
    c.execute("""
        SELECT rank, ticker, name, market, sector, close, change_pct, amount
        FROM trading_volume WHERE date=?
        ORDER BY rank LIMIT 20
    """, (target_date,))
    top_stocks = [dict(r) for r in c.fetchall()]

    # 신고가 종목 (상위 30)
    c.execute("""
        SELECT ticker, name, market, sector, close, change_pct
        FROM high_price WHERE date=?
        ORDER BY change_pct DESC LIMIT 30
    """, (target_date,))
    high_stocks = [dict(r) for r in c.fetchall()]

    # 상한가 종목
    c.execute("""
        SELECT ticker, name, market, sector, close
        FROM upper_limit WHERE date=?
        ORDER BY market, name
    """, (target_date,))
    upper_stocks = [dict(r) for r in c.fetchall()]

    conn.close()

    result = {
        "date": target_date,
        "prev_date": prev_date,
        "sectors": sectors,
        "leading_sectors": leading,
        "changes": changes,
        "rotation": rotation,
        "market_summary": summary,
        "top_stocks": top_stocks,
        "high_stocks": high_stocks,
        "upper_stocks": upper_stocks,
        "high_total": high_total,
        "upper_total": upper_total,
        "total_amount": sum(s["total_amount"] for s in sectors),
    }

    print(f"[Analysis] Done. Leading: {[s['sector'] for s in leading[:3]]}")
    print(f"[Analysis] Rotation: {rotation['signal']}")
    return result


if __name__ == "__main__":
    result = run_analysis()
    if result:
        print(f"\nMarket Summary: {result['market_summary']}")
        print(f"Top Sectors: {[s['sector'] for s in result['leading_sectors']]}")
