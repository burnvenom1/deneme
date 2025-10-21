# 📁 app.py - DİNAMİK WEBSOCKET BAĞLANTILI SİSTEM
from flask import Flask, jsonify, request
import socketio
import time
import logging
import threading
import requests
import json

app = Flask(__name__)

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 📨 Mail depolama
email_storage = {}
active_connections = {}

class EmailMonitor:
    def __init__(self, email_address):
        self.email_address = email_address
        self.sio = None
        self.received_emails = []
        self.connected = False
        self.new_email_received = False
        self.latest_email = None
        
    def connect_and_monitor(self, wait_time=5):
        """Email adresine özel WebSocket bağlantısı kur ve dinle"""
        self.sio = socketio.Client(logger=False)
        
        @self.sio.event
        def connect():
            self.connected = True
            logger.info(f"✅ {self.email_address} WebSocket'e BAĞLANDI!")
            # Email takibini başlat
            self.sio.emit("watch_for_my_email", self.email_address)
            logger.info(f"👂 {self.email_address} dinleniyor...")
        
        @self.sio.event
        def connect_error(data):
            logger.error(f"❌ {self.email_address} bağlantı hatası: {data}")
            self.connected = False
        
        @self.sio.event
        def disconnect():
            logger.info(f"🔌 {self.email_address} bağlantısı kapandı")
            self.connected = False
        
        @self.sio.event
        def new_email(data):
            """YENİ MAIL GELDİĞİNDE BU FONKSİYON ÇALIŞIR"""
            logger.info(f"🎉 {self.email_address} için YENİ MAIL GELDİ!")
            
            # Mail bilgilerini işle
            email_info = {
                'id': len(self.received_emails) + 1,
                'from': data.get('from', 'Bilinmiyor'),
                'subject': data.get('subject', 'Konu Yok'),
                'date': data.get('date', 'Tarih Yok'),
                'content': data.get('content', ''),
                'received_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                'timestamp': time.time()
            }
            
            self.received_emails.append(email_info)
            self.latest_email = email_info
            self.new_email_received = True
            
            logger.info(f"📧 {self.email_address} - GÖNDEREN: {email_info['from']}")
            logger.info(f"📌 KONU: {email_info['subject']}")
        
        try:
            # WebSocket bağlantısını kur
            logger.info(f"🔌 {self.email_address} için WebSocket bağlantısı kuruluyor...")
            
            self.sio.connect(
                "wss://tr.emailfake.com",
                transports=['websocket', 'polling'],
                wait_timeout=10
            )
            
            # Bağlantının kurulmasını bekle
            time.sleep(2)
            
            if not self.connected:
                return {
                    "status": "error",
                    "error": "WebSocket bağlantısı kurulamadı",
                    "email": None
                }
            
            # Önceki son maili kaydet
            previous_email = self.latest_email
            
            # Belirtilen süre boyunca yeni mail bekle
            logger.info(f"⏳ {self.email_address} için {wait_time} saniye bekleniyor...")
            
            start_time = time.time()
            while time.time() - start_time < wait_time:
                if self.new_email_received:
                    break
                time.sleep(0.1)  # Küçük aralıklarla kontrol et
            
            # Bağlantıyı kapat
            self.sio.disconnect()
            
            # Sonucu değerlendir
            if self.new_email_received and self.latest_email:
                logger.info(f"🎯 YENİ MAIL BULUNDU: {self.email_address}")
                return {
                    "status": "new_email_received",
                    "email": self.latest_email,
                    "wait_time": wait_time,
                    "is_new": True
                }
            elif previous_email:
                logger.info(f"📨 SON MAIL GÖNDERİLİYOR: {self.email_address}")
                return {
                    "status": "last_email_sent",
                    "email": previous_email,
                    "wait_time": wait_time,
                    "is_new": False
                }
            else:
                logger.info(f"📭 HİÇ MAIL BULUNAMADI: {self.email_address}")
                return {
                    "status": "no_emails_found",
                    "email": None,
                    "wait_time": wait_time,
                    "is_new": False
                }
                
        except Exception as e:
            logger.error(f"❌ {self.email_address} dinleme hatası: {e}")
            # Bağlantıyı kapatmayı dene
            try:
                if self.sio:
                    self.sio.disconnect()
            except:
                pass
            return {
                "status": "error",
                "error": str(e),
                "email": None
            }

