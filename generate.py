#!/usr/bin/env python3
"""
ACCR - Job Application Tracker
Cron script: fetches Gmail emails, generates static HTML, pushes to GitHub.
Runs in Maton sandbox where MATON_API_KEY is available.
"""
import urllib.request, os, json, base64, re, time
from datetime import datetime

MATON_KEY = os.environ["MATON_API_KEY"]
GMAIL_CONN = "78ff6d67-4e32-4dd8-934a-8add7240090f"
GH_CONN = "d0d2040a-4044-403b-ad61-b3a83b93e25f"
REPO = "art992398-lgtm/ACCR"

# ── Gmail helpers ──────────────────────────────────────────────────────────────

def gmail(path):
    req = urllib.request.Request(f"https://api.maton.ai/google-mail/gmail/v1/users/me/{path}")
    req.add_header("Authorization", f"Bearer {MATON_KEY}")
    req.add_header("Maton-Connection", GMAIL_CONN)
    return json.load(urllib.request.urlopen(req))

def decode_b64(data):
    if not data: return ""
    return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="ignore")

def extract_body(p, prefer_html=False):
    mime = p.get("mimeType", "")
    has_data = bool(p.get("body", {}).get("data"))
    if mime == "text/plain" and has_data and not prefer_html:
        return decode_b64(p["body"]["data"])
    if mime == "text/html" and has_data:
        return re.sub(r"<[^>]+>", " ", decode_b64(p["body"]["data"]))
    for part in p.get("parts", []):
        r = extract_body(part)
        if r: return r
    # No text/plain found — retry accepting HTML
    if mime == "text/plain" and has_data:
        return decode_b64(p["body"]["data"])
    return ""

def clean(text):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text)).strip()

# ── Parsing ────────────────────────────────────────────────────────────────────

def fmt_date(d):
    try:
        dt = datetime.strptime(re.sub(r"\s*\(.*\)", "", d).strip(), "%a, %d %b %Y %H:%M:%S %z")
        return dt.strftime("%-d %b %Y"), dt.timestamp()
    except:
        return d[:15], 0

def parse_one(e):
    s, sub, body = e["sender"], e["subject"], e["body"]
    date_str, ts = fmt_date(e["date"])
    r = dict(date=date_str, ts=ts, company="", position="", source="", category="", status="")

    if "jobbkk.com" in s:
        r["source"] = "JOBBKK"
        if "apply@jobbkk.com" in s:
            r["category"], r["status"] = "sent", "applied"
            m = re.search(r"Application letter in\s+(.+)", sub)
            if m: r["position"] = m.group(1).strip()
            m2 = re.search(r"เรียน\s+(.+?)\s+(?:ดิฉัน|ผม)", body)
            if not m2: m2 = re.search(r"เรียน\s+([^,\n\r]+),", body)
            if m2: r["company"] = m2.group(1).strip()
        else:
            r["category"] = "newsletter"

    elif "jobthai.com" in s:
        r["source"] = "JobThai"
        if "upload-file@application.jobthai.com" in s:
            r["category"], r["status"] = "sent", "applied"
            m = re.search(r"ใบสมัครตำแหน่ง\s+(.+?)\s+ถูกส่งถึง\s+(.+?)\s+แล้ว", sub)
            if m: r["position"], r["company"] = m.group(1).strip(), m.group(2).strip()
        else:
            r["category"] = "newsletter"

    elif "jobsdb.com" in s:
        r["source"] = "Jobsdb"
        if "ส่งใบสมัครของคุณเรียบร้อยแล้ว" in sub:
            r["category"], r["status"] = "sent", "applied"
            m = re.search(r"ตำแหน่งงาน\s+(.+?)\s+ไปยัง\s+(.+?)\s+เรียบร้อย", body)
            if not m: m = re.search(r"ใบสมัครงานตำแหน่ง\s+(.+?)\s+ของคุณถูกส่งไปยัง\s+(.+?)\s+เรียบร้อย", body)
            if m: r["position"], r["company"] = m.group(1).strip(), m.group(2).strip()
        elif "ได้ดูใบสมัครของคุณสำหรับ" in sub:
            r["category"], r["status"] = "response", "viewed"
            m = re.search(r"^(.+?)\s+ได้ดูใบสมัครของคุณสำหรับ\s+(.+)$", sub)
            if m: r["company"], r["position"] = m.group(1).strip(), m.group(2).strip()
        elif "กิจกรรมใหม่" in sub or "นัดสัมภาษณ์" in sub:
            r["category"] = "response"
            r["status"] = "interview" if "นัดสัมภาษณ์" in sub else "activity"
        else:
            r["category"] = "newsletter"
    return r

