# 📁 app.py - TÜM MAİLLERİ İSTEYEN WEBSOCKET
from flask import Flask, jsonify, request
import socketio
import time
import logging
import threading

app = Flask(__name__)

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Mail depolama
email_storage = {}

class CompleteEmailMonitor:
    def __init__(self, email_address):
        self.email_address = email_address
        self.sio = None
        self.connected = False
        self.all_emails = []  # TÜM mailler
        self.emails_received = False
        
    def get_all_emails(self, wait_time=10):
        """TÜM mailleri al (öncekiler + yeniler)"""
        self.sio = socketio.Client(
            logger=True,
            engineio_logger=True,
            reconnection=False
        )
        
        @self.sio.event
        def connect():
            self.connected = True
            logger.info(f"✅ ✅ ✅ WebSocket'e BAĞLANDI: {self.email_address}")
            
            # 1. ÖNCE: Önceki mailleri iste
            self.sio.emit("get_emails", self.email_address)
            self.sio.emit("get_all_emails", self.email_address)
            self.sio.emit("load_emails", self.email_address)
            self.sio.emit("fetch_emails", self.email_address)
            
            # 2. SONRA: Yeni mailleri dinle
            self.sio.emit("watch_for_my_email", self.email_address)
            self.sio.emit("subscribe", self.email_address)
            
            logger.info(f"📨 Tüm mail event'leri gönderildi: {self.email_address}")
        
        @self.sio.event
        def connect_error(data):
            logger.error(f"❌ Bağlantı hatası: {data}")
            self.connected = False
        
        @self.sio.event
        def disconnect():
            logger.info("🔌 Bağlantı kapandı")
            self.connected = False
        
        @self.sio.on('new_email')
        def on_new_email(data):
            """YENİ MAIL"""
            logger.info(f"🎉 YENİ MAIL: {data}")
            self.process_email(data, is_new=True)
        
        @self.sio.on('email')
        def on_email(data):
            """TEKIL MAIL"""
            logger.info(f"📧 MAIL: {data}")
            self.process_email(data)
        
        @self.sio.on('emails')
        def on_emails(data):
            """MAIL LISTESI"""
            logger.info(f"📨 MAIL LISTESI: {len(data) if isinstance(data, list) else 'unknown'}")
            if isinstance(data, list):
                for email in data:
                    self.process_email(email)
            else:
                self.process_email(data)
        
        @self.sio.on('email_list')
        def on_email_list(data):
            """MAIL LISTESI (alternatif)"""
            logger.info(f"📋 EMAIL LIST: {data}")
            self.process_email(data)
        
        # Tüm eventleri yakala
        @self.sio.on('*')
        def catch_all(event, data):
            if event not in ['connect', 'disconnect', 'connect_error']:
                logger.info(f"🔍 EVENT: {event} -> {data}")
                # Email içeren event'leri işle
                if any(keyword in event.lower() for keyword in ['email', 'mail']):
                    self.process_email(data)
        
        try:
            logger.info(f"🔌 Tüm mailler alınıyor: {self.email_address}")
            
            self.sio.connect(
                "wss://tr.emailfake.com",
                transports=['websocket'],
                wait_timeout=10,
                namespaces=['/']
            )
            
            # Bağlantı kontrolü
            time.sleep(3)
            
            if not self.connected:
                return {
                    "status": "connection_failed",
                    "error": "WebSocket bağlantısı kurulamadı",
                    "emails": []
                }
            
            logger.info(f"⏳ {wait_time} saniye mailler bekleniyor...")
            
            # Mail bekleme döngüsü
            start_time = time.time()
            while time.time() - start_time < wait_time:
                if len(self.all_emails) > 0:
                    logger.info(f"⚡ {len(self.all_emails)} mail alındı!")
                    # Mail geldi ama daha fazla bekleyelim
                    time.sleep(1)
                else:
                    time.sleep(0.5)
            
            # Bağlantıyı kapat
            try:
                self.sio.disconnect()
            except:
                pass
            
            # Sonuçları döndür
            if self.all_emails:
                self.save_to_storage()
                return {
                    "status": "success",
                    "total_emails": len(self.all_emails),
                    "emails": self.all_emails,
                    "wait_time": wait_time
                }
            else:
                return {
                    "status": "no_emails",
                    "total_emails": 0,
                    "emails": [],
                    "wait_time": wait_time
                }
                    
        except Exception as e:
            logger.error(f"❌ Monitor hatası: {e}")
            try:
                if self.sio:
                    self.sio.disconnect()
            except:
                pass
            return {
                "status": "error",
                "error": str(e),
                "emails": []
            }
    
    def process_email(self, data, is_new=False):
        """Mail verisini işle"""
        if not data:
            return
            
        # Data formatını kontrol et
        email_data = None
        
        if isinstance(data, dict) and ('from' in data or 'subject' in data):
            # Direkt mail objesi
            email_data = data
        elif isinstance(data, list):
            # Mail listesi
            for item in data:
                self.process_email(item, is_new)
            return
        elif isinstance(data, str):
            # String format, parse etmeye çalış
            try:
                import json
                parsed = json.loads(data)
                self.process_email(parsed, is_new)
                return
            except:
                pass
        
        if email_data:
            email_info = {
                'id': len(self.all_emails) + 1,
                'from': email_data.get('from', 'Bilinmiyor'),
                'subject': email_data.get('subject', 'Konu Yok'),
                'date': email_data.get('date', 'Tarih Yok'),
                'content': email_data.get('content', ''),
                'received_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                'timestamp': time.time(),
                'is_new': is_new
            }
            
            # Aynı maili ekleme
            if email_info not in self.all_emails:
                self.all_emails.append(email_info)
                logger.info(f"📧 MAIL #{len(self.all_emails)}: {email_info['from']} - {email_info['subject']}")
    
    def save_to_storage(self):
        """Mailleri depolamaya kaydet"""
        if self.email_address not in email_storage:
            email_storage[self.email_address] = []
        
        for email in self.all_emails:
            if email not in email_storage[self.email_address]:
                email_storage[self.email_address].append(email)

