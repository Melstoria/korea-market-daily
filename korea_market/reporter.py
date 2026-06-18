"""
Korea Market HTML Report Generator
Apple 스타일 + 임팩트 있는 투자 인사이트 리포트
"""

import json
import os
from datetime import datetime
from analyzer import run_analysis

OUTPUT_DIR = os.environ.get("OUTPUT_DIR",
             os.path.join(os.path.dirname(__file__), "../docs/reports"))


def fmt_amt(val: float) -> str:
    """억원 → 읽기 좋은 형식"""
    if val >= 10000:
        return f"{val/10000:.1f}조"
    return f"{val:,.0f}억"


def fmt_pct(val: float) -> str:
    sign = "+" if val > 0 else ""
    return f"{sign}{val:.2f}%"


def sector_color(score: float) -> str:
    """섹터 점수 → 색상 클래스"""
    if score >= 70:
        return "hot"
    elif score >= 45:
        return "warm"
    elif score >= 20:
        return "mild"
    return "cool"


def change_class(pct: float) -> str:
    if pct > 0:
        return "up"
    elif pct < 0:
        return "down"
    return "flat"


def get_sector_icon(sector: str) -> str:
    icons = {
        "반도체": "🔵", "2차전지": "⚡", "바이오/제약": "🧬",
        "AI/소프트웨어": "🤖", "자동차": "🚗", "금융": "🏦",
        "건설/부동산": "🏗️", "방산/우주": "🚀", "조선/해운": "⚓",
        "철강/화학": "⚙️", "소비재/유통": "🛍️", "통신": "📡",
        "에너지": "⛽", "반도체장비": "🔬", "기타": "📊",
    }
    return icons.get(sector, "📊")


