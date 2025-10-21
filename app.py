# 📁 app.py - DOĞRU EMAILFAKE URL YAPISI
from flask import Flask, jsonify, request
import requests
import time
import logging
import re
from bs4 import BeautifulSoup
from urllib.request import build_opener, HTTPCookieProcessor, Request
from urllib.parse import urljoin, quote
import http.cookiejar

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Mail depolama
email_storage = {}

def get_emails_from_emailfake(email_address, only_last_email=False):
    """EmailFake'den mailleri çek - DOĞRU URL YAPISI"""
    try:
        # Cookie jar oluştur
        cookie_jar = http.cookiejar.CookieJar()
        session = build_opener(HTTPCookieProcessor(cookie_jar))
        
        domain = email_address.split("@")[1]
        username = email_address.split("@")[0]
        
        # DOĞRU URL YAPISI: https://tr.emailfake.com/mail
        base_url = f"https://tr.{domain}" if domain == "emailfake.com" else f"https://{domain}"
        mail_url = f"{base_url}/mail"
        
        logger.info(f"🌐 EmailFake açılıyor: {mail_url}")
        
        # Sayfayı aç
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'tr-TR,tr;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        req = Request(mail_url, headers=headers)
        response = session.open(req)
        html_content = response.read().decode("utf-8")
        
        # BeautifulSoup ile parse et
        soup = BeautifulSoup(html_content, 'html.parser')
        
        logger.info(f"🔍 Sayfa başlığı: {soup.title.string if soup.title else 'Bulunamadı'}")
        
        emails = []
        
        # 1. ÖNCE: Email adresini kontrol et
        email_element = soup.find('span', {'id': 'email_ch_text'})
        if email_element:
            current_email = email_element.get_text(strip=True)
            logger.info(f"📧 Aktif email: {current_email}")
        
        # 2. Mail listesini bul - EmailFake'e özel selector'lar
        logger.info("🔍 EmailFake mail listesi aranıyor...")
        
        # EmailFake'in mail listesi için selector'lar
        mail_selectors = [
            'div.email-list',
            'div.mail-list', 
            'table.table',
            'div.list-group',
            'tr.email-row',
            'div.email-item'
        ]
        
        mail_container = None
        for selector in mail_selectors:
            mail_container = soup.select_one(selector)
            if mail_container:
                logger.info(f"✅ Mail konteyneri bulundu: {selector}")
                break
        
        if mail_container:
            # Mail öğelerini bul
            mail_items = mail_container.find_all(['div', 'tr', 'li'], class_=re.compile(r'email|mail|message', re.I))
            
            if not mail_items:
                # Direkt child'ları kontrol et
                mail_items = mail_container.find_all(recursive=False)
            
            logger.info(f"📨 {len(mail_items)} mail öğesi bulundu")
            
            for item in mail_items:
                email_data = extract_email_from_item(item, email_address)
                if email_data:
                    emails.append(email_data)
                    if only_last_email:
                        break
        
        # 3. Eğer mail bulamazsak, sayfadaki tüm linkleri kontrol et
        if not emails:
            logger.info("🔍 Sayfadaki tüm linkler kontrol ediliyor...")
            all_links = soup.find_all('a', href=True)
            mail_links = []
            
            for link in all_links:
                href = link['href']
                if any(keyword in href.lower() for keyword in ['mail', 'email', 'inbox', 'message']):
                    mail_links.append(href)
            
            logger.info(f"🔗 {len(mail_links)} mail linki bulundu")
            
            for i, link in enumerate(mail_links):
                if only_last_email and i > 0:
                    break
                    
                try:
                    # Mail detay sayfasını aç
                    if link.startswith('/'):
                        detail_url = urljoin(base_url, link)
                    else:
                        detail_url = link
                    
                    logger.info(f"📧 Mail detayı: {detail_url}")
                    
                    detail_req = Request(detail_url, headers=headers)
                    detail_response = session.open(detail_req)
                    detail_html = detail_response.read().decode("utf-8")
                    detail_soup = BeautifulSoup(detail_html, 'html.parser')
                    
                    email_data = extract_email_details(detail_soup, email_address)
                    if email_data:
                        emails.append(email_data)
                        
                except Exception as e:
                    logger.error(f"❌ Mail detay hatası: {e}")
        
        # 4. Debug: Sayfa içeriğini logla
        if not emails:
            logger.info("🔍 Sayfa içeriği debug...")
            # Sayfadaki tüm text'leri logla (ilk 2000 karakter)
            all_text = soup.get_text()
            logger.info(f"📄 Sayfa metni (ilk 1000 karakter): {all_text[:1000]}")
            
            # Tüm div'leri logla
            divs = soup.find_all('div', class_=True)
            for div in divs[:10]:  # İlk 10 div
                logger.info(f"🏷️ Div class: {div.get('class')}")
        
        logger.info(f"📨 {len(emails)} mail başarıyla alındı")
        
        return {
            "status": "success" if emails else "no_emails",
            "email": email_address,
            "total_emails": len(emails),
            "emails": emails,
            "only_last_email": only_last_email,
            "page_title": soup.title.string if soup.title else "Unknown"
        }
        
    except Exception as e:
        logger.error(f"❌ Scraper hatası: {e}")
        return {
            "status": "error",
            "error": str(e),
            "emails": []
        }

