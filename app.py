# 📁 app.py - BASİT EMAILFAKE SCRAPER
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

def get_emails_simple(email_address):
    """Basit ve etkili email scraper"""
    try:
        # EmailFake URL yapısı
        domain = email_address.split('@')[1]
        
        if domain == "newdailys.com":
            # NewDailys için özel URL
            base_url = "https://tr.emailfake.com"
            inbox_url = f"{base_url}/mail"
        else:
            # Diğer domain'ler
            base_url = f"https://{domain}"
            inbox_url = f"{base_url}/mail"
        
        logger.info(f"🌐 Sayfa açılıyor: {inbox_url}")
        
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
                "emails": []
            }
        
        # HTML'i parse et
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Debug: Sayfa bilgilerini logla
        logger.info(f"📄 Sayfa başlığı: {soup.title.string if soup.title else 'Yok'}")
        
        emails = []
        
        # 1. Email adresini kontrol et
        email_elem = soup.find('span', id='email_ch_text')
        if email_elem:
            current_email = email_elem.get_text(strip=True)
            logger.info(f"📧 Aktif email: {current_email}")
        
        # 2. Tablo formatında mailleri ara
        tables = soup.find_all('table')
        for table in tables:
            rows = table.find_all('tr')[1:]  # İlk satır header olabilir
            for row in rows:
                cells = row.find_all(['td', 'div'])
                if len(cells) >= 2:
                    email_data = {
                        'from': cells[0].get_text(strip=True),
                        'subject': cells[1].get_text(strip=True),
                        'date': cells[2].get_text(strip=True) if len(cells) > 2 else '',
                        'to': email_address,
                        'received_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                        'source': 'table'
                    }
                    if email_data['from'] or email_data['subject']:
                        emails.append(email_data)
        
        # 3. Div formatında mailleri ara
        email_divs = soup.find_all('div', class_=re.compile(r'email|mail|message', re.I))
        for div in email_divs:
            # From bilgisini ara
            from_elem = div.find(['span', 'div'], class_=re.compile(r'from|sender', re.I))
            from_text = from_elem.get_text(strip=True) if from_elem else ''
            
            # Subject bilgisini ara
            subject_elem = div.find(['span', 'div'], class_=re.compile(r'subject|title', re.I))
            subject_text = subject_elem.get_text(strip=True) if subject_elem else ''
            
            if from_text or subject_text:
                emails.append({
                    'from': from_text,
                    'subject': subject_text,
                    'date': '',
                    'to': email_address,
                    'received_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'source': 'div'
                })
        
        # 4. JSON formatında mailleri ara
        script_tags = soup.find_all('script')
        for script in script_tags:
            if script.string:
                # JSON pattern'leri ara
                json_patterns = [
                    r'\{"from":"([^"]+)","subject":"([^"]+)"[^}]*\}',
                    r'"from":"([^"]+)".*?"subject":"([^"]+)"',
                    r"'from':'([^']+)'.*?'subject':'([^']+)'"
                ]
                
                for pattern in json_patterns:
                    matches = re.findall(pattern, script.string, re.DOTALL)
                    for match in matches:
                        if len(match) == 2:
                            emails.append({
                                'from': match[0],
                                'subject': match[1],
                                'date': '',
                                'to': email_address,
                                'received_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                                'source': 'json'
                            })
        
        logger.info(f"✅ {len(emails)} mail bulundu")
        
        return {
            "status": "success",
            "email": email_address,
            "total_emails": len(emails),
            "emails": emails,
            "url_used": inbox_url
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
        "service": "Simple EmailFake Scraper",
        "usage": "POST /get-emails with {'email': 'address@domain.com'}",
        "example": {
            "email": "fedotiko@newdailys.com"
        }
    })

@app.route('/get-emails', methods=['POST'])
def get_emails():
    """Mailleri getir"""
    data = request.get_json()
    email = data.get('email', '')
    
    if not email:
        return jsonify({"error": "Email adresi gerekli"}), 400
    
    logger.info(f"📨 İstek: {email}")
    
    result = get_emails_simple(email)
    
    # Depolamaya kaydet
    if result['emails']:
        email_storage[email] = result['emails']
    
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

@app.route('/test')
def test():
    """Test endpoint"""
    return jsonify({
        "status": "working",
        "timestamp": time.time(),
        "message": "API çalışıyor"
    })

if __name__ == '__main__':
    logger.info("🚀 Basit Email Scraper Başlatılıyor...")
    app.run(host='0.0.0.0', port=10000, debug=False)