@app.route('/')
def home():
    return jsonify({
        "status": "active",
        "service": "Complete EmailFake Monitor - Tüm Mailler",
        "total_tracked_emails": sum(len(emails) for emails in email_storage.values()),
        "usage": "POST /get-emails with {'email': 'address@domain.com'}"
    })

@app.route('/get-emails', methods=['POST'])
def get_emails():
    """TÜM mailleri al"""
    data = request.get_json()
    
    if not data or 'email' not in data:
        return jsonify({"error": "Email adresi gerekli"}), 400
    
    email_address = data['email']
    wait_time = data.get('wait_time', 10)
    
    logger.info(f"📨 TÜM MAİLLER isteği: {email_address}")
    
    # Monitor oluştur ve başlat
    monitor = CompleteEmailMonitor(email_address)
    result = monitor.get_all_emails(wait_time)
    
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

@app.route('/test-event', methods=['POST'])
def test_event():
    """Event test endpoint"""
    data = request.get_json()
    email = data.get('email', '')
    event_name = data.get('event', 'get_emails')
    
    import websocket
    import json
    import threading
    
    def on_message(ws, message):
        print(f"📨 TEST MESAJ: {message}")
    
    def on_open(ws):
        print("✅ TEST BAĞLANTI AÇILDI")
        ws.send(json.dumps([event_name, email]))
        print(f"🎯 TEST EVENT GÖNDERİLDİ: {event_name}")
    
    ws = websocket.WebSocketApp(
        "wss://tr.emailfake.com/socket.io/?EIO=4&transport=websocket",
        on_open=on_open,
        on_message=on_message
    )
    
    thread = threading.Thread(target=ws.run_forever)
    thread.daemon = True
    thread.start()
    time.sleep(5)
    ws.close()
    
    return jsonify({"status": "test_completed", "event": event_name})

if __name__ == '__main__':
    logger.info("🚀 TÜM MAİLLER WebSocket Monitor Başlatılıyor...")
    app.run(host='0.0.0.0', port=10000, debug=False)