COMPANY_INFO = {
    "PHITHAN LEASING CO., LTD.": {
        "industry": "การเงิน / สินเชื่อเช่าซื้อ",
        "summary": "บริษัทให้บริการสินเชื่อเช่าซื้อและลีสซิ่ง เน้นรถยนต์และเครื่องจักร มีสาขาทั่วประเทศ",
        "tips": "เตรียมพูดถึงประสบการณ์กับระบบ Backend / Database เพราะงานเน้นระบบ Back-office ขององค์กรการเงิน",
    },
    "NILECON (THAILAND) CO., LTD.": {
        "industry": "IT / Mobile Application",
        "summary": "บริษัทด้าน IT Solution และ Mobile Application Development ในไทย งานที่สมัครคือ React Native Developer",
        "tips": "เตรียมพูดถึง React Native, TypeScript, การ integrate API เข้า Mobile App และ Portfolio โปรเจกต์ Mobile",
    },
    "บริษัท ศิริวัฒนา อินเตอร์พริ้นท์ จำกัด (มหาชน)": {
        "industry": "สื่อสิ่งพิมพ์ / บรรจุภัณฑ์",
        "summary": "บริษัทมหาชนด้านการพิมพ์และบรรจุภัณฑ์ จดทะเบียนในตลาดหลักทรัพย์ MAI มีโรงงานผลิตขนาดใหญ่",
        "tips": "งานน่าจะเน้น ERP / ระบบ MRP สำหรับโรงงาน ควรพูดถึงประสบการณ์กับ Database หรือ Business Logic",
    },
    "บริษัท โสมาภา อินฟอร์เมชั่น เทคโนโลยี จำกัด (มหาชน)": {
        "industry": "IT Services / Software House",
        "summary": "บริษัทพัฒนา Software และ IT Solutions สำหรับธุรกิจ จดทะเบียนในตลาดหลักทรัพย์ MAI",
        "tips": "Software House มักมีโปรเจกต์หลากหลาย ควรพูดถึง Stack ที่ใช้คล่องและความสามารถเรียนรู้เทคโนโลยีใหม่",
    },
    "บริษัท อินเทอร์เน็ตประเทศไทย จำกัด (มหาชน)": {
        "industry": "Telecommunications / ISP / Cloud",
        "summary": "INET เป็นผู้ให้บริการ Internet, Data Center และ Cloud ชั้นนำ เป็นรัฐวิสาหกิจในเครือ NECTEC/NSTDA",
        "tips": "บริษัทใหญ่มั่นคง ควรพูดถึง Networking, Cloud, Linux/Server Admin และ Security Awareness",
    },
    "Maholan Co., Ltd.": {
        "industry": "Tech Startup",
        "summary": "Startup เทคโนโลยีไทย พัฒนา Platform ออนไลน์ งานที่สมัครคือ Fullstack Developer",
        "tips": "Startup ต้องการคนทำได้ครอบคลุม Frontend + Backend เตรียม Portfolio และ Side Project",
    },
    "Future Makers Co., Ltd.": {
        "industry": "Technology / Digital Products",
        "summary": "บริษัทพัฒนา Digital Products งานที่สมัครคือ Full Stack Javascript Developer (Node.js + React)",
        "tips": "เตรียมพูดถึง Node.js, React/Vue, REST API, Database และ Git workflow",
    },
    "AZTEK CO., LTD.": {
        "industry": "IT / Software Development",
        "summary": "บริษัทพัฒนา Software Solutions งานที่สมัครคือ Full Stack Developer",
        "tips": "เตรียม Portfolio Full Stack ครบวงจร และพูดถึงกระบวนการพัฒนาตั้งแต่ต้นจนปล่อยระบบ",
    },
    "บริษัท คอนเวอร์เจนซ์ เทคโนโลยี จำกัด (Convergence Technology Co.Ltd.)": {
        "industry": "IT Solutions / System Integrator",
        "summary": "บริษัท IT Solutions ให้บริการพัฒนาระบบและวางโครงสร้าง IT ให้กับองค์กรต่างๆ",
        "tips": "เตรียมพูดถึง Frontend/Backend ที่ใช้จริง และ Project ที่เคยทำงานร่วมกับทีม",
    },
    "TECHINVENT CO., LTD.": {
        "industry": "Technology / Innovation",
        "summary": "บริษัทเทคโนโลยีเน้นนวัตกรรม งานที่สมัครคือ Programmer/โปรแกรมเมอร์",
        "tips": "เตรียมพูดถึง Programming Language ที่ถนัดและโปรเจกต์ที่ผ่านมา",
    },
}

