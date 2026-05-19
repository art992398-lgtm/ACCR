const https = require('https');
const url = require('url');

const MATON_KEY = process.env.MATON_API_KEY;
const GMAIL_CONN = process.env.GMAIL_CONNECTION_ID;

function fetchJSON(reqUrl, headers) {
  return new Promise((resolve, reject) => {
    const parsed = url.parse(reqUrl);
    const options = {
      hostname: parsed.hostname,
      path: parsed.path,
      method: 'GET',
      headers: Object.assign({
        'Authorization': `Bearer ${MATON_KEY}`,
        'Maton-Connection': GMAIL_CONN,
      }, headers || {}),
    };
    const req = https.request(options, (res) => {
      let data = '';
      res.on('data', (chunk) => { data += chunk; });
      res.on('end', () => {
        let parsed;
        try { parsed = JSON.parse(data); } catch (e) {
          return reject(new Error(`Non-JSON (${res.statusCode}): ${data.slice(0, 200)}`));
        }
        if (res.statusCode >= 400) {
          return reject(new Error(`HTTP ${res.statusCode}: ${JSON.stringify(parsed).slice(0, 300)}`));
        }
        resolve(parsed);
      });
    });
    req.on('error', reject);
    req.end();
  });
}

function gmailFetch(path) {
  return fetchJSON(`https://api.maton.ai/google-mail/gmail/v1/users/me/${path}`);
}

function decodeBase64(data) {
  if (!data) return '';
  return Buffer.from(data.replace(/-/g, '+').replace(/_/g, '/'), 'base64').toString('utf-8');
}

function extractBody(payload) {
  const mime = payload.mimeType || '';
  if (mime === 'text/plain' && payload.body && payload.body.data)
    return decodeBase64(payload.body.data);
  if (payload.parts) {
    for (const part of payload.parts) {
      const r = extractBody(part);
      if (r) return r;
    }
  }
  return '';
}

function cleanText(text) {
  return text.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
}

function parseDate(dateStr) {
  try { return new Date(dateStr.replace(/\s*\(.*\)/, '').trim()); }
  catch { return new Date(); }
}

function formatDate(d) {
  if (!d || isNaN(d)) return '';
  return d.toLocaleDateString('th-TH', { day: 'numeric', month: 'short', year: 'numeric' });
}

function extractCompanyJobbkk(body) {
  const m = body.match(/เรียน\s+([^\n\r]+?)(?:\s+ดิฉัน|,|\n|\r)/);
  return m ? m[1].trim() : '';
}

function extractJobThaiSubject(subject) {
  const m = subject.match(/ใบสมัครตำแหน่ง\s+(.+?)\s+ถูกส่งถึง\s+(.+?)\s+แล้ว/);
  return m ? { position: m[1].trim(), company: m[2].trim() } : null;
}

function extractJobsdbSent(body) {
  let m = body.match(/ตำแหน่งงาน\s+(.+?)\s+ไปยัง\s+(.+?)\s+เรียบร้อย/);
  if (m) return { position: m[1].trim(), company: m[2].trim() };
  m = body.match(/ใบสมัครงานตำแหน่ง\s+(.+?)\s+ของคุณถูกส่งไปยัง\s+(.+?)\s+เรียบร้อย/);
  return m ? { position: m[1].trim(), company: m[2].trim() } : null;
}

