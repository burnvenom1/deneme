# 📁 app.py - SADECE WEB SOCKET
from flask import Flask, jsonify
import socketio
import time
import logging
import threading

app = Flask(__name__)
sio = socketio.Client()

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 📨 Gelen mailleri kaydet
received_emails = []
websocket_connected = False

@sio.event
def connect():
    global websocket_connected
    websocket_connected = True
    logger.info("✅ ✅ ✅ EMAILFAKE WebSocket'e BAĞLANDI!")
    
    # Email takibini BAŞLAT
    sio.emit("watch_for_my_email", "fedotiko@newdailys.com")
    logger.info("👂 fedotiko@newdailys.com TAKİBE ALINDI!")

@sio.event
def disconnect():
    global websocket_connected
    websocket_connected = False
    logger.error("❌ ❌ ❌ BAĞLANTI KESİLDİ!")

@sio.event
def new_email(data):
    """YENİ MAIL GELDİĞİNDE BU FONKSİYON ÇALIŞIR"""
    logger.info("🎉 🎉 🎉 YENİ MAIL GELDİ!")
    
    # Mail bilgilerini işle
    email_info = {
        'from': data.get('from', 'Bilinmiyor'),
        'subject': data.get('subject', 'Konu Yok'),
        'date': data.get('date', 'Tarih Yok'),
        'received_at': time.strftime('%Y-%m-%d %H:%M:%S')
    }
    
    # Mailler listesine ekle
    received_emails.append(email_info)
    
    logger.info(f"📧 GÖNDEREN: {email_info['from']}")
    logger.info(f"📌 KONU: {email_info['subject']}")
    logger.info(f"📅 TARİH: {email_info['date']}")
    logger.info(f"⏰ ALGILANDI: {email_info['received_at']}")
    logger.info("=" * 50)

@app.route('/')
def home():
    """Ana sayfa - sistem durumu"""
    return jsonify({
        "status": "active",
        "service": "EmailFake WebSocket Monitor",
        "monitored_email": "fedotiko@newdailys.com",
        "websocket_connected": websocket_connected,
        "total_emails_received": len(received_emails),
        "uptime": time.time()
    })

@app.route('/emails')
def list_emails():
    """Alınan tüm mailleri göster"""
    return jsonify({
        "total_emails": len(received_emails),
        "emails": received_emails
    })

@app.route('/health')
def health():
    """Sağlık kontrolü"""
    return jsonify({
        "status": "healthy" if websocket_connected else "unhealthy",
        "websocket_connected": websocket_connected,
        "timestamp": time.time(),
        "last_10_emails": received_emails[-10:] if received_emails else []
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
                transports=['websocket'],
                wait_timeout=10
            )
            
            logger.info("🚀 🚀 🚀 WEB SOCKET BAĞLANTISI BAŞARILI!")
            break
            
        except Exception as e:
            logger.error(f"❌ Bağlantı hatası ({attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                logger.info(f"⏳ {retry_delay} saniye sonra yeniden deneniyor...")
                time.sleep(retry_delay)
                retry_delay = min(retry_delay * 1.5, 30)  # Exponential backoff
    else:
        logger.error("💥 MAXIMUM RETRY SAYISINA ULAŞILDI! Bağlantı kurulamadı.")

def keep_alive():
    """Bağlantıyı canlı tut"""
    while True:
        if not websocket_connected:
            logger.warning("🔁 WebSocket bağlantısı kopmuş, yeniden bağlanılıyor...")
            start_websocket()
        time.sleep(30)  # 30 saniyede bir kontrol et

if __name__ == '__main__':
    # WebSocket bağlantısını başlat
    logger.info("🚀 EmailFake WebSocket Monitor Başlatılıyor...")
    
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