def generate_report(data: dict, output_dir: str = None) -> str:
    """HTML 리포트 생성 → 파일 경로 반환"""
    if not data:
        raise ValueError("No analysis data")

    if output_dir is None:
        output_dir = OUTPUT_DIR
    os.makedirs(output_dir, exist_ok=True)

    date_str = data["date"]
    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    date_kor = date_obj.strftime("%Y년 %m월 %d일")
    weekdays = ["월", "화", "수", "목", "금", "토", "일"]
    date_display = f"{date_kor} ({weekdays[date_obj.weekday()]})"

    sectors = data.get("sectors", [])
    leading = data.get("leading_sectors", [])
    changes = data.get("changes", {})
    rotation = data.get("rotation", {})
    top_stocks = data.get("top_stocks", [])
    high_stocks = data.get("high_stocks", [])
    upper_stocks = data.get("upper_stocks", [])

    total_amount = data.get("total_amount", 0)
    high_total = data.get("high_total", 0)
    upper_total = data.get("upper_total", 0)
    summary = data.get("market_summary", "")

    # 섹터 점수 차트 (상위 12개)
    top_sectors_chart = sorted(sectors, key=lambda x: x["sector_score"], reverse=True)[:12]
    max_score = max(s["sector_score"] for s in top_sectors_chart) if top_sectors_chart else 100

    # 섹터 막대 차트 데이터
    chart_bars = ""
    for s in top_sectors_chart:
        bar_w = (s["sector_score"] / max_score * 100)
        cls = sector_color(s["sector_score"])
        icon = get_sector_icon(s["sector"])
        ch = changes.get(s["sector"], {})
        ac = ch.get("amount_change_pct", 0)
        ac_cls = change_class(ac)
        chart_bars += f"""
        <div class="bar-row">
          <div class="bar-label">
            <span class="sector-icon">{icon}</span>
            <span class="sector-name">{s["sector"]}</span>
            <span class="change-badge {ac_cls}">{fmt_pct(ac)}</span>
          </div>
          <div class="bar-track">
            <div class="bar-fill {cls}" style="width:{bar_w:.1f}%"></div>
            <span class="bar-score">{s['sector_score']:.1f}</span>
          </div>
          <div class="bar-meta">
            <span>{fmt_amt(s['total_amount'])}</span>
            <span class="tag-high">📍{s['high_count']}</span>
            <span class="tag-upper">🔝{s['upper_count']}</span>
          </div>
        </div>"""

    # 주도섹터 카드
    leading_cards = ""
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
    for i, s in enumerate(leading[:5]):
        medal = medals[i] if i < len(medals) else f"{i+1}."
        icon = get_sector_icon(s["sector"])
        ch = changes.get(s["sector"], {})
        ac = ch.get("amount_change_pct", 0)
        hc = ch.get("high_change_pct", 0)
        cls = sector_color(s["sector_score"])
        leading_cards += f"""
        <div class="lead-card {cls}">
          <div class="lead-rank">{medal}</div>
          <div class="lead-icon">{icon}</div>
          <div class="lead-name">{s["sector"]}</div>
          <div class="lead-score">{s['sector_score']:.1f}<span>pts</span></div>
          <div class="lead-stats">
            <div class="lead-stat"><label>거래대금</label><val>{fmt_amt(s['total_amount'])}</val></div>
            <div class="lead-stat"><label>신고가</label><val>{s['high_count']}개</val></div>
            <div class="lead-stat"><label>상한가</label><val>{s['upper_count']}개</val></div>
          </div>
          <div class="lead-change">
            전일比 거래대금 <span class="{change_class(ac)}">{fmt_pct(ac)}</span>
          </div>
        </div>"""

    # 거래대금 TOP20 테이블
    volume_rows = ""
    for stock in top_stocks:
        cc = change_class(stock.get("change_pct", 0))
        market_badge = "kospi" if stock.get("market") == "KOSPI" else "kosdaq"
        volume_rows += f"""
        <tr>
          <td class="rank-cell">{stock['rank']}</td>
          <td class="name-cell">
            <span class="stock-name">{stock['name']}</span>
            <span class="market-badge {market_badge}">{stock.get('market','')}</span>
          </td>
          <td class="sector-cell">{get_sector_icon(stock.get('sector','기타'))} {stock.get('sector','기타')}</td>
          <td class="price-cell">{stock.get('close',0):,.0f}원</td>
          <td class="change-cell {cc}">{fmt_pct(stock.get('change_pct',0))}</td>
          <td class="amount-cell">{fmt_amt(stock.get('amount',0))}</td>
        </tr>"""

    # 신고가 종목 그리드
    high_grid = ""
    for stock in high_stocks[:20]:
        cc = change_class(stock.get("change_pct", 0))
        high_grid += f"""
        <div class="stock-chip">
          <span class="chip-name">{stock['name']}</span>
          <span class="chip-pct {cc}">{fmt_pct(stock.get('change_pct',0))}</span>
          <span class="chip-sector">{stock.get('sector','기타')}</span>
        </div>"""

    # 상한가 종목 그리드
    upper_grid = ""
    for stock in upper_stocks:
        market_badge = "kospi" if stock.get("market") == "KOSPI" else "kosdaq"
        upper_grid += f"""
        <div class="upper-chip">
          <span class="chip-name">{stock['name']}</span>
          <span class="market-badge {market_badge}">{stock.get('market','')}</span>
          <span class="chip-sector">{get_sector_icon(stock.get('sector','기타'))}</span>
        </div>"""

    if not upper_grid:
        upper_grid = '<div class="empty-state">상한가 종목 없음</div>'
    if not high_grid:
        high_grid = '<div class="empty-state">신고가 종목 없음</div>'

    # 로테이션 신호 아이콘
    rot_signal = rotation.get("signal", "데이터 없음")
    rot_detail = rotation.get("detail", "")
    if "순환매" in rot_signal:
        rot_icon = "🔄"
        rot_cls = "rotation-alert"
    elif "집중" in rot_signal or "부상" in rot_signal:
        rot_icon = "📈"
        rot_cls = "rotation-up"
    elif "약화" in rot_signal:
        rot_icon = "📉"
        rot_cls = "rotation-down"
    else:
        rot_icon = "➡️"
        rot_cls = "rotation-neutral"

    # 전일 비교 섹션
    if data.get("prev_date"):
        prev_display = data["prev_date"]
    else:
        prev_display = "전일 데이터 없음"

    # === HTML 생성 ===
    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>한국 시장 일간 리포트 — {date_kor}</title>
