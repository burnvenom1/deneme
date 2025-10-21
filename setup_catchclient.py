# 📁 setup_catchclient.py
import subprocess
import sys

def install_catchclient():
    """CatchClient'i GitHub'dan kur"""
    try:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install",
            "git+https://github.com/Podzied/catchclient.git"
        ])
        return True
    except:
        return False

# Kurulumu dene
if install_catchclient():
    from catchclient import TempMail
else:
    # Fallback: Kendi client'imizi kullan
    from my_catchclient import MyTempMail
    TempMail = MyTempMail
