# 📁 app.py - API + WEBSOCKET KARMA ÇÖZÜM
from flask import Flask, jsonify, request
import requests
import time
import logging
import socketio
import re
import json

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

email_storage = {}

def get_emails_via_api(email_address):
    """API veya sayfa scraping ile önceki mailleri al"""
    try:
        domain = email_address.split('@')[1]
        
        # 1. EmailFake API endpoint'ini dene
        api_urls = [
            f"https://{domain}/api/emails/{email_address}",
            f"https://{domain}/api/inbox/{email_address}",
            f"https://{domain}/inbox/{email_address}/json",
            f"https://{domain}/inbox/{email_address}",
        ]
        
        for api_url in api_urls:
            try:
                logger.info(f"🔍 API deneniyor: {api_url}")
                response = requests.get(api_url, timeout=5)
                
                if response.status_code == 200:
                    # JSON response
                    data = response.json()
                    if isinstance(data, list) or 'emails' in data:
                        logger.info(f"✅ API başarılı: {len(data) if isinstance(data, list) else len(data.get('emails', []))} mail")
                        return data
            except:
                continue
        
        # 2. Sayfayı çek ve mailleri parse et
        logger.info(f"🌐 Sayfa çekiliyor: {email_address}")
        inbox_url = f"https://{domain}/inbox/{email_address}"
        response = requests.get(inbox_url, timeout=10)
        
        if response.status_code == 200:
            # HTML'den email verilerini çıkar
            emails = extract_emails_from_html(response.text)
            if emails:
                logger.info(f"✅ HTML'den {len(emails)} mail çıkarıldı")
                return emails
            
        return []
        
    except Exception as e:
        logger.error(f"❌ API hatası: {e}")
        return []

def extract_emails_from_html(html):
    """HTML'den email verilerini çıkar"""
    emails = []
    
    # Script tag'lerinden JSON verilerini ara
    script_pattern = r'<script[^>]*>.*?(var\s+\w+\s*=\s*\{.*?\}).*?</script>'
    script_matches = re.findall(script_pattern, html, re.DOTALL | re.IGNORECASE)
    
    for script in script_matches:
        # JSON benzeri yapıları ara
        json_patterns = [
            r'\{[^{}]*"[^"]*"[^{}]*:[^{}]*[^}]*\}',
            r'\[[^\]]*\{[^}]*\}[^\]]*\]',
        ]
        
        for pattern in json_patterns:
            matches = re.findall(pattern, script, re.DOTALL)
            for match in matches:
                try:
                    data = json.loads(match)
                    if isinstance(data, list) and len(data) > 0:
                        # Mail listesi
                        for item in data:
                            if isinstance(item, dict) and ('from' in item or 'subject' in item):
                                emails.append(item)
                    elif isinstance(data, dict) and ('from' in data or 'subject' in data):
                        # Tekil mail
                        emails.append(data)
                except:
                    continue
    
    # Tablo satırlarından mailleri çıkar
    table_pattern = r'<tr[^>]*>.*?<td[^>]*>(.*?)</td>.*?<td[^>]*>(.*?)</td>.*?<td[^>]*>(.*?)</td>'
    table_matches = re.findall(table_pattern, html, re.DOTALL | re.IGNORECASE)
    
    for match in table_matches:
        if len(match) >= 2:
            emails.append({
                'from': clean_html(match[0]),
                'subject': clean_html(match[1]),
                'date': clean_html(match[2]) if len(match) > 2 else '',
                'source': 'html_table'
            })
    
    return emails

def clean_html(text):
    """HTML tag'lerini temizle"""
    return re.sub(r'<[^>]*>', '', text).strip()

