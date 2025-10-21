# 📁 app.py - GERÇEK DİNAMİK WEBSOCKET SİSTEMİ
from flask import Flask, jsonify, request
import socketio
import time
import logging
import threading
import re

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 📨 Mail depolama
email_storage = {}

def extract_domain_from_email(email):
    """Email adresinden domaini çıkar"""
    match = re.match(r'.*@(.*\.com)', email)
    if match:
        return match.group(1)
    return "tr.emailfake.com"  # fallback

def generate_websocket_url(email):
    """Email adresine göre WebSocket URL oluştur"""
    domain = extract_domain_from_email(email)
    
    # Farklı domain formatları
    if domain == "newdailys.com":
        return "wss://ws.newdailys.com"
    elif domain == "emailfake.com":
        return "wss://tr.emailfake.com"
    else:
        # Varsayılan pattern
        return f"wss://{domain}"

class EmailMonitor:
    def __init__(self, email_address):
        self.email_address = email_address
        self.websocket_url = generate_websocket_url(email_address)
        self.sio = None
        self.connected = False
        self.new_email_received = False
        self.latest_email = None
        self.received_emails = []
        
    def connect_and_monitor(self, wait_time=5):
        """Email adresine özel WebSocket URL'sine bağlan ve dinle"""
        self.sio = socketio.Client(logger=False, engineio_logger=False)
        
        @self.sio.event
        def connect():
            self.connected = True
            logger.info(f"✅ {self.email_address} -> {self.websocket_url} BAĞLANDI!")
            # Email takibini başlat
            self.sio.emit("watch_for_my_email", self.email_address)
            logger.info(f"👂 {self.email_address} dinleniyor...")
        
        @self.sio.event
        def connect_error(data):
            logger.error(f"❌ {self.email_address} -> {self.websocket_url} bağlantı hatası: {data}")
            self.connected = False
        
        @self.sio.event
        def disconnect():
            logger.info(f"🔌 {self.email_address} bağlantısı kapandı")
            self.connected = False
        
        @self.sio.event
        def new_email(data):
            """YENİ MAIL GELDİĞİNDE BU FONKSİYON ÇALIŞIR"""
            logger.info(f"🎉 {self.email_address} için YENİ MAIL GELDİ!")
            
            email_info = {
                'id': len(self.received_emails) + 1,
                'from': data.get('from', 'Bilinmiyor'),
                'subject': data.get('subject', 'Konu Yok'),
                'date': data.get('date', 'Tarih Yok'),
                'content': data.get('content', ''),
                'received_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                'timestamp': time.time(),
                'websocket_url': self.websocket_url
            }
            
            self.received_emails.append(email_info)
            self.latest_email = email_info
            self.new_email_received = True
            
            logger.info(f"📧 {self.email_address} - GÖNDEREN: {email_info['from']}")
            logger.info(f"📌 KONU: {email_info['subject']}")
            logger.info(f"🌐 WEBSOCKET: {self.websocket_url}")
        
        try:
            logger.info(f"🔌 {self.email_address} -> {self.websocket_url} bağlanıyor...")
            
            # WebSocket bağlantısını kur
            self.sio.connect(
                self.websocket_url,
                transports=['websocket', 'polling'],
                wait_timeout=10,
                namespaces=['/']
            )
            
            # Bağlantının kurulmasını bekle
            time.sleep(2)
            
            if not self.connected:
                return {
                    "status": "connection_error",
                    "error": f"{self.websocket_url} bağlantısı kurulamadı",
                    "email": None,
                    "websocket_url": self.websocket_url
                }
            
            # Önceki son maili kaydet
            previous_email = self.get_previous_emails()
            
            # Belirtilen süre boyunca yeni mail bekle
            logger.info(f"⏳ {self.email_address} için {wait_time} saniye bekleniyor...")
            
            start_time = time.time()
            while time.time() - start_time < wait_time:
                if self.new_email_received:
                    logger.info(f"⚡ YENİ MAIL ALGILANDI: {self.email_address}")
                    break
                time.sleep(0.1)
            
            # Bağlantıyı kapat
            try:
                self.sio.disconnect()
            except:
                pass
            
            # Sonucu değerlendir
            if self.new_email_received and self.latest_email:
                self.save_emails()
                return {
                    "status": "new_email_received",
                    "email": self.latest_email,
                    "wait_time": wait_time,
                    "is_new": True,
                    "websocket_url": self.websocket_url
                }
            elif previous_email:
                logger.info(f"📨 SON MAIL GÖNDERİLİYOR: {self.email_address}")
                return {
                    "status": "last_email_sent",
                    "email": previous_email,
                    "wait_time": wait_time,
                    "is_new": False,
                    "websocket_url": self.websocket_url
                }
            else:
                logger.info(f"📭 HİÇ MAIL BULUNAMADI: {self.email_address}")
                return {
                    "status": "no_emails_found",
                    "email": None,
                    "wait_time": wait_time,
                    "is_new": False,
                    "websocket_url": self.websocket_url
                }
                
        except Exception as e:
            logger.error(f"❌ {self.email_address} dinleme hatası: {e}")
            try:
                if self.sio:
                    self.sio.disconnect()
            except:
                pass
            return {
                "status": "error",
                "error": str(e),
                "email": None,
                "websocket_url": self.websocket_url
            }
    
    def get_previous_emails(self):
        """Önceden alınmış mailleri getir"""
        if self.email_address in email_storage and email_storage[self.email_address]:
            return email_storage[self.email_address][-1]
        return None
    
    def save_emails(self):
        """Mailleri depolamaya kaydet"""
        if self.email_address not in email_storage:
            email_storage[self.email_address] = []
        
        # Yeni mailleri ekle
        for email in self.received_emails:
            if email not in email_storage[self.email_address]:
                email_storage[self.email_address].append(email)

