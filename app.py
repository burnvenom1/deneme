# 📁 app.py - ALTERNATİF YAKLAŞIM
from flask import Flask, jsonify, request
import requests
import time
import logging
from bs4 import BeautifulSoup

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_emails_alternative(email_address):
    """Alternatif yöntemlerle mailleri al"""
    try:
        username, domain = email_address.split('@')
        
        # Farklı URL pattern'leri deneyelim
        url_patterns = [
            f"https://tr.emailfake.com/{domain}/{username}",
            f"https://{domain}/inbox/{username}",
            f"https://emailfake.com/{domain}/{username}",
        ]
        
        for url in url_patterns:
            try:
                logger.info(f"🔗 Deneniyor: {url}")
                
                # Daha basit headers
                headers = {
                    'User-Agent': 'Mozilla/5.0 (compatible; Bot)'
                }
                
                response = requests.get(url, headers=headers, timeout=15, verify=False)
                logger.info(f"📄 Status: {response.status_code}")
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # Basit email arama
                    emails = []
                    
                    # Email adresini bul
                    email_elem = soup.find('span', id='email_ch_text')
                    if email_elem:
                        logger.info(f"📧 Email bulundu: {email_elem.text}")
                    
                    # Tablolardan mailleri çıkar
                    for table in soup.find_all('table'):
                        for row in table.find_all('tr')[1:]:
                            cells = row.find_all(['td', 'div'])
                            if len(cells) >= 2:
                                email_data = {
                                    'from': cells[0].get_text(strip=True),
                                    'subject': cells[1].get_text(strip=True),
                                    'to': email_address,
                                    'source': 'table'
                                }
                                if email_data['from'] or email_data['subject']:
                                    emails.append(email_data)
                    
                    if emails:
                        return {
                            "status": "success",
                            "email": email_address,
                            "total_emails": len(emails),
                            "emails": emails,
                            "working_url": url
                        }
                        
            except requests.exceptions.SSLError:
                logger.warning(f"⚠️ SSL Hatası: {url}")
                continue
            except requests.exceptions.ConnectionError:
                logger.warning(f"⚠️ Bağlantı Hatası: {url}")
                continue
            except Exception as e:
                logger.warning(f"⚠️ Diğer hata ({url}): {e}")
                continue
        
        return {
            "status": "error",
            "error": "Tüm URL'ler denenmesine rağmen bağlantı kurulamadı",
            "emails": []
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "emails": []
        }

@app.route('/get-emails', methods=['POST'])
def get_emails():
    data = request.get_json()
    email = data.get('email', '')
    
    if not email:
        return jsonify({"error": "Email gerekli"}), 400
    
    result = get_emails_alternative(email)
    return jsonify(result)

@app.route('/test')
def test():
    """Basit bağlantı testi"""
    try:
        # Google'a bağlanabiliyor muyuz?
        response = requests.get("https://www.google.com", timeout=10)
        return jsonify({
            "internet_connection": True,
            "google_status": response.status_code,
            "render_ip": requests.get("https://httpbin.org/ip").json()
        })
    except Exception as e:
        return jsonify({
            "internet_connection": False,
            "error": str(e)
        })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000, debug=False)