def get_previous_emails(email_address):
    """Önceden alınmış mailleri kontrol et"""
    if email_address in email_storage and email_storage[email_address]:
        return email_storage[email_address][-1]
    return None

@app.route('/')
def home():
    """Ana sayfa - sistem durumu"""
    return jsonify({
        "status": "active",
        "service": "Dinamik EmailFake Monitor",
        "total_tracked_emails": len(email_storage),
        "active_connections": len(active_connections),
        "uptime": time.time()
    })

@app.route('/get-email', methods=['POST'])
def get_email():
    """
    AKILLI MAIL ALMA ENDPOINT'I
    - Her istekte yeni WebSocket bağlantısı
    - 5 saniye yeni mail bekler
    - Yeni mail gelirse onu döndürür
    - Gelmezse önceki maili/sonucu döndürür
    """
    data = request.get_json()
    
    if not data or 'email' not in data:
        return jsonify({"error": "Email adresi gerekli"}), 400
    
    email_address = data['email']
    wait_time = data.get('wait_time', 5)  # Varsayılan 5 saniye
    
    logger.info(f"📨 MAIL İSTEĞİ: {email_address} ({wait_time}s bekleme)")
    
    # Önceki mailleri kontrol et
    previous_email = get_previous_emails(email_address)
    
    # Yeni monitor oluştur ve dinlemeye başla
    monitor = EmailMonitor(email_address)
    
    # Eğer önceki mail varsa, monitor'a aktar
    if previous_email:
        monitor.received_emails = email_storage.get(email_address, [])
        monitor.latest_email = previous_email
    
    # Emaili dinle ve sonucu al
    result = monitor.connect_and_monitor(wait_time)
    
    # Sonucu depolaya kaydet
    if result.get('email'):
        if email_address not in email_storage:
            email_storage[email_address] = []
        
        # Yeni mailse listeye ekle
        if result.get('is_new'):
            email_storage[email_address].append(result['email'])
        # Önceki maili güncelle
        else:
            email_storage[email_address] = [result['email']]
    
    return jsonify(result)

@app.route('/emails/<email_address>')
def list_emails(email_address):
    """Belirli bir email adresinin tüm maillerini listele"""
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

@app.route('/health')
def health():
    """Sağlık kontrolü"""
    return jsonify({
        "status": "healthy",
        "timestamp": time.time(),
        "total_tracked_emails": len(email_storage),
        "total_active_connections": len(active_connections)
    })

@app.route('/test', methods=['POST'])
def test_email():
    """Test endpoint - gerçek WebSocket olmadan çalışır"""
    data = request.get_json()
    email_address = data.get('email', 'test@example.com')
    
    # Test maili oluştur
    test_email = {
        'id': 1,
        'from': 'noreply@test.com',
        'subject': f'Test Maili - {time.strftime("%H:%M:%S")}',
        'date': time.strftime('%Y-%m-%d %H:%M:%S'),
        'content': 'Bu bir test mailidir',
        'received_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'timestamp': time.time(),
        'is_test': True
    }
    
    # Depolamaya kaydet
    if email_address not in email_storage:
        email_storage[email_address] = []
    email_storage[email_address].append(test_email)
    
    return jsonify({
        "status": "test_email_created",
        "email": test_email,
        "message": "Test maili oluşturuldu"
    })

if __name__ == '__main__':
    # Flask uygulamasını başlat
    logger.info("🚀 Dinamik EmailFake Monitor Başlatılıyor...")
    logger.info("🌐 Flask Web Server Başlatılıyor...")
    app.run(host='0.0.0.0', port=10000, debug=False)