function parseEmail(e) {
  const { sender, subject, date, body } = e;
  const dateObj = parseDate(date);
  const result = {
    id: e.id, date: formatDate(dateObj), dateSort: dateObj.getTime() || 0,
    subject, sender, company: '', position: '', source: '', category: '', status: '',
  };

  if (sender.includes('jobbkk.com')) {
    result.source = 'JOBBKK';
    if (sender.includes('apply@jobbkk.com')) {
      result.category = 'sent'; result.status = 'applied';
      const m = subject.match(/Application letter in\s+(.+)/);
      if (m) result.position = m[1].trim();
      result.company = extractCompanyJobbkk(body);
    } else { result.category = 'newsletter'; }
  } else if (sender.includes('jobthai.com')) {
    result.source = 'JobThai';
    if (sender.includes('upload-file@application.jobthai.com')) {
      result.category = 'sent'; result.status = 'applied';
      const parsed = extractJobThaiSubject(subject);
      if (parsed) { result.position = parsed.position; result.company = parsed.company; }
    } else { result.category = 'newsletter'; }
  } else if (sender.includes('jobsdb.com')) {
    result.source = 'Jobsdb';
    if (subject.includes('ส่งใบสมัครของคุณเรียบร้อยแล้ว')) {
      result.category = 'sent'; result.status = 'applied';
      const parsed = extractJobsdbSent(body);
      if (parsed) { result.position = parsed.position; result.company = parsed.company; }
    } else if (subject.includes('ได้ดูใบสมัครของคุณสำหรับ')) {
      result.category = 'response'; result.status = 'viewed';
      const m = subject.match(/^(.+?)\s+ได้ดูใบสมัครของคุณสำหรับ\s+(.+)$/);
      if (m) { result.company = m[1].trim(); result.position = m[2].trim(); }
    } else if (subject.includes('กิจกรรมใหม่') || subject.includes('นัดสัมภาษณ์')) {
      result.category = 'response';
      result.status = subject.includes('นัดสัมภาษณ์') ? 'interview' : 'activity';
    } else { result.category = 'newsletter'; }
  }
  return result;
}

const COMPANY_INFO = {
  'PHITHAN LEASING CO., LTD.': {
    industry: 'การเงิน / สินเชื่อเช่าซื้อ',
    summary: 'บริษัทให้บริการสินเชื่อเช่าซื้อและลีสซิ่ง เน้นรถยนต์และเครื่องจักร มีสาขาทั่วประเทศ',
    tips: 'เตรียมพูดถึงประสบการณ์กับระบบ Backend / Database เพราะงานเน้นระบบ Back-office ขององค์กรการเงิน',
  },
  'NILECON (THAILAND) CO., LTD.': {
    industry: 'IT / Mobile Application',
    summary: 'บริษัทด้าน IT Solution และ Mobile Application Development ในไทย งานที่สมัครคือ React Native Developer',
    tips: 'เตรียมพูดถึง React Native, TypeScript, การ integrate API เข้า Mobile App และ Portfolio โปรเจกต์ Mobile',
  },
  'บริษัท ศิริวัฒนา อินเตอร์พริ้นท์ จำกัด (มหาชน)': {
    industry: 'สื่อสิ่งพิมพ์ / บรรจุภัณฑ์',
    summary: 'บริษัทมหาชนด้านการพิมพ์และบรรจุภัณฑ์ จดทะเบียนในตลาดหลักทรัพย์ MAI มีโรงงานผลิตขนาดใหญ่',
    tips: 'งานน่าจะเน้น ERP / ระบบ MRP สำหรับโรงงาน ควรพูดถึงประสบการณ์กับ Database หรือ Business Logic',
  },
  'บริษัท โสมาภา อินฟอร์เมชั่น เทคโนโลยี จำกัด (มหาชน)': {
    industry: 'IT Services / Software House',
    summary: 'บริษัทพัฒนา Software และ IT Solutions สำหรับธุรกิจ จดทะเบียนในตลาดหลักทรัพย์ MAI',
    tips: 'Software House มักมีโปรเจกต์หลากหลาย ควรพูดถึง Stack ที่ใช้คล่องและความสามารถเรียนรู้เทคโนโลยีใหม่',
  },
  'บริษัท อินเทอร์เน็ตประเทศไทย จำกัด (มหาชน)': {
    industry: 'Telecommunications / ISP / Cloud',
    summary: 'INET เป็นผู้ให้บริการ Internet, Data Center และ Cloud ชั้นนำ เป็นรัฐวิสาหกิจในเครือ NECTEC/NSTDA จดทะเบียนในตลาดหลักทรัพย์',
    tips: 'บริษัทใหญ่มั่นคง ควรพูดถึง Networking, Cloud, Linux/Server Admin และ Security Awareness',
  },
  'Maholan Co., Ltd.': {
    industry: 'Tech Startup',
    summary: 'Startup เทคโนโลยีไทย พัฒนา Platform ออนไลน์ งานที่สมัครคือ Fullstack Developer',
    tips: 'Startup ต้องการคนทำได้ครอบคลุม Frontend + Backend เตรียม Portfolio และ Side Project',
  },
  'Future Makers Co., Ltd.': {
    industry: 'Technology / Digital Products',
    summary: 'บริษัทพัฒนา Digital Products งานที่สมัครคือ Full Stack Javascript Developer (Node.js + React)',
    tips: 'เตรียมพูดถึง Node.js, React/Vue, REST API, Database และ Git workflow',
  },
  'AZTEK CO., LTD.': {
    industry: 'IT / Software Development',
    summary: 'บริษัทพัฒนา Software Solutions งานที่สมัครคือ Full Stack Developer',
    tips: 'เตรียม Portfolio Full Stack ครบวงจร และพูดถึงกระบวนการพัฒนาตั้งแต่ต้นจนปล่อยระบบ',
  },
  'บริษัท คอนเวอร์เจนซ์ เทคโนโลยี จำกัด (Convergence Technology Co.Ltd.)': {
    industry: 'IT Solutions / System Integrator',
    summary: 'บริษัท IT Solutions ให้บริการพัฒนาระบบและวางโครงสร้าง IT ให้กับองค์กรต่างๆ',
    tips: 'เตรียมพูดถึง Frontend/Backend ที่ใช้จริง และ Project ที่เคยทำงานร่วมกับทีม',
  },
  'TECHINVENT CO., LTD.': {
    industry: 'Technology / Innovation',
    summary: 'บริษัทเทคโนโลยีเน้นนวัตกรรม งานที่สมัครคือ Programmer/โปรแกรมเมอร์',
    tips: 'เตรียมพูดถึง Programming Language ที่ถนัดและโปรเจกต์ที่ผ่านมา',
  },
};

