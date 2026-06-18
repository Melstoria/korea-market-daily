import os
import glob
from datetime import datetime

OUTPUT_DIR = os.environ.get("OUTPUT_DIR", os.path.join(os.path.dirname(__file__), "../docs/reports"))
DOCS_DIR = os.path.join(os.path.dirname(__file__), "../docs")

def update_index():
    reports = sorted(
        glob.glob(os.path.join(OUTPUT_DIR, "korea_daily_report_*.html")),
        reverse=True
    )
    items = ""
    for path in reports:
        fname = os.path.basename(path)
        date_str = fname.replace("korea_daily_report_","").replace(".html","")
        date_fmt = f"{date_str[:4]}.{date_str[4:6]}.{date_str[6:]}"
        items += f'<li><a href="reports/{fname}">📊 {date_fmt} 일간 리포트</a></li>\n'

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Korea Market Hub</title>
<style>
  body {{ font-family: -apple-system, sans-serif; background:#0a0a0f; color:#e8e8f0;
          max-width:800px; margin:0 auto; padding:40px 20px; }}
  h1 {{ font-size:28px; margin-bottom:8px; }}
  p {{ color:#9090a8; margin-bottom:32px; }}
  ul {{ list-style:none; padding:0; }}
  li {{ margin-bottom:12px; }}
  a {{ color:#6c6cff; text-decoration:none; font-size:16px; }}
  a:hover {{ color:#8080ff; }}
  .updated {{ font-size:12px; color:#5a5a72; margin-top:40px; }}
</style>
</head>
<body>
<h1>🇰🇷 Korea Market Hub</h1>
<p>한국 증시 일간 분석 리포트</p>
<ul>{items}</ul>
<p class="updated">Updated: {datetime.now().strftime('%Y-%m-%d %H:%M')} KST</p>
</body>
</html>"""

    os.makedirs(DOCS_DIR, exist_ok=True)
    with open(os.path.join(DOCS_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[Index] Updated with {len(reports)} reports")

if __name__ == "__main__":
    update_index()
