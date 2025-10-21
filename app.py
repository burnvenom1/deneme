# 📁 app.py - SSL SORUNSUZ
from flask import Flask, jsonify, request
import requests
import time
import logging
import re
from bs4 import BeautifulSoup
import urllib3
import warnings

# SSL warning'larını kapat
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings('ignore', message='Unverified HTTPS request')

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Mail depolama
email_storage = {}

def get_emails_safe(email_address):
    """Güvenli ve SSL sorunsuz email getirme"""
    try:
        username, domain = email_address.split('@')
        
        # Doğru URL - sadece bir tane kullan
        inbox_url = f"https://tr.emailfake.com/mail{domain}/{username}"
        
        logger.info(f"🌐 Sayfa açılıyor: {inbox_url}")
        
        # Basit session - SSL verify kapalı
        session = requests.Session()
        session.verify = False  # SSL sertifikasını doğrulama
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'tr-TR,tr;q=0.9,en;q=0.8',
        }
        
        # Daha kısa timeout ile dene
        response = session.get(inbox_url, headers=headers, timeout=10, verify=False)
        
        if response.status_code != 200:
            return {
                "status": "error",
                "error": f"HTTP {response.status_code}: Sayfa yüklenemedi",
                "emails": []
            }
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Debug: Sayfa içeriğini kontrol et
        page_title = soup.title.string if soup.title else "No title"
        logger.info(f"📄 Sayfa başlığı: {page_title}")
        
        # Email adresini kontrol et
        email_elem = soup.find('span', id='email_ch_text')
        if email_elem:
            current_email = email_elem.get_text(strip=True)
            logger.info(f"📧 Aktif email: {current_email}")
        
        # 1. ÖNCE: Email listesi container'ını ara
        emails = []
        
        # EmailFake'in email listesi için spesifik container
        email_container = soup.find('div', class_=re.compile(r'email|mail|list', re.I))
        if not email_container:
            # Fallback: tüm sayfayı tara
            email_container = soup
        
        # 2. Tablo formatında mailleri ara
        tables = email_container.find_all('table')
        logger.info(f"📊 {len(tables)} tablo bulundu")
        
        for table_idx, table in enumerate(tables):
            rows = table.find_all('tr')
            logger.info(f"📋 Tablo {table_idx}: {len(rows)} satır")
            
            for row_idx, row in enumerate(rows):
                # Header satırını atla (genellikle ilk satır)
                if row_idx == 0 and any('from' in cell.get_text().lower() or 'subject' in cell.get_text().lower() for cell in row.find_all(['td', 'th', 'div'])):
                    continue
                
                cells = row.find_all(['td', 'div'])
                if len(cells) >= 2:
                    from_text = cells[0].get_text(strip=True)
                    subject_text = cells[1].get_text(strip=True)
                    
                    # Basit filtreleme
                    if from_text and subject_text and len(subject_text) > 5:
                        email_data = {
                            'from': from_text,
                            'subject': subject_text,
                            'date': cells[2].get_text(strip=True) if len(cells) > 2 else '',
                            'to': email_address,
                            'received_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                            'source': f'table_{table_idx}_row_{row_idx}'
                        }
                        emails.append(email_data)
                        logger.info(f"✅ Mail bulundu: {from_text} - {subject_text}")
        
        # 3. Eğer tabloda mail bulamazsak, linkleri kontrol et
        if not emails:
            logger.info("🔍 Linkler kontrol ediliyor...")
            mail_links = email_container.find_all('a', href=re.compile(r'mail|email|message', re.I))
            for link in mail_links:
                link_text = link.get_text(strip=True)
                if len(link_text) > 10:  # Anlamlı metin
                    emails.append({
                        'from': 'Link',
                        'subject': link_text,
                        'date': '',
                        'to': email_address,
                        'received_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                        'source': 'link'
                    })
        
        logger.info(f"🎯 {len(emails)} mail bulundu")
        
        return {
            "status": "success",
            "email": email_address,
            "total_emails": len(emails),
            "emails": emails,
            "url_used": inbox_url,
            "page_title": page_title
        }
        
    except requests.exceptions.Timeout:
        logger.error("⏰ Timeout: Sayfa çok yavaş")
        return {
            "status": "error",
            "error": "Timeout: Sayfa çok yavaş yükleniyor",
            "emails": []
        }
    except requests.exceptions.ConnectionError:
        logger.error("🔌 ConnectionError: Bağlantı hatası")
        return {
            "status": "error", 
            "error": "ConnectionError: Bağlantı kurulamadı",
            "emails": []
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
        "service": "EmailFake Scraper - SSL Fixed",
        "usage": "POST /get-emails with {'email': 'address@domain.com'}",
        "example": {"email": "fedotiko@newdailys.com"}
    })

@app.route('/get-emails', methods=['POST'])
def get_emails():
    """Mailleri getir"""
    data = request.get_json()
    email = data.get('email', '')
    
    if not email:
        return jsonify({"error": "Email adresi gerekli"}), 400
    
    logger.info(f"📨 İstek: {email}")
    
    result = get_emails_safe(email)
    
    if result['emails']:
        email_storage[email] = result['emails']
    
    return jsonify(result)

@app.route('/check-connection', methods=['POST'])
def check_connection():
    """Bağlantı testi"""
    data = request.get_json()
    email = data.get('email', 'fedotiko@newdailys.com')
    
    try:
        username, domain = email.split('@')
        url = f"https://tr.emailfake.com/mail{domain}/{username}"
        
        # Hızlı HEAD isteği
        session = requests.Session()
        session.verify = False
        
        start_time = time.time()
        response = session.head(url, timeout=5, verify=False)
        response_time = time.time() - start_time
        
        return jsonify({
            "email": email,
            "url": url,
            "status_code": response.status_code,
            "response_time": f"{response_time:.2f}s",
            "accessible": response.status_code == 200,
            "content_type": response.headers.get('content-type', '')
        })
        
    except Exception as e:
        return jsonify({
            "email": email,
            "error": str(e),
            "accessible": False
        })

@app.route('/simple-test')
def simple_test():
    """Basit test endpoint"""
    return jsonify({
        "status": "working",
        "timestamp": time.time(),
        "message": "API çalışıyor - SSL sorunları giderildi"
    })

if __name__ == '__main__':
    logger.info("🚀 SSL Sorunsuz Email Scraper Başlatılıyor...")
    app.run(host='0.0.0.0', port=10000, debug=False)
