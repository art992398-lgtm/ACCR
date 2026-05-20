#!/usr/bin/env python3
"""
ACCR - Job Application Tracker
Cron script: fetches Gmail emails, generates static HTML, pushes to GitHub.
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

def extract_body(p):
    mime = p.get("mimeType", "")
    has_data = bool(p.get("body", {}).get("data"))
    if mime == "text/plain" and has_data:
        return decode_b64(p["body"]["data"])
    if mime == "text/html" and has_data:
        return re.sub(r"<[^>]+>", " ", decode_b64(p["body"]["data"]))
    for part in p.get("parts", []):
        r = extract_body(part)
        if r: return r
    return ""

def clean(text):
    return re.sub(r"\s+", " ", text).strip()

# ── Email parsing ──────────────────────────────────────────────────────────────

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

# ── Company database ───────────────────────────────────────────────────────────

COMPANY_INFO = {
    # ── Responded ──────────────────────────────────────────────────────────────
    "PHITHAN LEASING CO., LTD.": {
        "th": "บริษัท พิธาน ลิสซิ่ง จำกัด",
        "domain": "phithanleasing.co.th",
        "industry": "การเงิน / สินเชื่อ",
        "size": "500–1,000 คน",
        "hq": "กรุงเทพฯ",
        "about": "บริษัทสินเชื่อเช่าซื้อและลีสซิ่งชั้นนำของไทย ให้บริการสินเชื่อรถยนต์ เครื่องจักรอุตสาหกรรม และอุปกรณ์ธุรกิจ มีเครือข่ายสาขาและตัวแทนทั่วประเทศ",
        "stack": ["Oracle", "SQL Server", "Java", "Web App"],
        "tips": "งาน Programmer ที่นี่เน้น Back-office และระบบ ERP/สินเชื่อ เตรียมพูดถึง SQL, ระบบฐานข้อมูล, และประสบการณ์กับ Business Logic ด้านการเงิน",
    },
    "NILECON (THAILAND) CO., LTD.": {
        "th": "บริษัท ไนลคอน (ประเทศไทย) จำกัด",
        "domain": "nilecon.co.th",
        "industry": "IT Solutions / Mobile App",
        "size": "50–200 คน",
        "hq": "กรุงเทพฯ",
        "about": "บริษัท IT Solutions พัฒนา Mobile Application และระบบซอฟต์แวร์สำหรับองค์กร ลูกค้าทั้งภาครัฐและเอกชน งานที่เปิดรับคือ React Native Developer",
        "stack": ["React Native", "TypeScript", "Node.js", "REST API"],
        "tips": "เน้น React Native + TypeScript เตรียม Portfolio โปรเจกต์ Mobile App และพูดถึงการ debug performance บน iOS/Android",
    },
    # ── JobThai ─────────────────────────────────────────────────────────────────
    "บริษัท ศิริวัฒนา อินเตอร์พริ้นท์ จำกัด (มหาชน)": {
        "th": "บริษัท ศิริวัฒนา อินเตอร์พริ้นท์ จำกัด (มหาชน)",
        "domain": "siriwattana.co.th",
        "industry": "สื่อสิ่งพิมพ์ / บรรจุภัณฑ์",
        "size": "1,000–5,000 คน",
        "hq": "กรุงเทพฯ",
        "listed": "SET: SVOA",
        "about": "บริษัทมหาชนด้านการพิมพ์และบรรจุภัณฑ์ครบวงจร ผลิตหนังสือ นิตยสาร บรรจุภัณฑ์อาหาร ลูกค้ารายใหญ่ระดับประเทศ จดทะเบียนในตลาดหลักทรัพย์ SET",
        "stack": ["ERP", "SAP", "SQL Server", "MRP System"],
        "tips": "งาน Programmer ที่โรงงานพิมพ์ขนาดใหญ่เน้น ERP และระบบ Production Planning พูดถึงประสบการณ์กับ Database, Business Logic ด้านการผลิต",
    },
    "บริษัท โสมาภา อินฟอร์เมชั่น เทคโนโลยี จำกัด (มหาชน)": {
        "th": "โสมาภา อินฟอร์เมชั่น เทคโนโลยี",
        "domain": "somapah.co.th",
        "industry": "IT Services / Software House",
        "size": "200–500 คน",
        "hq": "กรุงเทพฯ",
        "listed": "SET: SMPC",
        "about": "Software House มหาชนพัฒนาระบบ IT ให้ภาครัฐและเอกชน บริการครอบคลุม Custom Software, ERP, e-Government, และระบบบัญชี จดทะเบียนในตลาดหลักทรัพย์ MAI",
        "stack": ["Java", ".NET", "Oracle", "PHP", "Angular"],
        "tips": "Software House รับงานหลากหลาย ควรพูดถึงความยืดหยุ่นในการเรียนรู้ tech ใหม่ และประสบการณ์งาน Project-based กับลูกค้าหลายราย",
    },
    "บริษัท อินเทอร์เน็ตประเทศไทย จำกัด (มหาชน)": {
        "th": "อินเทอร์เน็ตประเทศไทย (INET)",
        "domain": "inet.co.th",
        "industry": "Telecom / ISP / Cloud / Data Center",
        "size": "500–1,000 คน",
        "hq": "กรุงเทพฯ (Pathumwan)",
        "listed": "SET: INET",
        "about": "ผู้ให้บริการ Internet, Cloud Computing, Data Center และ Cybersecurity ชั้นนำของไทย บริษัทในเครือ NSTDA (สวทช.) ก่อตั้ง พ.ศ. 2537 ลูกค้าครอบคลุมทั้งภาครัฐ, ธนาคาร, และองค์กรขนาดใหญ่",
        "stack": ["Linux", "Cloud (VMware/OpenStack)", "Python", "Go", "Kubernetes", "Networking"],
        "tips": "บริษัทใหญ่มั่นคง เน้น Infrastructure, Cloud, Security เตรียมพูดถึง Linux, Networking basics, Docker/K8s และ Cloud platform ใดก็ได้",
    },
    # ── Jobsdb ──────────────────────────────────────────────────────────────────
    "Maholan Co., Ltd.": {
        "th": "บริษัท มาโฮลัน จำกัด",
        "domain": "maholan.com",
        "industry": "Tech Startup / Platform",
        "size": "10–50 คน",
        "hq": "กรุงเทพฯ",
        "about": "Tech Startup ไทยพัฒนา Digital Platform สำหรับธุรกิจ ทีมเล็กเน้นความเร็วและ ownership สูง งานที่รับคือ Fullstack Developer",
        "stack": ["React", "Node.js", "TypeScript", "PostgreSQL", "AWS/GCP"],
        "tips": "Startup ทีมเล็ก คาดหวังคนทำได้ทั้ง Frontend + Backend เตรียม GitHub portfolio โปรเจกต์ส่วนตัว และพูดถึงความสามารถในการรับ feedback เร็ว",
    },
    "Future Makers Co., Ltd.": {
        "th": "บริษัท ฟิวเจอร์ เมกเกอร์ส จำกัด",
        "domain": "futuremakers.co.th",
        "industry": "Digital Agency / Software",
        "size": "50–200 คน",
        "hq": "กรุงเทพฯ",
        "about": "บริษัทพัฒนา Digital Products และ Software ครบวงจร ให้บริการทั้ง Web App, Mobile App และ E-commerce สำหรับลูกค้าหลากหลายอุตสาหกรรม",
        "stack": ["React", "Vue.js", "Node.js", "Express", "MongoDB", "MySQL"],
        "tips": "งาน Full Stack JS เน้น React/Vue + Node.js เตรียมพูดถึง REST API design, state management (Redux/Pinia) และ version control workflow",
    },
    "AZTEK CO., LTD.": {
        "th": "บริษัท แอซเทก จำกัด",
        "domain": "aztek.co.th",
        "industry": "IT Solutions / Software",
        "size": "50–200 คน",
        "hq": "กรุงเทพฯ",
        "about": "บริษัทพัฒนา Software Solutions และ IT Systems ให้กับองค์กรธุรกิจ งานที่รับคือ Full Stack Developer สำหรับพัฒนาระบบให้ลูกค้า",
        "stack": ["React", "Angular", ".NET", "Java", "SQL Server", "PostgreSQL"],
        "tips": "เตรียม Portfolio โปรเจกต์ Full Stack ที่ครอบคลุมตั้งแต่ Database schema → API → Frontend และพูดถึงกระบวนการทดสอบระบบ",
    },
    "TECHINVENT CO., LTD.": {
        "th": "บริษัท เทคอินเวนท์ จำกัด",
        "domain": "techinvent.co.th",
        "industry": "Technology / Innovation",
        "size": "50–200 คน",
        "hq": "กรุงเทพฯ",
        "about": "บริษัทเทคโนโลยีเน้นนวัตกรรม พัฒนา Software และ Digital Solutions สำหรับธุรกิจไทย งานที่รับคือ Programmer/Developer",
        "stack": ["PHP", "Laravel", "React", "MySQL", "REST API"],
        "tips": "เตรียมพูดถึง Programming Language ที่ถนัด แสดง Portfolio และพูดถึงแนวทางแก้ปัญหา bug ในโปรเจกต์จริง",
    },
    # ── JOBBKK ──────────────────────────────────────────────────────────────────
    "เนกเจนซอฟ": {
        "th": "เนกเจนซอฟ (NextGenSoft)",
        "domain": "nextgensoftware.co.th",
        "industry": "Software Development",
        "size": "10–50 คน",
        "hq": "กรุงเทพฯ",
        "about": "บริษัท Software House ขนาดเล็กพัฒนาซอฟต์แวร์ตามความต้องการลูกค้า ทีมเล็ก agile รับงาน outsource และ custom development",
        "stack": ["PHP", "JavaScript", "MySQL", "Laravel"],
        "tips": "Software House เล็กเน้นความรวดเร็วในการทำงาน พูดถึงโปรเจกต์ที่เคยทำคนเดียวหรือทีมเล็กให้สำเร็จ",
    },
    "WINTEL SOFTECH RECRUITMENT": {
        "th": "วินเทล ซอฟเทค รีครูทเมนท์",
        "domain": "wintelsoftech.com",
        "industry": "IT Staffing / Outsourcing",
        "size": "50–200 คน",
        "hq": "กรุงเทพฯ",
        "about": "บริษัท IT Staffing และ Recruitment วาง Developer ที่ลูกค้าองค์กรชั้นนำ งาน Frontend/Fullstack ที่รับอาจเป็นงาน Outsource ประจำ Site ลูกค้า",
        "stack": ["React", "Vue.js", "Angular", "TypeScript", "Node.js"],
        "tips": "งาน Outsource ต้องปรับตัวกับ environment ลูกค้าได้ดี พูดถึงความสามารถทำงานในทีมขนาดต่างๆ และเรียนรู้ codebase ใหม่เร็ว",
    },
    "บริษัท ไอโคเน็กซ์ จำกัด": {
        "th": "บริษัท ไอโคเน็กซ์ จำกัด",
        "domain": "iconex.co.th",
        "industry": "IT Solutions",
        "size": "50–200 คน",
        "hq": "กรุงเทพฯ",
        "about": "บริษัท IT Solutions พัฒนาซอฟต์แวร์และระบบให้กับองค์กร รับนักศึกษาจบใหม่และนักศึกษาฝึกงาน เป็นจุดเริ่มต้นที่ดีสำหรับ Developer ใหม่",
        "stack": ["Java", "PHP", "MySQL", "JavaScript"],
        "tips": "บริษัทรับ New Grad เน้นดูความตั้งใจเรียนรู้มากกว่าประสบการณ์ เตรียมพูดถึง โปรเจกต์ที่ทำในมหาวิทยาลัยและ side project",
    },
    "บริษัท โปรเฟสชันแนลวัน จำกัด": {
        "th": "โปรเฟสชันแนลวัน",
        "domain": "professional1.co.th",
        "industry": "IT Solutions / Software",
        "size": "50–200 คน",
        "hq": "สมุทรสาคร",
        "about": "บริษัท IT Solutions ตั้งอยู่ที่สมุทรสาคร พัฒนาซอฟต์แวร์สำหรับอุตสาหกรรมและธุรกิจในพื้นที่ ใกล้ นิคมอุตสาหกรรม",
        "stack": ["C#", ".NET", "SQL Server", "JavaScript"],
        "tips": "ที่ตั้งสมุทรสาครห่างจาก กทม. เตรียมถามเรื่อง work-from-home policy, สวัสดิการเดินทาง และ tech stack ที่ใช้จริง",
    },
    "บริษัท พูนธนามาร์เก็ตติ้ง จำกัด": {
        "th": "พูนธนามาร์เก็ตติ้ง",
        "domain": "phoonthana.co.th",
        "industry": "Marketing / Distribution",
        "size": "50–500 คน",
        "hq": "กรุงเทพฯ",
        "about": "บริษัทด้านการตลาดและจัดจำหน่าย ต้องการ Developer สำหรับพัฒนาระบบ Internal หรือ E-commerce",
        "stack": ["PHP", "MySQL", "JavaScript", "WordPress"],
        "tips": "บริษัทนอก IT หลัก Developer จะต้องทำงานอิสระมากขึ้น เตรียมพูดถึงความสามารถในการทำงานคนเดียวและสื่อสารกับ non-tech stakeholder",
    },
    "บริษัท คอนเวอร์เจนซ์ เทคโนโลยี จำกัด (Convergence Technology Co.Ltd.)": {
        "th": "คอนเวอร์เจนซ์ เทคโนโลยี",
        "domain": "convergence-th.com",
        "industry": "IT Solutions / System Integrator",
        "size": "200–500 คน",
        "hq": "กรุงเทพฯ",
        "about": "บริษัท IT System Integrator ให้บริการพัฒนาระบบ, วาง IT Infrastructure, และ Digital Transformation ให้กับลูกค้าองค์กรชั้นนำ ทั้งภาครัฐและเอกชน (สมัคร 2 ครั้ง)",
        "stack": ["Java", "Spring Boot", ".NET", "React", "Oracle", "Docker"],
        "tips": "SI ทำงานหลายโปรเจกต์พร้อมกัน เตรียมพูดถึงการจัดการ deadline, การ handoff งานให้ทีม, และ tech stack ที่ปรับตัวได้หลายอย่าง",
    },
    "บริษัท โรงพยาบาล บีเจเอช จำกัด": {
        "th": "โรงพยาบาล บีเจเอช (BJC Healthcare)",
        "domain": "bjchealth.co.th",
        "industry": "Healthcare / Hospital",
        "size": "500–5,000 คน",
        "hq": "กรุงเทพฯ",
        "about": "เครือโรงพยาบาลในกลุ่ม BJC (เบอร์ลี่ยุคเกอร์) บริหารโรงพยาบาลหลายแห่งในไทย ต้องการ Mobile Developer สำหรับพัฒนา App ด้าน Healthcare",
        "stack": ["iOS", "Android", "React Native", "Flutter", "REST API", "HL7/FHIR"],
        "tips": "Healthcare IT เน้นความน่าเชื่อถือและ data privacy สูงมาก เตรียมพูดถึง Mobile App development และความเข้าใจเรื่อง Patient data handling",
    },
    "บริษัท พลัสอินไซ จำกัด": {
        "th": "พลัสอินไซ (Plus Insight)",
        "domain": "plusinsight.co.th",
        "industry": "Data Analytics / IT",
        "size": "10–50 คน",
        "hq": "กรุงเทพฯ",
        "about": "บริษัท Data Analytics และ Business Intelligence ให้บริการวิเคราะห์ข้อมูลและพัฒนา Dashboard สำหรับองค์กร งานที่รับคือ Junior Frontend Developer",
        "stack": ["React", "JavaScript", "Chart.js", "D3.js", "Python", "SQL"],
        "tips": "งาน Frontend ด้าน Data Viz เตรียมพูดถึง JavaScript charting libraries, responsive design และการนำเสนอข้อมูลให้เข้าใจง่าย",
    },
    "บริษัท เอเพ็กซ์ เซอร์คิต (ไทยแลนด์) จำกัด": {
        "th": "เอเพ็กซ์ เซอร์คิต (ไทยแลนด์)",
        "domain": "apexcircuit.com",
        "industry": "Electronics / PCB Manufacturing",
        "size": "1,000–5,000 คน",
        "hq": "สมุทรปราการ",
        "about": "โรงงานผลิต Printed Circuit Board (PCB) ชั้นนำ บริษัทในเครือ Apex International ผลิตชิ้นส่วนอิเล็กทรอนิกส์ให้แบรนด์ระดับโลก",
        "stack": ["C#", ".NET", "SQL Server", "MES System", "ERP SAP"],
        "tips": "โรงงานอิเล็กทรอนิกส์ งาน Programmer เน้น MES (Manufacturing Execution System) และ ERP ถามเรื่อง shift work และ OT policy ด้วย",
    },
    "Techspace Co.": {
        "th": "Techspace",
        "domain": "techspace.co.th",
        "industry": "Software Development",
        "size": "10–50 คน",
        "hq": "กรุงเทพฯ",
        "about": "บริษัท Software Development ขนาดเล็กพัฒนา Web และ Mobile Application รับโปรเจกต์ลูกค้าและพัฒนา Product ของตัวเอง",
        "stack": ["React", "Node.js", "Python", "PostgreSQL", "AWS"],
        "tips": "ทีมเล็กเน้นคนทำได้หลายอย่าง เตรียม Portfolio เน้น end-to-end project ที่ deploy จริง",
    },
    "IT SHOWROOM CO.": {
        "th": "ไอที โชว์รูม",
        "domain": "itshowroom.co.th",
        "industry": "IT Retail / Solutions",
        "size": "50–200 คน",
        "hq": "กรุงเทพฯ",
        "about": "บริษัท IT Retail และ Solutions จำหน่ายและให้บริการ IT Equipment ให้กับองค์กร งาน Programmer น่าจะเป็นพัฒนาระบบ Internal",
        "stack": ["PHP", "MySQL", "JavaScript", "ERP"],
        "tips": "ถามให้ชัดเจนว่างาน Programmer ทำอะไร พัฒนาระบบ Internal หรือ Product ของบริษัท",
    },
    "บริษัท ซอฟต์สแควร์ 1999 จำกัด": {
        "th": "ซอฟต์สแควร์ 1999",
        "domain": "softsquare.co.th",
        "industry": "ERP Software / IT Solutions",
        "size": "200–500 คน",
        "hq": "ปทุมธานี (สนง.ใหญ่)",
        "about": "บริษัทพัฒนา ERP Software ครบวงจรสำหรับธุรกิจไทย ก่อตั้งมานานกว่า 25 ปี ผลิตภัณฑ์ครอบคลุม บัญชี, ขาย, คลังสินค้า, HR ที่ตั้งหลักที่ปทุมธานี",
        "stack": ["Delphi", "C#", ".NET", "SQL Server", "Crystal Reports"],
        "tips": "บริษัท ERP เก่าแก่ tech stack อาจเป็น legacy แต่มั่นคงมาก เตรียมถามเรื่อง modernization roadmap และ training program",
    },
    "บริษัท ซิลค์สแปน อินชัวรันซ์ โบรกเกอร์เรจ จำกัด": {
        "th": "ซิลค์สแปน ประกันภัย",
        "domain": "silkspan.co.th",
        "industry": "Insurance Brokerage / Fintech",
        "size": "50–200 คน",
        "hq": "เอกมัย, กรุงเทพฯ",
        "about": "บริษัทนายหน้าประกันภัยให้บริการประกันภัยทุกประเภทสำหรับลูกค้า Corporate และบุคคล Office ตั้งอยู่แถวเอกมัย",
        "stack": ["PHP", "JavaScript", "MySQL", "Insurance Platform"],
        "tips": "Insurance Tech เน้นระบบที่น่าเชื่อถือและ secure มาก เตรียมพูดถึง data validation, security awareness และการทำงานกับ business rule ที่ซับซ้อน",
    },
    "บริษัท อะไลน์ โซลูชั่น จำกัด": {
        "th": "อะไลน์ โซลูชั่น",
        "domain": "aline.co.th",
        "industry": "IT Solutions / Software",
        "size": "50–200 คน",
        "hq": "กรุงเทพฯ",
        "about": "บริษัท IT Solutions พัฒนาซอฟต์แวร์และระบบให้กับลูกค้าองค์กร บริการครอบคลุม Custom Development, System Integration",
        "stack": ["Java", "PHP", "JavaScript", "MySQL", "Oracle"],
        "tips": "เตรียม portfolio โปรเจกต์ที่แก้ปัญหา business ได้จริง และพูดถึงความสามารถในการทำงาน end-to-end",
    },
    "Fidelity Fascinate Fastness": {
        "th": "Fidelity Fascinate Fastness",
        "domain": "",
        "industry": "IT / Digital Agency",
        "size": "10–50 คน",
        "hq": "กรุงเทพฯ",
        "about": "บริษัท Digital Agency / IT พัฒนาเว็บไซต์และแอปพลิเคชัน ชื่อบริษัทแสดงถึงเน้นความน่าเชื่อถือและความเร็ว",
        "stack": ["React", "Node.js", "PHP", "MySQL"],
        "tips": "เตรียม Portfolio ผลงานเว็บ/แอปที่ผ่านมา และพูดถึงกระบวนการทำงานตั้งแต่ design จนถึง deploy",
    },
    "บริษัท วิชั่นเน็ต จำกัด": {
        "th": "วิชั่นเน็ต",
        "domain": "visionnet.co.th",
        "industry": "IT Networking / Solutions",
        "size": "50–200 คน",
        "hq": "กรุงเทพฯ",
        "about": "บริษัท IT Networking และ Database Solutions งานที่รับคือ Database Programmer และ Application Developer ซึ่งต้องการคนที่เข้าใจทั้ง App และ Database",
        "stack": ["Oracle", "SQL Server", "Java", "C#", "PL/SQL"],
        "tips": "งานนี้เน้น Database มาก เตรียมพูดถึง SQL Query optimization, Stored Procedure, Database design และประสบการณ์กับ Oracle/SQL Server",
    },
    "VP Advance Co.": {
        "th": "VP Advance",
        "domain": "vpadvance.co.th",
        "industry": "IT Outsourcing / Consulting",
        "size": "50–200 คน",
        "hq": "กรุงเทพฯ",
        "about": "บริษัท IT Outsourcing วาง Programmer ไปทำงาน On-site ที่บริษัทลูกค้า งาน Outsource มักได้ทำงานกับบริษัทขนาดใหญ่ในหลายอุตสาหกรรม",
        "stack": ["Java", "PHP", ".NET", "JavaScript", "SQL"],
        "tips": "Outsource ต้องปรับตัวกับ environment ลูกค้าได้ดี พูดถึงความสามารถเรียนรู้ codebase ใหม่เร็วและการสื่อสารกับ team ลูกค้า",
    },
    "บริษัท กิฟฟารีน สกายไลน์ ยูนิตี้ จำกัด": {
        "th": "กิฟฟารีน สกายไลน์ ยูนิตี้",
        "domain": "giffarine.com",
        "industry": "Direct Selling / Consumer Goods",
        "size": "2,000+ คน",
        "hq": "กรุงเทพฯ",
        "about": "บริษัทขายตรงชื่อดังของไทย ผลิตภัณฑ์ครอบคลุม สุขภาพ, ความงาม, อาหาร มีเครือข่ายตัวแทนกว่าล้านคนทั่วประเทศ ต้องการ Programmer พัฒนาระบบ E-commerce และ Agent Management",
        "stack": ["PHP", "Laravel", "MySQL", "JavaScript", "React", "E-commerce Platform"],
        "tips": "บริษัทใหญ่มั่นคง ระบบ IT ซับซ้อนมาก (ตัวแทน + E-commerce + Inventory) เตรียมพูดถึงระบบขนาดใหญ่ที่เคยทำและ scalability",
    },
    "บริษัท แอ็บโซลูท เทคโนวัน จำกัด": {
        "th": "แอ็บโซลูท เทคโนวัน",
        "domain": "absolutetechno.com",
        "industry": "Web Development / IT",
        "size": "10–50 คน",
        "hq": "กรุงเทพฯ (WFH Available)",
        "about": "บริษัทพัฒนาเว็บและแอปพลิเคชัน PHP เน้น Back-end รับทั้งงาน WFH และ On-site งานที่รับคือ PHP Web Programmer",
        "stack": ["PHP", "Laravel", "CodeIgniter", "MySQL", "JavaScript", "jQuery"],
        "tips": "งาน PHP เน้น Laravel/CI เตรียมพูดถึง MVC pattern, OOP, REST API และ Database query optimization ถามด้วยว่า WFH กี่วันต่อสัปดาห์",
    },
    "บริษัท สมาร์ทโซลูชั่น แอนด์ เซอร์วิส จำกัด": {
        "th": "สมาร์ทโซลูชั่น แอนด์ เซอร์วิส",
        "domain": "smartsolution.co.th",
        "industry": "Web Development / IT Services",
        "size": "50–200 คน",
        "hq": "กรุงเทพฯ",
        "about": "บริษัทพัฒนาเว็บไซต์และ IT Services งานที่รับคือ Web Programmer สำหรับพัฒนา Web Application ให้ลูกค้าหลากหลายธุรกิจ",
        "stack": ["PHP", "JavaScript", "MySQL", "WordPress", "HTML/CSS"],
        "tips": "เตรียม Portfolio เว็บไซต์ที่เคยทำ และพูดถึงความสามารถ responsive design และ cross-browser compatibility",
    },
    "บริษัท เครดิตฟองซิเอร์ เอสเบ จำกัด": {
        "th": "เครดิตฟองซิเอร์ เอสเบ",
        "domain": "sbcf.co.th",
        "industry": "Financial Services / Real Estate Loans",
        "size": "200–500 คน",
        "hq": "กรุงเทพฯ",
        "about": "บริษัทเงินทุน Credit Foncier ให้บริการสินเชื่อที่ดินและอสังหาริมทรัพย์ อยู่ภายใต้การกำกับของธนาคารแห่งประเทศไทย (ธปท.)",
        "stack": ["Java", "Oracle", "SQL Server", "Core Banking System"],
        "tips": "งาน IT ในองค์กรการเงินเข้มงวดเรื่อง security และ compliance มาก เตรียมพูดถึง Database, security awareness และความละเอียดรอบคอบในการเขียน code",
    },
    "R.X. Company Limited": {
        "th": "R.X. Company",
        "domain": "rx.co.th",
        "industry": "IT / Healthcare / Pharma",
        "size": "50–200 คน",
        "hq": "กรุงเทพฯ",
        "about": "บริษัท IT หรือเกี่ยวข้องกับ Healthcare/Pharma (ชื่อ R.X. บ่งชี้ด้าน Medical/Pharmaceutical) งานที่รับคือ Programmer",
        "stack": ["PHP", "Java", "MySQL", "JavaScript"],
        "tips": "ถามให้ชัดว่าบริษัทดำเนินธุรกิจด้านไหน เตรียม Portfolio ที่หลากหลายเผื่อ domain ที่ต้องการ",
    },
}

SOURCE_COLORS = {
    "JOBBKK": {"bg": "rgba(99,102,241,.12)", "border": "rgba(99,102,241,.35)", "text": "#a5b4fc", "dot": "#6366f1"},
    "JobThai": {"bg": "rgba(16,185,129,.12)", "border": "rgba(16,185,129,.35)", "text": "#6ee7b7", "dot": "#10b981"},
    "Jobsdb": {"bg": "rgba(245,158,11,.12)", "border": "rgba(245,158,11,.35)", "text": "#fcd34d", "dot": "#f59e0b"},
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

def logo_html(info, company):
    domain = (info or {}).get("domain","") if info else ""
    initial = (company[:1] if company else "?").upper()
    colors = ["#6366f1","#10b981","#f59e0b","#8b5cf6","#06b6d4","#ef4444","#ec4899","#14b8a6"]
    color = colors[sum(ord(c) for c in company) % len(colors)]
    if domain:
        return f'<div class="logo-wrap"><img class="logo-img" src="https://logo.clearbit.com/{domain}" alt="" onerror="this.style.display=\'none\';var fb=this.nextElementSibling;if(fb)fb.style.display=\'flex\'"><div class="logo-fallback" style="background:{color};display:none">{esc(initial)}</div></div>'
    return f'<div class="logo-wrap"><div class="logo-fallback" style="background:{color}">{esc(initial)}</div></div>'

def stack_pills(stack):
    if not stack: return ""
    pills = "".join(f'<span class="pill">{esc(s)}</span>' for s in stack)
    return f'<div class="stack-row">{pills}</div>'

def info_section(info):
    if not info: return ""
    return f"""
    <div class="info-section">
      <div class="info-toggle" onclick="this.parentElement.classList.toggle('open')">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
        เตรียมสัมภาษณ์
        <svg class="arrow" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"/></svg>
      </div>
      <div class="info-content">
        <div class="info-block">
          <div class="info-label">เกี่ยวกับบริษัท</div>
          <div class="info-text">{esc(info.get('about',''))}</div>
        </div>
        <div class="info-block tip">
          <div class="info-label">เคล็ดลับสัมภาษณ์</div>
          <div class="info-text">{esc(info.get('tips',''))}</div>
        </div>
      </div>
    </div>"""

STATUS_BADGE = {
    "viewed": '<span class="status-badge viewed">เปิดดูใบสมัคร</span>',
    "activity": '<span class="status-badge activity">กิจกรรมใหม่</span>',
    "interview": '<span class="status-badge interview">นัดสัมภาษณ์</span>',
}

def sent_card(e, info):
    sc = SOURCE_COLORS.get(e["source"], SOURCE_COLORS["JOBBKK"])
    company = e["company"]
    q = urllib.request.quote((company+" "+e["position"]).strip())
    industry = (info or {}).get("industry","")
    size = (info or {}).get("size","")
    hq = (info or {}).get("hq","")
    listed = (info or {}).get("listed","")
    domain = (info or {}).get("domain","")
    meta_parts = [p for p in [size, hq] if p]
    meta = " · ".join(meta_parts)
    website = f'<a href="https://{domain}" target="_blank" class="website-link"><svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>{domain}</a>' if domain else ""
    listed_badge = f'<span class="listed-badge">{esc(listed)}</span>' if listed else ""

    return f"""
    <div class="card" data-company="{esc(company).lower()}" data-position="{esc(e['position']).lower()}" data-source="{esc(e['source'])}">
      <div class="card-source-bar" style="background:{sc['bg']};border-color:{sc['border']}">
        <span class="source-dot" style="background:{sc['dot']}"></span>
        <span style="color:{sc['text']};font-size:11px;font-weight:600">{esc(e['source'])}</span>
        <span class="card-date">{esc(e['date'])}</span>
        <a href="https://www.google.com/search?q={q}" target="_blank" class="search-btn">
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>ค้นหา
        </a>
      </div>
      <div class="card-body">
        {logo_html(info, company)}
        <div class="card-content">
          <div class="card-company">{esc(company)}{listed_badge}</div>
          <div class="card-position">{esc(e['position'])}</div>
          {f'<div class="card-industry">{esc(industry)}</div>' if industry else ""}
          {f'<div class="card-meta">{esc(meta)}</div>' if meta else ""}
          {website}
        </div>
      </div>
      {stack_pills((info or {}).get("stack",[]))}
      {info_section(info)}
    </div>"""

def response_card(e, info):
    badge = STATUS_BADGE.get(e["status"], '<span class="status-badge">อัพเดต</span>')
    company = e.get("company","")
    cls = "card-interview" if e["status"] == "interview" else ""
    q = urllib.request.quote((company+" "+e.get("position","")).strip())
    domain = (info or {}).get("domain","")
    size = (info or {}).get("size","")
    hq = (info or {}).get("hq","")
    meta = " · ".join([p for p in [size, hq] if p])

    return f"""
    <div class="card response-card {cls}">
      <div class="card-source-bar response-bar">
        {badge}
        <span class="card-date">{esc(e['date'])}</span>
        <a href="https://www.google.com/search?q={q}" target="_blank" class="search-btn">
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>ค้นหา
        </a>
      </div>
      <div class="card-body">
        {logo_html(info, company)}
        <div class="card-content">
          <div class="card-company">{esc(company)}</div>
          {f'<div class="card-position">{esc(e.get("position",""))}</div>' if e.get("position") else ""}
          {f'<div class="card-industry">{esc((info or {}).get("industry",""))}</div>' if (info or {}).get("industry") else ""}
          {f'<div class="card-meta">{esc(meta)}</div>' if meta else ""}
        </div>
      </div>
      {stack_pills((info or {}).get("stack",[]))}
      {info_section(info)}
    </div>"""

def group_by_source(items):
    groups = {"JOBBKK": [], "JobThai": [], "Jobsdb": []}
    for e in items:
        src = e.get("source","")
        if src in groups: groups[src].append(e)
    return groups

def build_html(sent, resp, updated_at):
    groups = group_by_source(sent)
    n_viewed = len([r for r in resp if r["status"] == "viewed"])
    n_interview = len([r for r in resp if r["status"] == "interview"])

    # All cards
    all_cards = "\n".join([sent_card(e, COMPANY_INFO.get(e["company"])) for e in sent])

    # Per-source sections
    source_sections = ""
    for src, items in groups.items():
        if not items: continue
        sc = SOURCE_COLORS[src]
        cards = "\n".join([sent_card(e, COMPANY_INFO.get(e["company"])) for e in items])
        source_sections += f"""
        <div class="source-section" id="sec-{src}">
          <div class="source-header" style="border-color:{sc['dot']}">
            <span class="source-title" style="color:{sc['text']}">{src}</span>
            <span class="source-count">{len(items)} รายการ</span>
          </div>
          <div class="grid">{cards}</div>
        </div>"""

    resp_html = ""
    if resp:
        resp_html = '<div class="grid">' + "\n".join([response_card(e, COMPANY_INFO.get(e.get("company",""))) for e in resp]) + "</div>"
    else:
        resp_html = "<div class='empty'>ยังไม่มีบริษัทติดต่อกลับ</div>"

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
.header{{background:linear-gradient(135deg,#1a1d2e,#242738);border-bottom:1px solid var(--border);padding:22px 32px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px}}
.header h1{{font-size:22px;font-weight:700;letter-spacing:-.3px}} .header h1 span{{color:var(--blue-l)}}
.header-sub{{color:var(--muted);font-size:12px;margin-top:3px}}
.stats{{display:flex;gap:12px;padding:16px 32px;background:var(--surface);border-bottom:1px solid var(--border);flex-wrap:wrap}}
.stat-card{{flex:1;min-width:100px;background:var(--surface2);border:1px solid var(--border);border-radius:10px;padding:12px 16px}}
.stat-num{{font-size:26px;font-weight:700;line-height:1}} .stat-label{{color:var(--muted);font-size:11px;margin-top:3px}}
.blue .stat-num{{color:var(--blue-l)}} .green .stat-num{{color:var(--green)}} .orange .stat-num{{color:var(--orange)}} .purple .stat-num{{color:var(--purple)}}

/* Tabs */
.tab-bar{{display:flex;align-items:center;gap:8px;padding:16px 32px 0;background:var(--surface);border-bottom:1px solid var(--border);flex-wrap:wrap}}
.tab{{padding:8px 18px;border-radius:8px 8px 0 0;cursor:pointer;font-size:13px;font-weight:500;color:var(--muted);border:none;background:none;border-bottom:2px solid transparent;transition:all .15s;white-space:nowrap}}
.tab.active{{color:var(--text);border-bottom-color:var(--blue-l);background:rgba(99,102,241,.08)}}
.tab:hover:not(.active){{color:var(--text);background:rgba(255,255,255,.04)}}
.tab.tab-jobbkk.active{{border-bottom-color:#818cf8}} .tab.tab-jobthai.active{{border-bottom-color:#34d399}} .tab.tab-jobsdb.active{{border-bottom-color:#fbbf24}} .tab.tab-resp.active{{border-bottom-color:#34d399}}
.tab-spacer{{flex:1}}

/* Toolbar */
.toolbar{{display:flex;gap:10px;margin-bottom:20px;align-items:center;flex-wrap:wrap}}
.search-input{{flex:1;min-width:200px;max-width:360px;background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:9px 14px 9px 36px;color:var(--text);font-size:13px;outline:none;background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='15' height='15' viewBox='0 0 24 24' fill='none' stroke='%238892a4' stroke-width='2'%3E%3Ccircle cx='11' cy='11' r='8'/%3E%3Cpath d='m21 21-4.35-4.35'/%3E%3C/svg%3E");background-repeat:no-repeat;background-position:12px center}}
.search-input:focus{{border-color:var(--blue)}}
.count-label{{color:var(--muted);font-size:13px;margin-left:auto}}

/* Main */
.main{{padding:24px 32px;max-width:1400px;margin:0 auto}}
.tab-content{{display:none}} .tab-content.active{{display:block}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(310px,1fr));gap:14px}}

/* Source sections */
.source-section{{margin-bottom:32px}}
.source-header{{display:flex;align-items:center;gap:10px;margin-bottom:14px;padding-bottom:10px;border-bottom:2px solid}}
.source-title{{font-size:16px;font-weight:700}} .source-count{{font-size:12px;color:var(--muted);margin-left:auto}}

/* Card */
.card{{background:var(--surface);border:1px solid var(--border);border-radius:12px;overflow:hidden;transition:border-color .15s,transform .1s}}
.card:hover{{border-color:#454a6b;transform:translateY(-1px)}}
.response-card{{border-top:2px solid var(--green)}} .card-interview{{border-top:2px solid var(--orange)!important}}
.card-source-bar{{display:flex;align-items:center;gap:8px;padding:7px 12px;border-bottom:1px solid;flex-wrap:wrap}}
.response-bar{{background:rgba(16,185,129,.08);border-color:rgba(16,185,129,.2)}}
.source-dot{{width:6px;height:6px;border-radius:50%;flex-shrink:0}}
.card-date{{font-size:11px;color:var(--muted);margin-left:auto}}
.search-btn{{display:flex;align-items:center;gap:4px;font-size:11px;color:var(--muted);text-decoration:none;padding:3px 8px;border-radius:5px;border:1px solid var(--border);transition:all .15s;white-space:nowrap;margin-left:6px}}
.search-btn:hover{{color:var(--text);border-color:#454a6b;background:var(--surface2)}}

.card-body{{display:flex;align-items:flex-start;gap:12px;padding:14px 14px 8px}}
.logo-wrap{{flex-shrink:0;width:44px;height:44px}}
.logo-img{{width:44px;height:44px;border-radius:8px;object-fit:contain;background:#fff;padding:2px}}
.logo-fallback{{width:44px;height:44px;border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:18px;font-weight:700;color:#fff;flex-shrink:0}}

.card-content{{flex:1;min-width:0}}
.card-company{{font-size:14px;font-weight:600;line-height:1.4;margin-bottom:2px;display:flex;align-items:center;gap:6px;flex-wrap:wrap}}
.card-position{{font-size:12px;color:var(--cyan);margin-bottom:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.card-industry{{font-size:11px;color:var(--muted);margin-bottom:2px}}
.card-meta{{font-size:11px;color:#6b7a8f;margin-bottom:3px}}
.listed-badge{{font-size:10px;font-weight:600;padding:1px 6px;border-radius:4px;background:rgba(245,158,11,.15);color:#fcd34d;border:1px solid rgba(245,158,11,.3);white-space:nowrap}}
.website-link{{font-size:11px;color:var(--muted);text-decoration:none;display:inline-flex;align-items:center;gap:4px;margin-top:2px}}
.website-link:hover{{color:var(--blue-l)}}

/* Stack pills */
.stack-row{{display:flex;flex-wrap:wrap;gap:5px;padding:0 14px 10px}}
.pill{{font-size:10px;padding:2px 8px;border-radius:20px;background:rgba(99,102,241,.1);color:#a5b4fc;border:1px solid rgba(99,102,241,.2);white-space:nowrap}}

/* Info section */
.info-section{{border-top:1px solid var(--border);padding:10px 14px}}
.info-toggle{{display:flex;align-items:center;gap:6px;cursor:pointer;color:var(--blue-l);font-size:12px;font-weight:500;user-select:none;padding:2px 0}}
.info-toggle:hover{{color:#fff}} .arrow{{margin-left:auto;transition:transform .2s}}
.info-section.open .arrow{{transform:rotate(180deg)}}
.info-content{{display:none;padding-top:10px}}
.info-section.open .info-content{{display:block}}
.info-block{{margin-bottom:10px}} .info-block:last-child{{margin-bottom:0}}
.info-label{{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.6px;color:var(--muted);margin-bottom:4px}}
.info-block.tip .info-label{{color:#fbbf24}}
.info-text{{font-size:12.5px;color:#c8d3e0;line-height:1.7}}

/* Status badges */
.status-badge{{font-size:11px;font-weight:600;padding:3px 10px;border-radius:20px}}
.status-badge.viewed{{background:rgba(16,185,129,.15);color:#6ee7b7;border:1px solid rgba(16,185,129,.3)}}
.status-badge.activity{{background:rgba(139,92,246,.15);color:#c4b5fd;border:1px solid rgba(139,92,246,.3)}}
.status-badge.interview{{background:rgba(245,158,11,.15);color:#fcd34d;border:1px solid rgba(245,158,11,.3)}}

.empty{{text-align:center;padding:60px;color:var(--muted)}}
@media(max-width:640px){{.header,.stats,.main{{padding:16px}}.tab-bar{{padding:12px 16px 0}}.grid{{grid-template-columns:1fr}}}}
</style>
</head>
<body>

<div class="header">
  <div>
    <h1>ACCR <span>ติดตามการสมัครงาน</span></h1>
    <div class="header-sub">Gmail: art992398@gmail.com &nbsp;·&nbsp; อัพเดตล่าสุด: {updated_at}</div>
  </div>
</div>

<div class="stats">
  <div class="stat-card blue"><div class="stat-num">{len(sent)}</div><div class="stat-label">ส่งใบสมัครแล้ว</div></div>
  <div class="stat-card green"><div class="stat-num">{len(resp)}</div><div class="stat-label">บริษัทตอบกลับ</div></div>
  <div class="stat-card orange"><div class="stat-num">{n_viewed}</div><div class="stat-label">เปิดดูใบสมัคร</div></div>
  <div class="stat-card purple"><div class="stat-num">{n_interview}</div><div class="stat-label">นัดสัมภาษณ์</div></div>
</div>

<div class="tab-bar">
  <button class="tab active" id="t-all" onclick="switchTab('all',this)">ทั้งหมด ({len(sent)})</button>
  <button class="tab tab-jobbkk" id="t-JOBBKK" onclick="switchTab('JOBBKK',this)">JOBBKK ({len(groups['JOBBKK'])})</button>
  <button class="tab tab-jobthai" id="t-JobThai" onclick="switchTab('JobThai',this)">JobThai ({len(groups['JobThai'])})</button>
  <button class="tab tab-jobsdb" id="t-Jobsdb" onclick="switchTab('Jobsdb',this)">Jobsdb ({len(groups['Jobsdb'])})</button>
  <div class="tab-spacer"></div>
  <button class="tab tab-resp" id="t-resp" onclick="switchTab('resp',this)">บริษัทติดต่อกลับ ({len(resp)})</button>
</div>

<div class="main">

  <!-- All tab -->
  <div class="tab-content active" id="tab-all">
    <div class="toolbar">
      <input class="search-input" type="text" placeholder="ค้นหาบริษัท หรือตำแหน่งงาน..." oninput="filterAll(this.value)" id="search-all">
      <span class="count-label" id="count-all">{len(sent)} รายการ</span>
    </div>
    <div class="grid" id="grid-all">{all_cards}</div>
  </div>

  <!-- Per-source tabs -->
  <div class="tab-content" id="tab-JOBBKK">
    <div class="toolbar"><span class="count-label">{len(groups['JOBBKK'])} รายการจาก JOBBKK</span></div>
    <div class="grid">{"".join([sent_card(e, COMPANY_INFO.get(e["company"])) for e in groups["JOBBKK"]])}</div>
  </div>
  <div class="tab-content" id="tab-JobThai">
    <div class="toolbar"><span class="count-label">{len(groups['JobThai'])} รายการจาก JobThai</span></div>
    <div class="grid">{"".join([sent_card(e, COMPANY_INFO.get(e["company"])) for e in groups["JobThai"]])}</div>
  </div>
  <div class="tab-content" id="tab-Jobsdb">
    <div class="toolbar"><span class="count-label">{len(groups['Jobsdb'])} รายการจาก Jobsdb</span></div>
    <div class="grid">{"".join([sent_card(e, COMPANY_INFO.get(e["company"])) for e in groups["Jobsdb"]])}</div>
  </div>

  <!-- Response tab -->
  <div class="tab-content" id="tab-resp">
    <div class="toolbar"><span class="count-label">{len(resp)} รายการ</span></div>
    {resp_html}
  </div>

</div>

<script>
function switchTab(name, btn) {{
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById('tab-' + name).classList.add('active');
}}

function filterAll(q) {{
  const ql = q.toLowerCase();
  const cards = document.querySelectorAll('#grid-all .card');
  let v = 0;
  cards.forEach(c => {{
    const ok = !ql || c.dataset.company.includes(ql) || c.dataset.position.includes(ql);
    c.style.display = ok ? '' : 'none';
    if (ok) v++;
  }});
  document.getElementById('count-all').textContent = v + ' รายการ';
}}
</script>
</body>
</html>"""

# ── GitHub push ────────────────────────────────────────────────────────────────

def gh_put(filepath_repo, content_bytes, message):
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
    req = urllib.request.Request(f"https://api.maton.ai/github/repos/{REPO}/contents/{filepath_repo}")
    req.add_header("Authorization", f"Bearer {MATON_KEY}")
    req.add_header("Maton-Connection", GH_CONN)
    req.add_header("Content-Type", "application/json")
    req.method = "PUT"
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
    # Also push updated generate.py
    with open(__file__, "rb") as f:
        gh_put("generate.py", f.read(), f"Sync generate.py: {updated_at}")
    print("Done:", url)

if __name__ == "__main__":
    main()
