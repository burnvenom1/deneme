# 📁 app.py - DOĞRU URL FORMATI
from flask import Flask, jsonify, request
import requests
import time
import logging
import re
from bs4 import BeautifulSoup

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Mail depolama
email_storage = {}

def get_emails_correct_url(email_address):
    """Doğru URL formatı ile mailleri getir"""
    try:
        username, domain = email_address.split('@')
        
        # DOĞRU URL FORMATI: https://tr.emailfake.com/{domain}/{username}
        base_url = "https://tr.emailfake.com"
        inbox_url = f"{base_url}/mail{domain}/{username}"
        
        logger.info(f"🌐 Doğru URL açılıyor: {inbox_url}")
        
        # Session oluştur
        session = requests.Session()
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'tr-TR,tr;q=0.9,en;q=0.8',
        }
        
        # Sayfayı getir
        response = session.get(inbox_url, headers=headers, timeout=10)
        
        if response.status_code != 200:
            return {
                "status": "error",
                "error": f"Sayfa yüklenemedi: {response.status_code}",
                "url_used": inbox_url,
                "emails": []
            }
        
        # HTML'i parse et
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Debug: Sayfa bilgilerini logla
        logger.info(f"📄 Sayfa başlığı: {soup.title.string if soup.title else 'Yok'}")
        logger.info(f"📄 Sayfa URL: {inbox_url}")
        
        emails = []
        
        # 1. Aktif email adresini kontrol et
        email_elem = soup.find('span', id='email_ch_text')
        if email_elem:
            current_email = email_elem.get_text(strip=True)
            logger.info(f"📧 Aktif email: {current_email}")
        
        # 2. Tablolardan mailleri çıkar
        tables = soup.find_all('table')
        logger.info(f"🔍 {len(tables)} tablo bulundu")
        
        for i, table in enumerate(tables):
            rows = table.find_all('tr')
            logger.info(f"📊 Tablo {i+1}: {len(rows)} satır")
            
            for j, row in enumerate(rows[1:]):  # İlk satır header olabilir
                cells = row.find_all(['td', 'div'])
                
                if len(cells) >= 2:
                    email_data = {
                        'from': cells[0].get_text(strip=True),
                        'subject': cells[1].get_text(strip=True),
                        'date': cells[2].get_text(strip=True) if len(cells) > 2 else '',
                        'to': email_address,
                        'received_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                        'source': f'table_{i+1}_row_{j+1}'
                    }
                    
                    # Boş olmayan mailleri ekle
                    if email_data['from'].strip() or email_data['subject'].strip():
                        emails.append(email_data)
                        logger.info(f"✅ Mail bulundu: {email_data['from']} - {email_data['subject']}")
        
        # 3. Email listesi container'ını ara
        email_containers = soup.find_all('div', class_=re.compile(r'email|mail|list|container', re.I))
        logger.info(f"🔍 {len(email_containers)} email konteyneri bulundu")
        
        for container in email_containers:
            # Container içindeki tüm linkleri kontrol et
            links = container.find_all('a', href=True)
            for link in links:
                link_text = link.get_text(strip=True)
                if link_text and len(link_text) > 5:  # Anlamlı metin
                    emails.append({
                        'from': 'Link',
                        'subject': link_text,
                        'date': '',
                        'to': email_address,
                        'received_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                        'source': 'link_container'
                    })
        
        # 4. Script tag'lerinden JSON verilerini ara
        scripts = soup.find_all('script')
        for script in scripts:
            if script.string:
                # Email verisi içeren JSON'ları ara
                json_patterns = [
                    r'"from":"([^"]+)".*?"subject":"([^"]+)"',
                    r"'from':'([^']+)'.*?'subject':'([^']+)'",
                    r'from[^:]*:[^"]*"([^"]+)".*?subject[^:]*:[^"]*"([^"]+)"'
                ]
                
                for pattern in json_patterns:
                    matches = re.findall(pattern, script.string, re.DOTALL)
                    for match in matches:
                        if len(match) == 2 and (match[0].strip() or match[1].strip()):
                            emails.append({
                                'from': match[0].strip(),
                                'subject': match[1].strip(),
                                'date': '',
                                'to': email_address,
                                'received_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                                'source': 'json_script'
                            })
        
        logger.info(f"🎯 Toplam {len(emails)} mail bulundu")
        
        return {
            "status": "success",
            "email": email_address,
            "total_emails": len(emails),
            "emails": emails,
            "url_used": inbox_url,
            "page_title": soup.title.string if soup.title else "No title"
        }
        
    except Exception as e:
        logger.error(f"❌ Hata: {e}")
        return {
            "status": "error",
            "error": str(e),
            "emails": []
        }

@app.route('/')
def home():
    return jsonify({
        "status": "active",
        "service": "EmailFake Scraper - Correct URL Format",
        "usage": "POST /get-emails with {'email': 'address@domain.com'}",
        "url_format": "https://tr.emailfake.com/{domain}/{username}",
        "example": {
            "email": "fedotiko@newdailys.com",
            "url": "https://tr.emailfake.com/newdailys.com/fedotiko"
        }
    })

@app.route('/get-emails', methods=['POST'])
def get_emails():
    """Mailleri getir - DOĞRU URL FORMATI"""
    data = request.get_json()
    email = data.get('email', '')
    
    if not email:
        return jsonify({"error": "Email adresi gerekli"}), 400
    
    logger.info(f"📨 İstek: {email}")
    
    result = get_emails_correct_url(email)
    
    # Depolamaya kaydet
    if result['emails']:
        email_storage[email] = result['emails']
    
    return jsonify(result)

@app.route('/debug-url', methods=['POST'])
def debug_url():
    """URL debug endpoint"""
    data = request.get_json()
    email = data.get('email', 'fedotiko@newdailys.com')
    
    try:
        username, domain = email.split('@')
        correct_url = f"https://tr.emailfake.com/{domain}/{username}"
        
        session = requests.Session()
        response = session.get(correct_url, timeout=10)
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        return jsonify({
            "email": email,
            "correct_url": correct_url,
            "status_code": response.status_code,
            "page_title": soup.title.string if soup.title else "No title",
            "email_element_exists": bool(soup.find('span', id='email_ch_text')),
            "tables_count": len(soup.find_all('table')),
            "first_200_chars": response.text[:200]
        })
        
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/test-url/<email>')
def test_url(email):
    """URL test endpoint (GET)"""
    try:
        username, domain = email.split('@')
        correct_url = f"https://tr.emailfake.com/{domain}/{username}"
        
        return jsonify({
            "email": email,
            "generated_url": correct_url,
            "test_link": f'<a href="{correct_url}" target="_blank">Test URL</a>'
        })
        
    except Exception as e:
        return jsonify({"error": str(e)})

if __name__ == '__main__':
    logger.info("🚀 EmailFake Scraper (Doğru URL) Başlatılıyor...")
    app.run(host='0.0.0.0', port=10000, debug=False)
