# 📁 app.py - BEAUTIFULSOUP İLE EMAILFAKE SCRAPER
from urllib.request import build_opener, HTTPCookieProcessor, Request
from urllib.parse import urljoin
import http.cookiejar
import time
import logging
import re
from flask import Flask, jsonify, request
from bs4 import BeautifulSoup

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Mail depolama
email_storage = {}

def get_emails_from_emailfake(email_address, only_last_email=False):
    """EmailFake'den mailleri çek (BeautifulSoup ile)"""
    try:
        # Cookie jar oluştur
        cookie_jar = http.cookiejar.CookieJar()
        session = build_opener(HTTPCookieProcessor(cookie_jar))
        
        domain = email_address.split("@")[1]
        base_url = f"https://{domain}"
        inbox_url = f"{base_url}/inbox/{email_address}"
        
        logger.info(f"🌐 EmailFake açılıyor: {inbox_url}")
        
        # Sayfayı aç
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        req = Request(inbox_url, headers=headers)
        response = session.open(req)
        html_content = response.read().decode("utf-8")
        
        # BeautifulSoup ile parse et
        soup = BeautifulSoup(html_content, 'html.parser')
        
        emails = []
        
        # 1. Mail linklerini bul
        logger.info("🔍 Mail linkleri aranıyor...")
        
        mail_links = []
        link_selectors = [
            'a[href*="/inbox/"]',
            'a[href*="email"]',
            'a.email-link',
            'a.mail-link'
        ]
        
        for selector in link_selectors:
            links = soup.select(selector)
            if links:
                mail_links.extend([link.get('href') for link in links])
                logger.info(f"✅ {len(links)} mail linki bulundu: {selector}")
        
        # Benzersiz linkler
        mail_links = list(set(mail_links))
        
        # 2. Tablo satırlarından mailleri çıkar
        logger.info("🔍 Tablo satırları kontrol ediliyor...")
        table_emails = extract_emails_from_table(soup, email_address)
        emails.extend(table_emails)
        
        # 3. Mail detay sayfalarını kontrol et
        if not emails and mail_links:
            logger.info("🔍 Mail detay sayfaları kontrol ediliyor...")
            for i, link in enumerate(mail_links):
                if only_last_email and i > 0:
                    break
                    
                try:
                    # URL'yi tamamla
                    if link.startswith('/'):
                        mail_url = urljoin(base_url, link)
                    elif not link.startswith('http'):
                        mail_url = urljoin(inbox_url, link)
                    else:
                        mail_url = link
                    
                    logger.info(f"📧 Mail detayı açılıyor: {mail_url}")
                    
                    # Mail detay sayfasını aç
                    mail_req = Request(mail_url, headers=headers)
                    mail_response = session.open(mail_req)
                    mail_html = mail_response.read().decode("utf-8")
                    mail_soup = BeautifulSoup(mail_html, 'html.parser')
                    
                    # Mail detaylarını parse et
                    email_data = extract_email_details(mail_soup, email_address)
                    if email_data:
                        emails.append(email_data)
                        
                except Exception as e:
                    logger.error(f"❌ Mail detay hatası: {e}")
                    continue
        
        # 4. Basit parsing fallback
        if not emails:
            logger.info("🔍 Basit parsing deneniyor...")
            simple_emails = extract_emails_simple(soup, email_address)
            emails.extend(simple_emails)
        
        logger.info(f"📨 {len(emails)} mail başarıyla alındı")
        
        return {
            "status": "success",
            "email": email_address,
            "total_emails": len(emails),
            "emails": emails,
            "only_last_email": only_last_email
        }
        
    except Exception as e:
        logger.error(f"❌ Scraper hatası: {e}")
        return {
            "status": "error",
            "error": str(e),
            "emails": []
        }

def extract_emails_from_table(soup, email_address):
    """Tablodan email verilerini çıkar"""
    emails = []
    
    # Tablo selector'ları
    table_selectors = [
        'table',
        'table tr',
        '.email-table',
        '.mail-table'
    ]
    
    for selector in table_selectors:
        rows = soup.select(selector)
        if len(rows) > 1:  # Header + en az 1 data satırı
            logger.info(f"✅ Tablo bulundu: {selector} - {len(rows)} satır")
            
            for row in rows[1:]:  # İlk satır header olabilir
                cells = row.find_all(['td', 'div'])
                if len(cells) >= 2:
                    email_data = {
                        'from': cells[0].get_text(strip=True) if len(cells) > 0 else '',
                        'subject': cells[1].get_text(strip=True) if len(cells) > 1 else '',
                        'date': cells[2].get_text(strip=True) if len(cells) > 2 else '',
                        'to': email_address,
                        'received_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                        'source': 'table'
                    }
                    
                    # Boş olmayan mailleri ekle
                    if email_data['from'] or email_data['subject']:
                        emails.append(email_data)
            break
    
    return emails