<style>
  /* ── Reset & Base ── */
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  :root {{
    --bg: #0a0a0f;
    --bg2: #111118;
    --bg3: #1a1a24;
    --surface: #1e1e2e;
    --surface2: #252538;
    --border: rgba(255,255,255,0.08);
    --border2: rgba(255,255,255,0.14);
    --text: #e8e8f0;
    --text2: #9090a8;
    --text3: #5a5a72;
    --accent: #6c6cff;
    --accent2: #8080ff;
    --accent-glow: rgba(108,108,255,0.25);
    --up: #00d97e;
    --up-bg: rgba(0,217,126,0.1);
    --down: #ff4d6d;
    --down-bg: rgba(255,77,109,0.1);
    --flat: #8888aa;
    --gold: #ffd700;
    --hot: #ff6b2b;
    --hot-bg: rgba(255,107,43,0.12);
    --warm: #f7c948;
    --warm-bg: rgba(247,201,72,0.12);
    --mild: #4db8ff;
    --mild-bg: rgba(77,184,255,0.1);
    --cool: #7a7a9a;
    --cool-bg: rgba(122,122,154,0.08);
    --radius: 16px;
    --radius-sm: 10px;
    --font: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Pretendard', 'Noto Sans KR', sans-serif;
    --mono: 'SF Mono', 'JetBrains Mono', 'Fira Code', monospace;
  }}

  body {{
    font-family: var(--font);
    background: var(--bg);
    color: var(--text);
    line-height: 1.5;
    min-height: 100vh;
    overflow-x: hidden;
  }}

  /* ── Header ── */
  .header {{
    background: linear-gradient(160deg, #0d0d1a 0%, #111128 40%, #0d0d1a 100%);
    border-bottom: 1px solid var(--border);
    padding: 40px 48px 32px;
    position: relative;
    overflow: hidden;
  }}
  .header::before {{
    content: '';
    position: absolute;
    top: -60px; left: -60px;
    width: 300px; height: 300px;
    background: radial-gradient(circle, rgba(108,108,255,0.15) 0%, transparent 70%);
    pointer-events: none;
  }}
  .header::after {{
    content: '';
    position: absolute;
    bottom: -80px; right: 100px;
    width: 250px; height: 250px;
    background: radial-gradient(circle, rgba(255,107,43,0.08) 0%, transparent 70%);
    pointer-events: none;
  }}
  .header-top {{
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 16px;
    position: relative;
  }}
  .header-brand {{
    display: flex;
    align-items: center;
    gap: 12px;
  }}
  .brand-logo {{
    width: 44px; height: 44px;
    background: linear-gradient(135deg, var(--accent), var(--hot));
    border-radius: 12px;
    display: flex; align-items: center; justify-content: center;
    font-size: 22px;
  }}
  .brand-text h1 {{
    font-size: 20px;
    font-weight: 700;
    letter-spacing: -0.3px;
    color: var(--text);
  }}
  .brand-text p {{
    font-size: 12px;
    color: var(--text3);
    letter-spacing: 0.5px;
    text-transform: uppercase;
  }}
  .header-date {{
    text-align: right;
  }}
  .date-main {{
    font-size: 28px;
    font-weight: 700;
    color: var(--text);
    letter-spacing: -0.5px;
  }}
  .date-sub {{
    font-size: 12px;
    color: var(--text3);
    margin-top: 2px;
  }}

  /* ── Summary Banner ── */
  .summary-banner {{
    background: linear-gradient(135deg, rgba(108,108,255,0.1), rgba(255,107,43,0.08));
    border: 1px solid rgba(108,108,255,0.2);
    border-radius: var(--radius);
    padding: 20px 24px;
    margin-top: 28px;
    position: relative;
    backdrop-filter: blur(8px);
  }}
  .summary-banner p {{
    font-size: 15px;
    color: var(--text);
    line-height: 1.7;
    font-weight: 400;
  }}
  .summary-banner strong {{
    color: var(--accent2);
    font-weight: 600;
  }}

  /* ── KPI Grid ── */
  .kpi-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 16px;
    padding: 32px 48px;
    background: var(--bg);
  }}
  .kpi-card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 20px;
    transition: border-color 0.2s, transform 0.2s;
  }}
  .kpi-card:hover {{ border-color: var(--border2); transform: translateY(-2px); }}
  .kpi-label {{
    font-size: 11px;
    color: var(--text3);
    text-transform: uppercase;
    letter-spacing: 0.8px;
    font-weight: 500;
    margin-bottom: 8px;
  }}
  .kpi-value {{
    font-size: 28px;
    font-weight: 700;
    letter-spacing: -0.5px;
    line-height: 1;
  }}
  .kpi-value.accent {{ color: var(--accent2); }}
  .kpi-value.hot {{ color: var(--hot); }}
  .kpi-value.gold {{ color: var(--gold); }}
  .kpi-value.up {{ color: var(--up); }}
  .kpi-sub {{
    font-size: 12px;
    color: var(--text3);
    margin-top: 6px;
  }}

  /* ── Main layout ── */
  .main {{
    padding: 0 48px 48px;
    max-width: 1400px;
    margin: 0 auto;
  }}
  .section {{
    margin-bottom: 40px;
  }}
  .section-header {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 20px;
    padding-bottom: 12px;
    border-bottom: 1px solid var(--border);
  }}
  .section-title {{
    font-size: 18px;
    font-weight: 700;
    color: var(--text);
    letter-spacing: -0.3px;
  }}
  .section-badge {{
    font-size: 12px;
    color: var(--text3);
    background: var(--surface);
    padding: 4px 10px;
    border-radius: 20px;
    border: 1px solid var(--border);
  }}

  /* ── Leading Cards ── */
  .lead-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
    gap: 16px;
  }}
  .lead-card {{
    border-radius: var(--radius);
    padding: 20px;
    border: 1px solid var(--border);
    transition: transform 0.2s, box-shadow 0.2s;
    position: relative;
    overflow: hidden;
  }}
  .lead-card::before {{
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
  }}
  .lead-card.hot {{ background: var(--hot-bg); }}
  .lead-card.hot::before {{ background: linear-gradient(90deg, var(--hot), #ff9f6b); }}
  .lead-card.warm {{ background: var(--warm-bg); }}
  .lead-card.warm::before {{ background: linear-gradient(90deg, var(--warm), #ffe08a); }}
  .lead-card.mild {{ background: var(--mild-bg); }}
  .lead-card.mild::before {{ background: linear-gradient(90deg, var(--mild), #a0d4ff); }}
  .lead-card.cool {{ background: var(--cool-bg); }}
  .lead-card.cool::before {{ background: var(--cool); }}
  .lead-card:hover {{ transform: translateY(-4px); box-shadow: 0 12px 32px rgba(0,0,0,0.4); }}
  .lead-rank {{ font-size: 20px; margin-bottom: 6px; }}
  .lead-icon {{ font-size: 28px; margin-bottom: 8px; }}
  .lead-name {{ font-size: 15px; font-weight: 700; color: var(--text); margin-bottom: 8px; }}
  .lead-score {{
    font-size: 32px; font-weight: 800; letter-spacing: -1px;
    color: var(--text); line-height: 1; margin-bottom: 12px;
  }}
  .lead-score span {{ font-size: 13px; font-weight: 400; color: var(--text3); margin-left: 2px; }}
  .lead-stats {{ display: flex; flex-direction: column; gap: 4px; margin-bottom: 10px; }}
  .lead-stat {{ display: flex; justify-content: space-between; align-items: center; }}
  .lead-stat label {{ font-size: 11px; color: var(--text3); }}
  .lead-stat val {{ font-size: 12px; font-weight: 600; color: var(--text); }}
  .lead-change {{ font-size: 11px; color: var(--text3); padding-top: 8px; border-top: 1px solid var(--border); }}
  .lead-change .up {{ color: var(--up); font-weight: 600; }}
  .lead-change .down {{ color: var(--down); font-weight: 600; }}

  /* ── Sector Bar Chart ── */
  .bar-chart {{ display: flex; flex-direction: column; gap: 10px; }}
  .bar-row {{
    display: grid;
    grid-template-columns: 220px 1fr 160px;
    gap: 12px;
    align-items: center;
  }}
  .bar-label {{
    display: flex; align-items: center; gap: 8px;
    min-width: 0;
  }}
  .sector-icon {{ font-size: 16px; flex-shrink: 0; }}
  .sector-name {{
    font-size: 13px; font-weight: 500; color: var(--text);
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }}
  .change-badge {{
    font-size: 10px; font-weight: 600; padding: 2px 6px;
    border-radius: 10px; flex-shrink: 0; font-family: var(--mono);
  }}
  .change-badge.up {{ background: var(--up-bg); color: var(--up); }}
  .change-badge.down {{ background: var(--down-bg); color: var(--down); }}
  .change-badge.flat {{ background: var(--cool-bg); color: var(--flat); }}
  .bar-track {{
    background: var(--surface2);
    border-radius: 4px;
    height: 24px;
    position: relative;
    overflow: visible;
    display: flex;
    align-items: center;
  }}
  .bar-fill {{
    height: 100%;
    border-radius: 4px;
    transition: width 0.8s cubic-bezier(0.16,1,0.3,1);
    min-width: 4px;
  }}
  .bar-fill.hot {{ background: linear-gradient(90deg, var(--hot), #ff9f6b); }}
  .bar-fill.warm {{ background: linear-gradient(90deg, var(--warm), #ffe08a); }}
  .bar-fill.mild {{ background: linear-gradient(90deg, var(--mild), #a0d4ff); }}
  .bar-fill.cool {{ background: var(--cool); }}
  .bar-score {{
    position: absolute;
    right: 8px;
    font-size: 11px; font-weight: 700;
    color: rgba(255,255,255,0.7);
    font-family: var(--mono);
  }}
  .bar-meta {{
    display: flex; gap: 10px; align-items: center;
    font-size: 12px; color: var(--text2);
    justify-content: flex-end;
  }}
  .tag-high {{ color: var(--mild); font-weight: 600; }}
  .tag-upper {{ color: var(--gold); font-weight: 600; }}

  /* ── Tables ── */
  .data-table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
  }}
  .data-table th {{
    text-align: left;
    padding: 10px 14px;
    font-size: 11px;
    color: var(--text3);
    text-transform: uppercase;
    letter-spacing: 0.6px;
    font-weight: 600;
    border-bottom: 1px solid var(--border);
    background: var(--surface);
  }}
  .data-table tr {{ border-bottom: 1px solid rgba(255,255,255,0.04); }}
  .data-table tr:hover td {{ background: rgba(255,255,255,0.03); }}
  .data-table td {{ padding: 10px 14px; vertical-align: middle; }}
  .rank-cell {{ color: var(--text3); font-family: var(--mono); font-size: 12px; width: 40px; }}
  .name-cell {{ font-weight: 600; }}
  .stock-name {{ margin-right: 6px; }}
  .market-badge {{
    font-size: 9px; font-weight: 700; padding: 2px 5px;
    border-radius: 4px; text-transform: uppercase; letter-spacing: 0.3px;
  }}
  .market-badge.kospi {{ background: rgba(108,108,255,0.2); color: var(--accent2); }}
  .market-badge.kosdaq {{ background: rgba(77,184,255,0.2); color: var(--mild); }}
  .sector-cell {{ color: var(--text2); font-size: 12px; }}
  .price-cell {{ font-family: var(--mono); font-weight: 600; }}
  .change-cell {{ font-family: var(--mono); font-weight: 700; }}
  .change-cell.up {{ color: var(--up); }}
  .change-cell.down {{ color: var(--down); }}
  .change-cell.flat {{ color: var(--flat); }}
  .amount-cell {{ font-family: var(--mono); font-weight: 600; color: var(--accent2); }}

  /* ── Stock Chips ── */
  .chip-grid {{
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
  }}
  .stock-chip {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 8px 12px;
    display: flex;
    align-items: center;
    gap: 8px;
    transition: border-color 0.2s;
  }}
  .stock-chip:hover {{ border-color: var(--border2); }}
  .chip-name {{ font-size: 13px; font-weight: 600; color: var(--text); }}
  .chip-pct {{ font-size: 12px; font-weight: 700; font-family: var(--mono); }}
  .chip-pct.up {{ color: var(--up); }}
  .chip-pct.down {{ color: var(--down); }}
  .chip-sector {{ font-size: 10px; color: var(--text3); }}
  .upper-chip {{
    background: rgba(255,215,0,0.08);
    border: 1px solid rgba(255,215,0,0.2);
    border-radius: 10px;
    padding: 8px 12px;
    display: flex; align-items: center; gap: 8px;
  }}

  /* ── Rotation Signal ── */
  .rotation-box {{
    border-radius: var(--radius);
    padding: 20px 24px;
    border: 1px solid var(--border);
    display: flex;
    align-items: flex-start;
    gap: 16px;
  }}
  .rotation-alert {{ background: rgba(255,107,43,0.1); border-color: rgba(255,107,43,0.3); }}
  .rotation-up {{ background: rgba(0,217,126,0.08); border-color: rgba(0,217,126,0.25); }}
  .rotation-down {{ background: rgba(255,77,109,0.08); border-color: rgba(255,77,109,0.25); }}
  .rotation-neutral {{ background: var(--surface); }}
  .rot-icon {{ font-size: 32px; flex-shrink: 0; line-height: 1; }}
  .rot-content h3 {{ font-size: 16px; font-weight: 700; color: var(--text); margin-bottom: 6px; }}
  .rot-content p {{ font-size: 13px; color: var(--text2); }}

  /* ── 2-col layout ── */
  .two-col {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 24px;
  }}
  .card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 24px;
    overflow: hidden;
  }}

  .empty-state {{ color: var(--text3); font-size: 13px; padding: 16px 0; }}

  /* ── Footer ── */
  .footer {{
    background: var(--bg2);
    border-top: 1px solid var(--border);
    padding: 24px 48px;
    text-align: center;
    font-size: 12px;
    color: var(--text3);
  }}
  .footer strong {{ color: var(--text2); }}

  /* ── Responsive ── */
  @media (max-width: 900px) {{
    .header, .kpi-grid, .main {{ padding-left: 20px; padding-right: 20px; }}
    .bar-row {{ grid-template-columns: 150px 1fr; }}
    .bar-meta {{ display: none; }}
    .two-col {{ grid-template-columns: 1fr; }}
  }}
  @media (max-width: 600px) {{
    .date-main {{ font-size: 20px; }}
    .lead-grid {{ grid-template-columns: 1fr 1fr; }}
  }}

  /* ── Animations ── */
  @keyframes fadeUp {{
    from {{ opacity: 0; transform: translateY(12px); }}
    to {{ opacity: 1; transform: translateY(0); }}
  }}
  .kpi-card, .lead-card, .rotation-box {{
    animation: fadeUp 0.4s ease both;
  }}
</style>
</head>
<body>

<!-- ── HEADER ── -->
<header class="header">
  <div class="header-top">
    <div class="header-brand">
      <div class="brand-logo">📊</div>
      <div class="brand-text">
        <h1>Korea Market Daily</h1>
        <p>한국 증시 일간 분석 리포트</p>
      </div>
    </div>
    <div class="header-date">
      <div class="date-main">{date_display}</div>
      <div class="date-sub">장 마감 기준 · 16:05 자동 생성</div>
    </div>
  </div>
  <div class="summary-banner">
    <p>{summary}</p>
  </div>
</header>

<!-- ── KPI ── -->
<div class="kpi-grid">
  <div class="kpi-card">
    <div class="kpi-label">총 거래대금 (TOP300)</div>
    <div class="kpi-value accent">{fmt_amt(total_amount)}</div>
    <div class="kpi-sub">거래대금 상위 300개 종목 합산</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-label">52주 신고가</div>
    <div class="kpi-value up">{high_total}개</div>
    <div class="kpi-sub">KOSPI + KOSDAQ 합산</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-label">상한가 종목</div>
    <div class="kpi-value hot">{upper_total}개</div>
    <div class="kpi-sub">+30% 가격 제한 도달</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-label">1위 주도섹터</div>
    <div class="kpi-value gold">{leading[0]['sector'] if leading else '-'}</div>
    <div class="kpi-sub">강도점수 {leading[0]['sector_score']:.1f}pts</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-label">섹터 수</div>
    <div class="kpi-value accent">{len(sectors)}</div>
    <div class="kpi-sub">활성 섹터</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-label">전일 비교</div>
    <div class="kpi-value" style="font-size:16px;color:var(--text2);">{prev_display}</div>
    <div class="kpi-sub">이전 거래일</div>
  </div>
</div>

<!-- ── MAIN ── -->
<main class="main">

  <!-- 주도섹터 -->
  <section class="section">
    <div class="section-header">
      <h2 class="section-title">🏆 주도섹터 TOP5</h2>
      <span class="section-badge">섹터 강도 점수 기준</span>
    </div>
    <div class="lead-grid">
      {leading_cards}
    </div>
  </section>

  <!-- 섹터 강도 차트 -->
  <section class="section">
    <div class="section-header">
      <h2 class="section-title">📊 섹터별 강도 분석</h2>
      <span class="section-badge">거래대금·신고가·상한가 종합</span>
    </div>
    <div class="card">
      <div class="bar-chart">
        {chart_bars}
      </div>
    </div>
  </section>

  <!-- 순환매 탐지 -->
  <section class="section">
    <div class="section-header">
      <h2 class="section-title">🔄 순환매 탐지</h2>
      <span class="section-badge">전일 대비 섹터 강도 변화</span>
    </div>
    <div class="rotation-box {rot_cls}">
      <div class="rot-icon">{rot_icon}</div>
      <div class="rot-content">
        <h3>{rot_signal}</h3>
        <p>{rot_detail if rot_detail else '전일 대비 섹터 이동 데이터를 기반으로 분석됩니다.'}</p>
      </div>
    </div>
  </section>

  <!-- 거래대금 TOP20 -->
  <section class="section">
    <div class="section-header">
      <h2 class="section-title">💰 거래대금 TOP20</h2>
      <span class="section-badge">당일 거래대금 기준 순위</span>
    </div>
    <div class="card" style="padding:0;overflow:hidden;">
      <table class="data-table">
        <thead>
          <tr>
            <th>#</th>
            <th>종목</th>
            <th>섹터</th>
            <th>종가</th>
            <th>등락률</th>
            <th>거래대금</th>
          </tr>
        </thead>
        <tbody>{volume_rows}</tbody>
      </table>
    </div>
  </section>

  <!-- 신고가 + 상한가 -->
  <div class="two-col">
    <section class="section" style="margin-bottom:0">
      <div class="section-header">
        <h2 class="section-title">📍 52주 신고가</h2>
        <span class="section-badge">{high_total}개</span>
      </div>
      <div class="card">
        <div class="chip-grid">{high_grid}</div>
      </div>
    </section>

    <section class="section" style="margin-bottom:0">
      <div class="section-header">
        <h2 class="section-title">🔝 상한가 종목</h2>
        <span class="section-badge">{upper_total}개</span>
      </div>
      <div class="card">
        <div class="chip-grid">{upper_grid}</div>
      </div>
    </section>
  </div>

</main>

<!-- ── FOOTER ── -->
<footer class="footer">
  <p><strong>Korea Market Daily Report</strong> · {date_kor} · 자동 생성 시스템</p>
  <p style="margin-top:6px;">데이터 출처: RiccoRank, 네이버 금융 · 본 리포트는 투자 참고용이며 투자 결정의 책임은 본인에게 있습니다</p>
</footer>

</body>
</html>"""

    # 파일 저장
    filename = f"korea_daily_report_{date_str.replace('-', '')}.html"
    filepath = os.path.join(output_dir, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"[Report] Saved: {filepath}")
    return filepath


def generate_report_for_date(target_date: str = None, output_dir: str = None) -> str:
    """날짜별 리포트 생성 (분석 포함)"""
    data = run_analysis(target_date)
    if not data:
        raise ValueError(f"No data for {target_date}")
    return generate_report(data, output_dir)


if __name__ == "__main__":
    import sys
    target = sys.argv[1] if len(sys.argv) > 1 else None
    path = generate_report_for_date(target)
    print(f"\n✅ Report generated: {path}")