# ── Fetch all emails ───────────────────────────────────────────────────────────

def fetch_all():
    queries = [
        "from:(apply@jobbkk.com OR jobbkk.com)",
        "from:(jobthai.com)",
        "from:(jobsdb.com)",
    ]
    seen, ids = set(), []
    for q in queries:
        data = gmail(f"messages?maxResults=50&q={urllib.request.quote(q)}")
        for m in data.get("messages", []):
            if m["id"] not in seen:
                seen.add(m["id"]); ids.append(m["id"])
    emails = []
    for mid in ids:
        try:
            msg = gmail(f"messages/{mid}?format=full")
            pl = msg.get("payload", {})
            hdrs = {h["name"]: h["value"] for h in pl.get("headers", [])}
            body = clean(extract_body(pl))[:2000]
            emails.append(dict(id=mid, subject=hdrs.get("Subject",""),
                               sender=hdrs.get("From",""), date=hdrs.get("Date",""), body=body))
        except:
            pass
        time.sleep(0.12)
    return emails

# ── HTML generation ────────────────────────────────────────────────────────────

def esc(s):
    return (s or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"','&quot;')

def info_section(info):
    if not info: return ""
    return f"""
    <div class="info-section">
      <div class="info-toggle" onclick="this.parentElement.classList.toggle('open')">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
        ข้อมูลบริษัท / เตรียมสัมภาษณ์
        <svg class="arrow" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"/></svg>
      </div>
      <div class="info-content">
        <div class="info-block">
          <div class="info-label">เกี่ยวกับบริษัท</div>
          <div class="info-text">{esc(info.get('summary',''))}</div>
        </div>
        <div class="info-block tip">
          <div class="info-label">เคล็ดลับสัมภาษณ์</div>
          <div class="info-text">{esc(info.get('tips',''))}</div>
        </div>
      </div>
    </div>"""

BADGE = {
    "JOBBKK": '<span class="badge badge-blue">JOBBKK</span>',
    "JobThai": '<span class="badge badge-green">JobThai</span>',
    "Jobsdb": '<span class="badge badge-orange">Jobsdb</span>',
}
STATUS_BADGE = {
    "viewed": '<span class="status-badge viewed">เปิดดูใบสมัคร</span>',
    "activity": '<span class="status-badge activity">กิจกรรมใหม่</span>',
    "interview": '<span class="status-badge interview">นัดสัมภาษณ์</span>',
}

def sent_card(e, info):
    badge = BADGE.get(e["source"], '<span class="badge badge-gray">Other</span>')
    industry = info.get("industry","") if info else ""
    q = urllib.request.quote((e["company"]+" "+e["position"]).strip())
    return f"""
    <div class="card {'has-info' if info else ''}" data-company="{esc(e['company']).lower()}" data-position="{esc(e['position']).lower()}" data-source="{esc(e['source'])}">
      <div class="card-header">
        <div class="card-left">{badge}<span class="card-date">{esc(e['date'])}</span></div>
        <a href="https://www.google.com/search?q={q}" target="_blank" class="search-btn">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>ค้นหา
        </a>
      </div>
      <div class="card-company">{esc(e['company'])}</div>
      <div class="card-position">{esc(e['position'])}</div>
      {f'<div class="card-industry"><span>{esc(industry)}</span></div>' if industry else ""}
      {info_section(info)}
    </div>"""

def response_card(e, info):
    badge = STATUS_BADGE.get(e["status"], '<span class="status-badge">อัพเดต</span>')
    extra = "card-interview" if e["status"] == "interview" else ""
    q = urllib.request.quote((e["company"]+" "+e.get("position","")).strip())
    return f"""
    <div class="card response-card {extra}">
      <div class="card-header">
        <div class="card-left">{badge}<span class="card-date">{esc(e['date'])}</span></div>
        <a href="https://www.google.com/search?q={q}" target="_blank" class="search-btn">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>ค้นหา
        </a>
      </div>
      <div class="card-company">{esc(e['company'])}</div>
      {f'<div class="card-position">{esc(e.get("position",""))}</div>' if e.get("position") else ""}
      {info_section(info)}
    </div>"""

def build_html(sent, resp, updated_at):
    sent_cards = "\n".join([sent_card(e, COMPANY_INFO.get(e["company"])) for e in sent])
    resp_cards = "\n".join([response_card(e, COMPANY_INFO.get(e["company"])) for e in resp])
    n_viewed = len([r for r in resp if r["status"] == "viewed"])
    n_interview = len([r for r in resp if r["status"] == "interview"])

    return f"""<!DOCTYPE html>
<html lang="th">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ACCR - ติดตามการสมัครงาน</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  :root{{--bg:#0f1117;--surface:#1a1d2e;--surface2:#242738;--border:#2e3150;--text:#e2e8f0;--muted:#8892a4;--blue:#6366f1;--blue-l:#818cf8;--green:#10b981;--orange:#f59e0b;--purple:#8b5cf6;--cyan:#06b6d4}}
  body{{background:var(--bg);color:var(--text);font-family:'Segoe UI',-apple-system,BlinkMacSystemFont,'Noto Sans Thai',sans-serif;font-size:14px;line-height:1.6;min-height:100vh}}
  .header{{background:linear-gradient(135deg,#1a1d2e,#242738);border-bottom:1px solid var(--border);padding:24px 32px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px}}
  .header h1{{font-size:22px;font-weight:700;letter-spacing:-.3px}} .header h1 span{{color:var(--blue-l)}}
  .header-sub{{color:var(--muted);font-size:13px;margin-top:4px}}
  .stats{{display:flex;gap:16px;padding:20px 32px;background:var(--surface);border-bottom:1px solid var(--border);flex-wrap:wrap}}
  .stat-card{{flex:1;min-width:110px;background:var(--surface2);border:1px solid var(--border);border-radius:10px;padding:14px 18px}}
  .stat-num{{font-size:28px;font-weight:700;line-height:1}} .stat-label{{color:var(--muted);font-size:12px;margin-top:3px}}
  .blue .stat-num{{color:var(--blue-l)}} .green .stat-num{{color:var(--green)}} .orange .stat-num{{color:var(--orange)}} .purple .stat-num{{color:var(--purple)}}
  .main{{padding:24px 32px;max-width:1400px;margin:0 auto}}
  .tabs{{display:flex;gap:4px;margin-bottom:20px;background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:4px;width:fit-content}}
  .tab{{padding:8px 20px;border-radius:7px;cursor:pointer;font-size:13px;font-weight:500;color:var(--muted);border:none;background:none;transition:all .15s}}
  .tab.active{{background:var(--blue);color:#fff}} .tab:hover:not(.active){{background:var(--surface2);color:var(--text)}}
  .toolbar{{display:flex;gap:10px;margin-bottom:20px;align-items:center;flex-wrap:wrap}}
  .search-input{{flex:1;min-width:200px;max-width:360px;background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:9px 14px 9px 36px;color:var(--text);font-size:13px;outline:none;background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='15' height='15' viewBox='0 0 24 24' fill='none' stroke='%238892a4' stroke-width='2'%3E%3Ccircle cx='11' cy='11' r='8'/%3E%3Cpath d='m21 21-4.35-4.35'/%3E%3C/svg%3E");background-repeat:no-repeat;background-position:12px center}}
  .search-input:focus{{border-color:var(--blue)}}
  .filter-select{{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:9px 14px;color:var(--text);font-size:13px;outline:none;cursor:pointer}}
  .count-label{{color:var(--muted);font-size:13px;margin-left:auto}}
  .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px}}
  .card{{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:16px;transition:border-color .15s,transform .1s}}
  .card:hover{{border-color:#454a6b;transform:translateY(-1px)}}
  .has-info{{border-left:3px solid var(--blue)}} .response-card{{border-left:3px solid var(--green)}} .card-interview{{border-left:3px solid var(--orange)!important}}
  .card-header{{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px}}
  .card-left{{display:flex;align-items:center;gap:8px;flex-wrap:wrap}}
  .badge{{font-size:10px;font-weight:600;padding:2px 8px;border-radius:20px;letter-spacing:.3px;text-transform:uppercase}}
  .badge-blue{{background:rgba(99,102,241,.15);color:#a5b4fc;border:1px solid rgba(99,102,241,.3)}}
  .badge-green{{background:rgba(16,185,129,.15);color:#6ee7b7;border:1px solid rgba(16,185,129,.3)}}
  .badge-orange{{background:rgba(245,158,11,.15);color:#fcd34d;border:1px solid rgba(245,158,11,.3)}}
  .badge-gray{{background:rgba(148,163,184,.1);color:#94a3b8;border:1px solid rgba(148,163,184,.2)}}
  .status-badge{{font-size:11px;font-weight:600;padding:3px 10px;border-radius:20px}}
  .status-badge.viewed{{background:rgba(16,185,129,.15);color:#6ee7b7;border:1px solid rgba(16,185,129,.3)}}
  .status-badge.activity{{background:rgba(139,92,246,.15);color:#c4b5fd;border:1px solid rgba(139,92,246,.3)}}
  .status-badge.interview{{background:rgba(245,158,11,.15);color:#fcd34d;border:1px solid rgba(245,158,11,.3)}}
  .card-date{{font-size:11px;color:var(--muted)}}
  .card-company{{font-size:14px;font-weight:600;margin-bottom:4px;line-height:1.4}}
  .card-position{{font-size:13px;color:var(--cyan);margin-bottom:6px}}
  .card-industry{{margin-bottom:8px}} .card-industry span{{font-size:11px;color:var(--muted);background:rgba(255,255,255,.05);padding:2px 8px;border-radius:4px}}
  .search-btn{{display:flex;align-items:center;gap:4px;font-size:11px;color:var(--muted);text-decoration:none;padding:4px 8px;border-radius:6px;border:1px solid var(--border);transition:all .15s;white-space:nowrap}}
  .search-btn:hover{{color:var(--text);border-color:#454a6b;background:var(--surface2)}}
  .info-section{{margin-top:10px;border-top:1px solid var(--border);padding-top:10px}}
  .info-toggle{{display:flex;align-items:center;gap:6px;cursor:pointer;color:var(--blue-l);font-size:12px;font-weight:500;padding:4px 0;user-select:none}}
  .info-toggle:hover{{color:#fff}} .info-toggle .arrow{{margin-left:auto;transition:transform .2s}}
  .info-section.open .arrow{{transform:rotate(180deg)}} .info-content{{display:none;padding-top:10px}} .info-section.open .info-content{{display:block}}
  .info-block{{margin-bottom:10px}} .info-block:last-child{{margin-bottom:0}}
  .info-label{{font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.5px;color:var(--muted);margin-bottom:4px}}
  .info-block.tip .info-label{{color:#fbbf24}} .info-text{{font-size:12.5px;color:#c8d3e0;line-height:1.6}}
  .tab-content{{display:none}} .tab-content.active{{display:block}}
  .empty{{text-align:center;padding:60px;color:var(--muted)}}
  @media(max-width:600px){{.header,.stats,.main{{padding:16px}}.grid{{grid-template-columns:1fr}}}}
</style>
</head>
<body>
<div class="header">
  <div>
    <h1>ACCR <span>ติดตามการสมัครงาน</span></h1>
    <div class="header-sub">Gmail: art992398@gmail.com</div>
    <div style="font-size:11px;color:var(--muted);margin-top:2px">อัพเดตล่าสุด: {updated_at}</div>
  </div>
</div>
<div class="stats">
  <div class="stat-card blue"><div class="stat-num">{len(sent)}</div><div class="stat-label">ส่งใบสมัครแล้ว</div></div>
  <div class="stat-card green"><div class="stat-num">{len(resp)}</div><div class="stat-label">บริษัทตอบกลับ</div></div>
  <div class="stat-card orange"><div class="stat-num">{n_viewed}</div><div class="stat-label">เปิดดูใบสมัคร</div></div>
  <div class="stat-card purple"><div class="stat-num">{n_interview}</div><div class="stat-label">นัดสัมภาษณ์</div></div>
</div>
<div class="main">
  <div class="tabs">
    <button class="tab active" onclick="switchTab('sent',this)">ส่งใบสมัครแล้ว ({len(sent)})</button>
    <button class="tab" onclick="switchTab('response',this)">บริษัทติดต่อกลับ ({len(resp)})</button>
  </div>
  <div class="tab-content active" id="tab-sent">
    <div class="toolbar">
      <input class="search-input" type="text" placeholder="ค้นหาบริษัท หรือตำแหน่งงาน..." oninput="filterSent(this.value)" id="search-sent">
      <select class="filter-select" onchange="filterSource(this.value)">
        <option value="">แหล่งที่มาทั้งหมด</option>
        <option value="JOBBKK">JOBBKK</option>
        <option value="JobThai">JobThai</option>
        <option value="Jobsdb">Jobsdb</option>
      </select>
      <span class="count-label" id="sent-count">{len(sent)} รายการ</span>
    </div>
    <div class="grid" id="grid-sent">{sent_cards}</div>
  </div>
  <div class="tab-content" id="tab-response">
    {"<div class='grid'>"+resp_cards+"</div>" if resp else "<div class='empty'>ยังไม่มีบริษัทติดต่อกลับ</div>"}
  </div>
</div>
<script>
let activeSource='';
function switchTab(n,btn){{document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));document.querySelectorAll('.tab-content').forEach(t=>t.classList.remove('active'));btn.classList.add('active');document.getElementById('tab-'+n).classList.add('active');}}
function filterSent(q){{const ql=q.toLowerCase();const cards=document.querySelectorAll('#grid-sent .card');let v=0;cards.forEach(c=>{{const ok=(!ql||c.dataset.company.includes(ql)||c.dataset.position.includes(ql))&&(!activeSource||c.dataset.source===activeSource);c.style.display=ok?'':'none';if(ok)v++;}});document.getElementById('sent-count').textContent=v+' รายการ';}}
function filterSource(s){{activeSource=s;filterSent(document.getElementById('search-sent').value);}}
</script>
</body>
</html>"""

# ── GitHub push ────────────────────────────────────────────────────────────────

def gh_put(filepath_repo, content_bytes, message):
    req = urllib.request.Request(f"https://api.maton.ai/github/repos/{REPO}/contents/{filepath_repo}")
    req.add_header("Authorization", f"Bearer {MATON_KEY}")
    req.add_header("Maton-Connection", GH_CONN)
    req.add_header("Content-Type", "application/json")
    req.method = "PUT"
    # Get existing SHA
    try:
        get_req = urllib.request.Request(f"https://api.maton.ai/github/repos/{REPO}/contents/{filepath_repo}")
        get_req.add_header("Authorization", f"Bearer {MATON_KEY}")
        get_req.add_header("Maton-Connection", GH_CONN)
        existing = json.load(urllib.request.urlopen(get_req))
        sha = existing.get("sha")
    except:
        sha = None
    body = {"message": message, "content": base64.b64encode(content_bytes).decode(), "branch": "main"}
    if sha: body["sha"] = sha
    req.data = json.dumps(body).encode()
    r = json.load(urllib.request.urlopen(req))
    return r.get("content", {}).get("html_url", "")

# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    print("Fetching emails...")
    raw = fetch_all()
    parsed = [parse_one(e) for e in raw]

    sent = sorted([p for p in parsed if p["category"] == "sent" and p["company"]], key=lambda x: -x["ts"])
    resp = sorted([p for p in parsed if p["category"] == "response"], key=lambda x: -x["ts"])

    print(f"Sent: {len(sent)}, Response: {len(resp)}")

    updated_at = datetime.now().strftime("%-d %b %Y %H:%M น.")
    html = build_html(sent, resp, updated_at)

    print("Pushing to GitHub...")
    url = gh_put("public/index.html", html.encode("utf-8"), f"Auto-update: {updated_at}")
    print("Done:", url)

if __name__ == "__main__":
    main()