@app.route('/')
def home():
    """Ana sayfa - sistem durumu"""
    return jsonify({
        "status": "active",
        "service": "Çoklu WebSocket Email Monitor",
        "total_tracked_emails": len(email_storage),
        "endpoints": {
            "get_email": "POST /get-email",
            "list_emails": "GET /emails/<email>",
            "health": "GET /health",
            "test": "POST /test"
        }
    })

@app.route('/get-email', methods=['POST'])
def get_email():
    """
    HER EMAIL İÇİN FARKLI WEBSOCKET BAĞLANTISI
    """
    data = request.get_json()
    
    if not data or 'email' not in data:
        return jsonify({"error": "Email adresi gerekli"}), 400
    
    email_address = data['email']
    wait_time = data.get('wait_time', 5)
    
    logger.info(f"📨 MAIL İSTEĞİ: {email_address} ({wait_time}s bekleme)")
    
    # Email monitor oluştur ve dinle
    monitor = EmailMonitor(email_address)
    result = monitor.connect_and_monitor(wait_time)
    
    return jsonify(result)

@app.route('/emails/<email_address>')
def list_emails(email_address):
    """Belirli bir email adresinin tüm maillerini listele"""
    if email_address in email_storage:
        return jsonify({
            "email": email_address,
            "total_emails": len(email_storage[email_address]),
            "emails": email_storage[email_address],
            "websocket_urls_used": list(set([e.get('websocket_url', 'unknown') for e in email_storage[email_address]]))
        })
    else:
        return jsonify({
            "email": email_address,
            "total_emails": 0,
            "emails": []
        })

@app.route('/health')
def health():
    """Sağlık kontrolü"""
    return jsonify({
        "status": "healthy",
        "timestamp": time.time(),
        "total_tracked_emails": len(email_storage),
        "memory_usage": len(str(email_storage))
    })

@app.route('/test-websocket', methods=['POST'])
def test_websocket():
    """WebSocket URL test endpoint"""
    data = request.get_json()
    email = data.get('email', 'test@emailfake.com')
    
    monitor = EmailMonitor(email)
    
    return jsonify({
        "email": email,
        "generated_websocket_url": monitor.websocket_url,
        "domain": extract_domain_from_email(email)
    })

if __name__ == '__main__':
    logger.info("🚀 Çoklu WebSocket Email Monitor Başlatılıyor...")
    app.run(host='0.0.0.0', port=10000, debug=False)