def extract_email_details(soup, email_address):
    """Mail detay sayfasından email bilgilerini çıkar"""
    try:
        email_data = {}
        
        # From bilgisini bul
        from_selectors = [
            'div:contains("From:")',
            'span:contains("From:")',
            'b:contains("From:")',
            'td:contains("From:")'
        ]
        
        for selector in from_selectors:
            element = soup.find(text=re.compile('From:', re.IGNORECASE))
            if element:
                parent = element.parent
                # Sonraki element veya text'i al
                next_element = parent.find_next_sibling()
                if next_element:
                    email_data['from'] = next_element.get_text(strip=True)
                else:
                    # Text içinden al
                    full_text = parent.get_text()
                    match = re.search(r'From:\s*(.+)', full_text, re.IGNORECASE)
                    if match:
                        email_data['from'] = match.group(1).strip()
                break
        
        # Subject bilgisini bul
        subject_selectors = [
            'div:contains("Subject:")',
            'span:contains("Subject:")',
            'b:contains("Subject:")',
            'td:contains("Subject:")'
        ]
        
        for selector in subject_selectors:
            element = soup.find(text=re.compile('Subject:', re.IGNORECASE))
            if element:
                parent = element.parent
                next_element = parent.find_next_sibling()
                if next_element:
                    email_data['subject'] = next_element.get_text(strip=True)
                else:
                    full_text = parent.get_text()
                    match = re.search(r'Subject:\s*(.+)', full_text, re.IGNORECASE)
                    if match:
                        email_data['subject'] = match.group(1).strip()
                break
        
        # Date bilgisini bul
        date_selectors = [
            'div:contains("Date:")',
            'span:contains("Date:")', 
            'b:contains("Date:")',
            'td:contains("Date:")'
        ]
        
        for selector in date_selectors:
            element = soup.find(text=re.compile('Date:', re.IGNORECASE))
            if element:
                parent = element.parent
                next_element = parent.find_next_sibling()
                if next_element:
                    email_data['date'] = next_element.get_text(strip=True)
                else:
                    full_text = parent.get_text()
                    match = re.search(r'Date:\s*(.+)', full_text, re.IGNORECASE)
                    if match:
                        email_data['date'] = match.group(1).strip()
                break
        
        # İçerik bilgisini bul
        content_selectors = [
            '.email-content',
            '.mail-body',
            'pre',
            'div[style*="font-family"]'
        ]
        
        for selector in content_selectors:
            element = soup.select_one(selector)
            if element:
                email_data['content'] = element.get_text(strip=True)
                break
        
        if email_data.get('from') or email_data.get('subject'):
            email_data.update({
                'to': email_address,
                'received_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                'source': 'detail_page'
            })
            return email_data
            
    except Exception as e:
        logger.error(f"❌ Mail detay parsing hatası: {e}")
    
    return None

def extract_emails_simple(soup, email_address):
    """Basit parsing fallback"""
    emails = []
    
    # Tüm metni al
    all_text = soup.get_text()
    
    # Email pattern'leri ara
    email_patterns = [
        r'From:\s*([^\n\r<]+)',
        r'Sender:\s*([^\n\r<]+)',
        r'Subject:\s*([^\n\r<]+)',
        r'Konu:\s*([^\n\r<]+)',
    ]
    
    email_data = {}
    for pattern in email_patterns:
        matches = re.findall(pattern, all_text, re.IGNORECASE)
        if matches:
            key = 'from' if 'from' in pattern.lower() or 'sender' in pattern.lower() else 'subject'
            email_data[key] = matches[0].strip()
    
    if email_data:
        emails.append({
            **email_data,
            'to': email_address,
            'date': time.strftime('%Y-%m-%d %H:%M:%S'),
            'received_at': time.strftime('%Y-%m-%d %H:%M:%S'),
            'source': 'simple_parsing'
        })
    
    return emails

@app.route('/')
def home():
    return jsonify({
        "status": "active",
        "service": "EmailFake BeautifulSoup Scraper",
        "usage": {
            "all_emails": "POST /get-emails with {'email': 'address@domain.com'}",
            "last_email": "POST /get-last-email with {'email': 'address@domain.com'}"
        }
    })

@app.route('/get-emails', methods=['POST'])
def get_emails():
    """Tüm mailleri getir"""
    data = request.get_json()
    email = data.get('email', '')
    
    if not email:
        return jsonify({"error": "Email adresi gerekli"}), 400
    
    logger.info(f"📨 TÜM MAİLLER isteği: {email}")
    
    result = get_emails_from_emailfake(email, only_last_email=False)
    
    # Depolamaya kaydet
    if result['emails']:
        email_storage[email] = result['emails']
    
    return jsonify(result)

@app.route('/get-last-email', methods=['POST'])
def get_last_email():
    """Sadece son maili getir"""
    data = request.get_json()
    email = data.get('email', '')
    
    if not email:
        return jsonify({"error": "Email adresi gerekli"}), 400
    
    logger.info(f"📨 SON MAIL isteği: {email}")
    
    result = get_emails_from_emailfake(email, only_last_email=True)
    
    return jsonify(result)

@app.route('/emails/<email_address>')
def list_emails(email_address):
    """Depolanan mailleri göster"""
    if email_address in email_storage:
        return jsonify({
            "email": email_address,
            "total_emails": len(email_storage[email_address]),
            "emails": email_storage[email_address]
        })
    else:
        return jsonify({
            "email": email_address,
            "total_emails": 0,
            "emails": []
        })

if __name__ == '__main__':
    logger.info("🚀 EmailFake BeautifulSoup Scraper Başlatılıyor...")
    app.run(host='0.0.0.0', port=10000, debug=False)
