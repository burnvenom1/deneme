# 📁 app.py - AKILLI MAIL DİNLEME SİSTEMİ
from flask import Flask, jsonify, request
import socketio
import time
import logging
import threading
import requests
from datetime import datetime, timedelta

app = Flask(__name__)
sio = socketio.Client(logger=True, engineio_logger=True)

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 📨 Mail depolama
email_storage = {}
websocket_connected = False
current_monitored_email = None

@sio.event
def connect():
    global websocket_connected
    websocket_connected = True
    logger.info("✅ ✅ ✅ EMAILFAKE WebSocket'e BAĞLANDI!")

@sio.event
def connect_error(data):
    logger.error(f"❌ WebSocket bağlantı hatası: {data}")

@sio.event
def disconnect():
    global websocket_connected, current_monitored_email
    websocket_connected = False
    current_monitored_email = None
    logger.error("❌ ❌ ❌ BAĞLANTI KESİLDİ!")

@sio.event
def new_email(data):
    """YENİ MAIL GELDİĞİNDE BU FONKSİYON ÇALIŞIR"""
    global current_monitored_email
    
    if current_monitored_email:
        logger.info(f"🎉 {current_monitored_email} için YENİ MAIL GELDİ!")
        
        # Mail bilgilerini işle
        email_info = {
            'id': len(email_storage.get(current_monitored_email, [])) + 1,
            'from': data.get('from', 'Bilinmiyor'),
            'subject': data.get('subject', 'Konu Yok'),
            'date': data.get('date', 'Tarih Yok'),
            'content': data.get('content', ''),
            'received_at': time.strftime('%Y-%m-%d %H:%M:%S'),
            'timestamp': time.time()
        }
        
        # Mailleri email adresine göre sakla
        if current_monitored_email not in email_storage:
            email_storage[current_monitored_email] = []
        
        email_storage[current_monitored_email].append(email_info)
        
        logger.info(f"📧 {current_monitored_email} - GÖNDEREN: {email_info['from']}")
        logger.info(f"📌 KONU: {email_info['subject']}")
        logger.info("=" * 50)

def get_last_email(email_address):
    """Bir email adresinin son mailini getir"""
    if email_address in email_storage and email_storage[email_address]:
        return email_storage[email_address][-1]
    return None

def monitor_email_for_duration(email_address, duration=5):
    """Belirli bir süre boyunca emaili dinle"""
    global current_monitored_email
    
    # Önceki dinlemeyi durdur
    if current_monitored_email and current_monitored_email != email_address:
        logger.info(f"🔄 Önceki dinleme durduruldu: {current_monitored_email}")
    
    # Yeni emaili dinlemeye başla
    current_monitored_email = email_address
    
    try:
        # Email takibini başlat
        sio.emit("watch_for_my_email", email_address)
        logger.info(f"👂 {email_address} {duration} saniye dinleniyor...")
        
        # Son maili kaydet (dinlemeden önceki)
        last_email_before = get_last_email(email_address)
        
        # Belirtilen süre boyunca bekle
        time.sleep(duration)
        
        # Dinleme sonrası son mail
        last_email_after = get_last_email(email_address)
        
        # Eğer yeni mail geldiyse onu döndür, yoksa öncekini döndür
        if last_email_after and last_email_after != last_email_before:
            logger.info(f"🎯 YENİ MAIL BULUNDU: {email_address}")
            return {
                "status": "new_email_received",
                "email": last_email_after,
                "wait_time": duration,
                "is_new": True
            }
        elif last_email_before:
            logger.info(f"📨 SON MAIL GÖNDERİLİYOR: {email_address}")
            return {
                "status": "last_email_sent",
                "email": last_email_before,
                "wait_time": duration,
                "is_new": False
            }
        else:
            logger.info(f"📭 HİÇ MAIL BULUNAMADI: {email_address}")
            return {
                "status": "no_emails_found",
                "email": None,
                "wait_time": duration,
                "is_new": False
            }
            
    except Exception as e:
        logger.error(f"❌ Dinleme hatası: {e}")
        return {
            "status": "error",
            "error": str(e),
            "email": None
        }

@app.route('/')
def home():
    """Ana sayfa - sistem durumu"""
    return jsonify({
        "status": "active",
        "service": "Akıllı EmailFake Monitor",
        "websocket_connected": websocket_connected,
        "current_monitored_email": current_monitored_email,
        "total_tracked_emails": len(email_storage),
        "uptime": time.time()
    })

@app.route('/get-email', methods=['POST'])
def get_email():
    """
    AKILLI MAIL ALMA ENDPOINT'I
    - 5 saniye yeni mail bekler
    - Yeni mail gelirse onu döndürür
    - Gelmezse son maili döndürür
    """
    data = request.get_json()
    
    if not data or 'email' not in data:
        return jsonify({"error": "Email adresi gerekli"}), 400
    
    email_address = data['email']
    wait_time = data.get('wait_time', 5)  # Varsayılan 5 saniye
    
    # WebSocket bağlı değilse hata ver
    if not websocket_connected:
        return jsonify({
            "status": "error",
            "error": "WebSocket bağlantısı yok",
            "email": None
        }), 503
    
    logger.info(f"📨 MAIL İSTEĞİ: {email_address} ({wait_time}s bekleme)")
    
    # Emaili dinle ve sonucu al
    result = monitor_email_for_duration(email_address, wait_time)
    
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
        "status": "healthy" if websocket_connected else "unhealthy",
        "websocket_connected": websocket_connected,
        "current_monitored_email": current_monitored_email,
        "timestamp": time.time(),
        "total_tracked_emails": len(email_storage)
    })

def start_websocket():
    """WebSocket bağlantısını başlat"""
    max_retries = 10
    retry_delay = 5
    
    for attempt in range(max_retries):
        try:
            logger.info(f"🔌 WebSocket bağlantısı deneniyor... ({attempt + 1}/{max_retries})")
            
            # EMAILFAKE WebSocket'ine bağlan
            sio.connect(
                "wss://tr.emailfake.com",
                transports=['websocket', 'polling'],
                wait_timeout=10
            )
            
            logger.info("🚀 🚀 🠒 WEB SOCKET BAĞLANTISI BAŞARILI!")
            break
            
        except Exception as e:
            logger.error(f"❌ Bağlantı hatası ({attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                wait_time = retry_delay
                logger.info(f"⏳ {wait_time} saniye sonra yeniden deneniyor...")
                time.sleep(wait_time)
                retry_delay = min(retry_delay * 1.5, 30)
    else:
        logger.error("💥 MAXIMUM RETRY SAYISINA ULAŞILDI! Bağlantı kurulamadı.")

def keep_alive():
    """Bağlantıyı canlı tut"""
    while True:
        if not websocket_connected:
            logger.warning("🔁 WebSocket bağlantısı kopmuş, yeniden bağlanılıyor...")
            start_websocket()
        time.sleep(30)

if __name__ == '__main__':
    # WebSocket bağlantısını başlat
    logger.info("🚀 Akıllı EmailFake Monitor Başlatılıyor...")
    
    # WebSocket i ayrı thread de başlat
    websocket_thread = threading.Thread(target=start_websocket)
    websocket_thread.daemon = True
    websocket_thread.start()
    
    # Keep-alive thread i başlat
    keep_alive_thread = threading.Thread(target=keep_alive)
    keep_alive_thread.daemon = True
    keep_alive_thread.start()
    
    # Flask uygulamasını başlat
    logger.info("🌐 Flask Web Server Başlatılıyor...")
    app.run(host='0.0.0.0', port=10000, debug=False)