class HybridEmailMonitor:
    def __init__(self, email_address):
        self.email_address = email_address
        self.sio = None
        self.connected = False
        self.all_emails = []
        self.new_emails = []
        
    def get_all_emails(self, wait_time=10):
        """API + WebSocket ile tüm mailleri al"""
        
        # 1. ÖNCE: API ile önceki mailleri al
        logger.info(f"📨 Önceki mailler API ile alınıyor: {self.email_address}")
        previous_emails = get_emails_via_api(self.email_address)
        
        if isinstance(previous_emails, dict) and 'emails' in previous_emails:
            previous_emails = previous_emails['emails']
        
        for email in previous_emails:
            self.add_email(email, is_new=False)
        
        logger.info(f"📊 {len(previous_emails)} önceki mail alındı")
        
        # 2. SONRA: WebSocket ile yeni mailleri dinle
        logger.info(f"🔌 WebSocket ile yeni mailler dinleniyor...")
        ws_success = self.monitor_websocket(wait_time)
        
        # 3. Sonuçları birleştir
        all_emails = self.all_emails
        
        return {
            "status": "success" if all_emails else "no_emails",
            "total_emails": len(all_emails),
            "previous_emails": len(previous_emails),
            "new_emails": len(self.new_emails),
            "emails": all_emails,
            "wait_time": wait_time,
            "websocket_connected": ws_success
        }
    
    def monitor_websocket(self, wait_time):
        """WebSocket ile yeni mailleri dinle"""
        try:
            self.sio = socketio.Client(logger=False, reconnection=False)
            
            @self.sio.event
            def connect():
                self.connected = True
                logger.info("✅ WebSocket bağlandı - yeni mailler dinleniyor...")
                self.sio.emit("watch_for_my_email", self.email_address)
            
            @self.sio.event
            def new_email(data):
                logger.info(f"🎉 YENİ MAIL WEBSOCKET: {data}")
                self.add_email(data, is_new=True)
            
            self.sio.connect(
                "wss://tr.emailfake.com",
                transports=['websocket'],
                wait_timeout=5
            )
            
            # Kısa süre bekle
            time.sleep(wait_time)
            
            self.sio.disconnect()
            return True
            
        except Exception as e:
            logger.info(f"⚠️ WebSocket bağlanamadı: {e}")
            return False
    
    def add_email(self, email_data, is_new=False):
        """Mail ekle"""
        if not email_data:
            return
            
        email_info = {
            'id': len(self.all_emails) + 1,
            'from': email_data.get('from', 'Bilinmiyor'),
            'subject': email_data.get('subject', 'Konu Yok'),
            'date': email_data.get('date', ''),
            'content': email_data.get('content', ''),
            'received_at': time.strftime('%Y-%m-%d %H:%M:%S'),
            'timestamp': time.time(),
            'is_new': is_new,
            'source': 'websocket' if is_new else 'api'
        }
        
        # Aynı maili ekleme (basit deduplication)
        existing = any(e['subject'] == email_info['subject'] and e['from'] == email_info['from'] for e in self.all_emails)
        if not existing:
            self.all_emails.append(email_info)
            if is_new:
                self.new_emails.append(email_info)
            logger.info(f"📧 {'YENİ' if is_new else 'ÖNCEKİ'} MAIL: {email_info['from']} - {email_info['subject']}")

@app.route('/get-emails', methods=['POST'])
def get_emails():
    """API + WebSocket ile tüm mailleri al"""
    data = request.get_json()
    
    if not data or 'email' not in data:
        return jsonify({"error": "Email adresi gerekli"}), 400
    
    email_address = data['email']
    wait_time = data.get('wait_time', 10)
    
    logger.info(f"📨 KARMA sistemi: {email_address}")
    
    monitor = HybridEmailMonitor(email_address)
    result = monitor.get_all_emails(wait_time)
    
    # Depolamaya kaydet
    if result['emails']:
        email_storage[email_address] = result['emails']
    
    return jsonify(result)

@app.route('/test-api', methods=['POST'])
def test_api():
    """Sadece API testi"""
    data = request.get_json()
    email = data.get('email', '')
    
    emails = get_emails_via_api(email)
    
    return jsonify({
        "status": "success",
        "email": email,
        "emails_found": len(emails),
        "emails": emails
    })

if __name__ == '__main__':
    logger.info("🚀 API + WebSocket Karma Sistem Başlatılıyor...")
    app.run(host='0.0.0.0', port=10000, debug=False)