async function fetchAllEmails() {
  const queries = [
    'from:(apply@jobbkk.com OR jobbkk.com)',
    'from:(jobthai.com)',
    'from:(jobsdb.com)',
  ];

  const seen = new Set();
  const msgIds = [];

  for (const q of queries) {
    const data = await gmailFetch(`messages?maxResults=50&q=${encodeURIComponent(q)}`);
    for (const m of (data.messages || [])) {
      if (!seen.has(m.id)) { seen.add(m.id); msgIds.push(m.id); }
    }
  }

  const emails = [];
  for (const id of msgIds) {
    try {
      const msg = await gmailFetch(`messages/${id}?format=full`);
      const payload = msg.payload || {};
      const headers = Object.fromEntries((payload.headers || []).map((h) => [h.name, h.value]));
      const body = cleanText(extractBody(payload)).slice(0, 2000);
      emails.push({
        id,
        subject: headers.Subject || '',
        sender: headers.From || '',
        date: headers.Date || '',
        body,
      });
    } catch (err) {
      // skip individual message errors silently
    }
    await new Promise((r) => setTimeout(r, 100));
  }
  return emails;
}

module.exports = async (req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Cache-Control', 's-maxage=300, stale-while-revalidate=60');

  // Debug endpoint: /api/emails?debug=1
  if (req.query && req.query.debug === '1') {
    try {
      const testData = await gmailFetch('messages?maxResults=3&q=from:(apply@jobbkk.com)');
      return res.status(200).json({
        env: {
          hasMATON_KEY: !!MATON_KEY,
          keyLength: MATON_KEY ? MATON_KEY.length : 0,
          hasGMAIL_CONN: !!GMAIL_CONN,
        },
        testFetch: testData,
      });
    } catch (err) {
      return res.status(200).json({ debugError: err.message });
    }
  }

  try {
    const rawEmails = await fetchAllEmails();
    const parsed = rawEmails.map(parseEmail);

    const sent = parsed
      .filter((e) => e.category === 'sent' && e.company)
      .sort((a, b) => b.dateSort - a.dateSort);

    const response = parsed
      .filter((e) => e.category === 'response')
      .sort((a, b) => b.dateSort - a.dateSort);

    const attachInfo = (list) =>
      list.map((e) => ({ ...e, companyInfo: COMPANY_INFO[e.company] || null }));

    res.status(200).json({
      sent: attachInfo(sent),
      response: attachInfo(response),
      stats: {
        totalSent: sent.length,
        totalResponse: response.length,
        totalViewed: response.filter((e) => e.status === 'viewed').length,
        totalInterview: response.filter((e) => e.status === 'interview').length,
        withInfo: Object.keys(COMPANY_INFO).length,
      },
      updatedAt: new Date().toISOString(),
    });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
};
