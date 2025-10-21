# 📁 app.py - GELİŞMİŞ CONNECTION HANDLING
from flask import Flask, jsonify, request
import requests
import time
import logging
import re
from bs4 import BeautifulSoup
import random

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Mail depolama
email_storage = {}

def get_emails_advanced(email_address):
    """Gelişmiş connection handling ile mailleri getir"""
    try:
        username, domain = email_address.split('@')
        
        # Doğru URL formatı
        base_url = "https://tr.emailfake.com"
        inbox_url = f"{base_url}/mail{domain}/{username}"
        
        logger.info(f"🌐 URL açılıyor: {inbox_url}")
        
        # Daha gerçekçi headers
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0',
        }
        
        # Session with retry and timeout
        session = requests.Session()
        session.headers.update(headers)
        
        # Daha uzun timeout ve retry mekanizması
        try:
            response = session.get(inbox_url, timeout=15, allow_redirects=True)
            logger.info(f"📄 Status Code: {response.status_code}")
        except requests.exceptions.Timeout:
            return {
                "status": "error",
                "error": "Timeout: Sayfa çok yavaş yükleniyor",
                "emails": []
            }
        except requests.exceptions.ConnectionError:
            return {
                "status": "error", 
                "error": "ConnectionError: Bağlantı kurulamadı",
                "emails": []
            }
        
        if response.status_code != 200:
            return {
                "status": "error",
                "error": f"HTTP {response.status_code}: Sayfa yüklenemedi",
                "url": inbox_url,
                "emails": []
            }
        
        # HTML parsing
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Sayfa analizi
        logger.info(f"📄 Sayfa başlığı: {soup.title.string if soup.title else 'Yok'}")
        
        emails = []
        
        # 1. ÖNCE: Sayfanın çalışıp çalışmadığını kontrol et
        if "404" in soup.get_text() or "Not Found" in soup.get_text():
            return {
                "status": "error",
                "error": "Sayfa bulunamadı (404)",
                "emails": []
            }
        
        # 2. Email adresini kontrol et
        email_elem = soup.find('span', id='email_ch_text')
        if email_elem:
            current_email = email_elem.get_text(strip=True)
            logger.info(f"📧 Aktif email: {current_email}")
        else:
            logger.warning("⚠️ Email adresi element'i bulunamadı")
        
        # 3. Farklı parsing method'larını dene
        
        # Method A: Tablo parsing
        tables = soup.find_all('table')
        logger.info(f"📊 {len(tables)} tablo bulundu")
        
        for table in tables:
            rows = table.find_all('tr')
            for row in rows[1:]:  # Skip header
                cells = row.find_all(['td', 'div'])
                if len(cells) >= 2:
                    from_text = cells[0].get_text(strip=True)
                    subject_text = cells[1].get_text(strip=True)
                    
                    if from_text or subject_text:
                        email_data = {
                            'from': from_text,
                            'subject': subject_text,
                            'date': cells[2].get_text(strip=True) if len(cells) > 2 else '',
                            'to': email_address,
                            'received_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                            'source': 'table'
                        }
                        emails.append(email_data)
        
        # Method B: Data attributes
        email_elements = soup.find_all(attrs={"data-from": True, "data-subject": True})
        for elem in email_elements:
            email_data = {
                'from': elem.get('data-from', ''),
                'subject': elem.get('data-subject', ''),
                'date': elem.get('data-date', ''),
                'to': email_address,
                'received_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                'source': 'data_attrs'
            }
            if email_data['from'] or email_data['subject']:
                emails.append(email_data)
        
        # Method C: Specific classes
        email_divs = soup.find_all('div', class_=lambda x: x and any(cls in x for cls in ['email', 'mail', 'message']))
        for div in email_divs:
            # Try to extract from common patterns
            from_elem = div.find(class_=re.compile(r'from|sender', re.I))
            subject_elem = div.find(class_=re.compile(r'subject|title', re.I))
            
            if from_elem or subject_elem:
                email_data = {
                    'from': from_elem.get_text(strip=True) if from_elem else '',
                    'subject': subject_elem.get_text(strip=True) if subject_elem else '',
                    'date': '',
                    'to': email_address,
                    'received_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'source': 'div_classes'
                }
                if email_data['from'] or email_data['subject']:
                    emails.append(email_data)
        
        # Method D: Fallback - find any text that looks like email info
        if not emails:
            logger.info("🔍 Fallback parsing deneniyor...")
            # Look for common email patterns in text
            text_content = soup.get_text()
            email_patterns = [
                r'From:\s*([^\n]+)',
                r'Gönderen:\s*([^\n]+)',
                r'Subject:\s*([^\n]+)',
                r'Konu:\s*([^\n]+)',
            ]
            
            for pattern in email_patterns:
                matches = re.findall(pattern, text_content, re.IGNORECASE)
                for match in matches:
                    if len(match.strip()) > 3:
                        key = 'from' if 'from' in pattern.lower() or 'gönderen' in pattern.lower() else 'subject'
                        # Find existing email or create new
                        found = False
                        for email in emails:
                            if key not in email or not email[key]:
                                email[key] = match.strip()
                                found = True
                                break
                        
                        if not found:
                            emails.append({
                                key: match.strip(),
                                'from' if key == 'subject' else 'subject': '',
                                'date': '',
                                'to': email_address,
                                'received_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                                'source': 'text_pattern'
                            })
        
        logger.info(f"🎯 {len(emails)} mail bulundu")
        
        return {
            "status": "success",
            "email": email_address,
            "total_emails": len(emails),
            "emails": emails,
            "url_used": inbox_url,
            "page_title": soup.title.string if soup.title else "No title",
            "page_loaded": True
        }
        
    except Exception as e:
        logger.error(f"❌ Beklenmeyen hata: {str(e)}")
        return {
            "status": "error",
            "error": f"Beklenmeyen hata: {str(e)}",
            "emails": []
        }

@app.route('/')
def home():
    return jsonify({
        "status": "active",
        "service": "EmailFake Scraper - Advanced",
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
    
    result = get_emails_advanced(email)
    
    if result['emails']:
        email_storage[email] = result['emails']
    
    return jsonify(result)

@app.route('/check-url', methods=['POST'])
def check_url():
    """URL kontrol endpoint'i"""
    data = request.get_json()
    email = data.get('email', 'fedotiko@newdailys.com')
    
    try:
        username, domain = email.split('@')
        url = f"https://tr.emailfake.com/mail{domain}/{username}"
        
        # Sadece HEAD isteği gönder (daha hızlı)
        response = requests.head(url, timeout=10, allow_redirects=True)
        
        return jsonify({
            "email": email,
            "url": url,
            "status_code": response.status_code,
            "content_type": response.headers.get('content-type', ''),
            "server": response.headers.get('server', ''),
            "accessible": response.status_code == 200
        })
        
    except Exception as e:
        return jsonify({
            "email": email,
            "error": str(e),
            "accessible": False
        })

if __name__ == '__main__':
    logger.info("🚀 Gelişmiş Email Scraper Başlatılıyor...")
    app.run(host='0.0.0.0', port=10000, debug=False)
