# 📁 app.py - EMAILFAKE HTML SCRAPER
from urllib.request import build_opener, HTTPCookieProcessor, Request
from urllib.parse import urljoin
import http.cookiejar
from lxml import etree, html
import time
import logging
from flask import Flask, jsonify, request
from pprint import pprint

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Mail depolama
email_storage = {}

def get_emails_from_emailfake(email_address, only_last_email=False):
    """EmailFake'den mailleri çek"""
    try:
        # Cookie jar oluştur
        cookie_jar = http.cookiejar.CookieJar()
        session = build_opener(HTTPCookieProcessor(cookie_jar))
        
        domain = email_address.split("@")[1]
        username = email_address.split("@")[0]
        
        base_url = f"https://{domain}"
        inbox_url = f"{base_url}/inbox/{email_address}"
        
        logger.info(f"🌐 EmailFake açılıyor: {inbox_url}")
        
        # Sayfayı aç
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        req = Request(inbox_url, headers=headers)
        response = session.open(req)
        html_content = response.read().decode("utf-8")
        
        # HTML'i parse et
        tree = etree.HTML(html_content)
        
        emails = []
        email_links = []
        
        # 1. ÖNCE: Mail listesini bul
        logger.info("🔍 Mail listesi aranıyor...")
        
        # EmailFake'e özel selector'lar
        mail_selectors = [
            "//a[contains(@href, '/inbox/') and contains(@href, '/')]",
            "//div[contains(@class, 'email')]//a",
            "//tr[contains(@class, 'email')]//a",
            "//table//tr//a[contains(@href, '/inbox/')]",
            "//a[contains(@class, 'email-link')]",
        ]
        
        for selector in mail_selectors:
            links = tree.xpath(selector)
            if links:
                logger.info(f"✅ {len(links)} mail linki bulundu")
                email_links = links
                break
        
        # Eğer link bulamazsak, direkt tablo satırlarını oku
        if not email_links:
            logger.info("🔍 Tablo satırları kontrol ediliyor...")
            table_rows = tree.xpath("//table//tr[position()>1]")  # İlk satır header olabilir
            if table_rows:
                logger.info(f"✅ {len(table_rows)} tablo satırı bulundu")
                # Tablo satırlarından mailleri çıkar
                for row in table_rows:
                    email_data = extract_email_from_table_row(row)
                    if email_data:
                        emails.append(email_data)
                        if only_last_email:
                            break
        
        # 2. SONRA: Her mailin detay sayfasına git
        for i, link in enumerate(email_links):
            if only_last_email and i > 0:
                break
                
            try:
                mail_url = link.get('href')
                if mail_url:
                    # URL'yi tamamla
                    if mail_url.startswith('/'):
                        mail_url = urljoin(base_url, mail_url)
                    elif not mail_url.startswith('http'):
                        mail_url = urljoin(inbox_url, mail_url)
                    
                    logger.info(f"📧 Mail detayı açılıyor: {mail_url}")
                    
                    # Mail detay sayfasını aç
                    mail_req = Request(mail_url, headers=headers)
                    mail_response = session.open(mail_req)
                    mail_html = mail_response.read().decode("utf-8")
                    
                    # Mail detaylarını parse et
                    email_data = extract_email_details(mail_html, email_address)
                    if email_data:
                        emails.append(email_data)
                        
            except Exception as e:
                logger.error(f"❌ Mail detay hatası: {e}")
                continue
        
        # 3. Eğer hiç mail bulamazsak, basit parsing yap
        if not emails:
            logger.info("🔍 Basit parsing deneniyor...")
            emails = extract_emails_simple(tree, email_address)
        
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

def extract_email_from_table_row(row):
    """Tablo satırından email verilerini çıkar"""
    try:
        cells = row.xpath(".//td")
        if len(cells) >= 3:
            return {
                'from': ' '.join(cells[0].xpath(".//text()")).strip(),
                'subject': ' '.join(cells[1].xpath(".//text()")).strip(),
                'date': ' '.join(cells[2].xpath(".//text()")).strip(),
                'received_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                'source': 'table_row'
            }
    except:
        pass
    return None

def extract_email_details(mail_html, email_address):
    """Mail detay sayfasından email bilgilerini çıkar"""
    try:
        tree = etree.HTML(mail_html)
        
        # Farklı email detail formatları
        email_data = {}
        
        # Format 1: Email başlık bilgileri
        from_selectors = [
            "//div[contains(text(), 'From:')]/following-sibling::div",
            "//span[contains(text(), 'From:')]/following-sibling::span",
            "//b[contains(text(), 'From:')]/following-sibling::text()",
        ]
        
        subject_selectors = [
            "//div[contains(text(), 'Subject:')]/following-sibling::div",
            "//span[contains(text(), 'Subject:')]/following-sibling::span", 
            "//b[contains(text(), 'Subject:')]/following-sibling::text()",
        ]
        
        date_selectors = [
            "//div[contains(text(), 'Date:')]/following-sibling::div",
            "//span[contains(text(), 'Date:')]/following-sibling::span",
            "//b[contains(text(), 'Date:')]/following-sibling::text()",
        ]
        
        # Göndereni bul
        for selector in from_selectors:
            elements = tree.xpath(selector)
            if elements:
                email_data['from'] = ' '.join(elements[0].xpath(".//text()")).strip()
                break
        
        # Konuyu bul
        for selector in subject_selectors:
            elements = tree.xpath(selector)
            if elements:
                email_data['subject'] = ' '.join(elements[0].xpath(".//text()")).strip()
                break
        
        # Tarihi bul
        for selector in date_selectors:
            elements = tree.xpath(selector)
            if elements:
                email_data['date'] = ' '.join(elements[0].xpath(".//text()")).strip()
                break
        
        # İçeriği bul
        content_selectors = [
            "//div[contains(@class, 'email-content')]",
            "//div[contains(@class, 'mail-body')]",
            "//pre",
            "//div[contains(@style, 'font-family')]"
        ]
        
        for selector in content_selectors:
            elements = tree.xpath(selector)
            if elements:
                email_data['content'] = ' '.join(elements[0].xpath(".//text()")).strip()
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

def extract_emails_simple(tree, email_address):
    """Basit parsing fallback"""
    emails = []
    
    # Tüm metinleri tarayıp email benzeri yapıları bul
    all_text = ' '.join(tree.xpath("//text()"))
    
    # Email pattern'leri ara
    import re
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
        "service": "EmailFake HTML Scraper",
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
    logger.info("🚀 EmailFake HTML Scraper Başlatılıyor...")
    app.run(host='0.0.0.0', port=10000, debug=False)