def extract_email_from_item(item, email_address):
    """Mail öğesinden email verilerini çıkar"""
    try:
        # Farklı formatlar için deneme
        email_data = {}
        
        # Format 1: Tablo satırı
        cells = item.find_all(['td', 'div'])
        if len(cells) >= 2:
            email_data['from'] = cells[0].get_text(strip=True)
            email_data['subject'] = cells[1].get_text(strip=True)
            if len(cells) >= 3:
                email_data['date'] = cells[2].get_text(strip=True)
        
        # Format 2: Span veya div içinde
        if not email_data.get('from'):
            from_elem = item.find(['span', 'div'], class_=re.compile(r'from|sender', re.I))
            if from_elem:
                email_data['from'] = from_elem.get_text(strip=True)
        
        if not email_data.get('subject'):
            subject_elem = item.find(['span', 'div'], class_=re.compile(r'subject|title', re.I))
            if subject_elem:
                email_data['subject'] = subject_elem.get_text(strip=True)
        
        # Format 3: Data attribute'ları
        if not email_data.get('from'):
            from_data = item.get('data-from') or item.get('data-sender')
            if from_data:
                email_data['from'] = from_data
        
        if not email_data.get('subject'):
            subject_data = item.get('data-subject')
            if subject_data:
                email_data['subject'] = subject_data
        
        # Eğer from veya subject varsa, email olarak kabul et
        if email_data.get('from') or email_data.get('subject'):
            return {
                'from': email_data.get('from', 'Bilinmiyor'),
                'subject': email_data.get('subject', 'Konu Yok'),
                'date': email_data.get('date', time.strftime('%Y-%m-%d %H:%M:%S')),
                'to': email_address,
                'received_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                'source': 'emailfake_page'
            }
            
    except Exception as e:
        logger.error(f"❌ Mail öğesi parsing hatası: {e}")
    
    return None

def extract_email_details(soup, email_address):
    """Mail detay sayfasından email bilgilerini çıkar"""
    try:
        # EmailFake detay sayfası formatı
        email_data = {}
        
        # From bilgisi
        from_elem = soup.find(text=re.compile(r'From:|Gönderen:', re.I))
        if from_elem:
            from_parent = from_elem.parent
            from_value = from_parent.find_next_sibling()
            if from_value:
                email_data['from'] = from_value.get_text(strip=True)
        
        # Subject bilgisi  
        subject_elem = soup.find(text=re.compile(r'Subject:|Konu:', re.I))
        if subject_elem:
            subject_parent = subject_elem.parent
            subject_value = subject_parent.find_next_sibling()
            if subject_value:
                email_data['subject'] = subject_value.get_text(strip=True)
        
        # Date bilgisi
        date_elem = soup.find(text=re.compile(r'Date:|Tarih:', re.I))
        if date_elem:
            date_parent = date_elem.parent
            date_value = date_parent.find_next_sibling()
            if date_value:
                email_data['date'] = date_value.get_text(strip=True)
        
        # İçerik
        content_elem = soup.find('div', class_=re.compile(r'content|body|message', re.I))
        if not content_elem:
            content_elem = soup.find('pre')
        if content_elem:
            email_data['content'] = content_elem.get_text(strip=True)
        
        if email_data.get('from') or email_data.get('subject'):
            return {
                **email_data,
                'to': email_address,
                'received_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                'source': 'emailfake_detail'
            }
            
    except Exception as e:
        logger.error(f"❌ Mail detay parsing hatası: {e}")
    
    return None

@app.route('/')
def home():
    return jsonify({
        "status": "active", 
        "service": "EmailFake Scraper - Correct URL Structure",
        "usage": "POST /get-emails with {'email': 'address@domain.com'}"
    })

@app.route('/get-emails', methods=['POST'])
def get_emails():
    """Mailleri getir"""
    data = request.get_json()
    email = data.get('email', '')
    
    if not email:
        return jsonify({"error": "Email adresi gerekli"}), 400
    
    logger.info(f"📨 İstek: {email}")
    
    result = get_emails_from_emailfake(email, only_last_email=False)
    
    if result['emails']:
        email_storage[email] = result['emails']
    
    return jsonify(result)

@app.route('/get-last-email', methods=['POST'])
def get_last_email():
    """Son maili getir"""
    data = request.get_json()
    email = data.get('email', '')
    
    if not email:
        return jsonify({"error": "Email adresi gerekli"}), 400
    
    result = get_emails_from_emailfake(email, only_last_email=True)
    return jsonify(result)

@app.route('/debug-page', methods=['POST'])
def debug_page():
    """Sayfa debug endpoint'i"""
    data = request.get_json()
    email = data.get('email', '')
    
    try:
        import requests
        domain = email.split('@')[1]
        base_url = f"https://tr.{domain}" if domain == "emailfake.com" else f"https://{domain}"
        url = f"{base_url}/mail"
        
        response = requests.get(url)
        
        return jsonify({
            "status": "success",
            "url": url,
            "status_code": response.status_code,
            "content_sample": response.text[:1000],
            "headers": dict(response.headers)
        })
        
    except Exception as e:
        return jsonify({"error": str(e)})

if __name__ == '__main__':
    logger.info("🚀 EmailFake Scraper (Doğru URL) Başlatılıyor...")
    app.run(host='0.0.0.0', port=10000, debug=False)
