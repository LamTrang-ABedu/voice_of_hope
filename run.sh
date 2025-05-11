#!/bin/bash
cd /opt/hopehub/voice_of_hope

# Cài thư viện (nếu cần)
/usr/bin/python3 -m pip install -r requirements.txt

# Chạy Flask app
/usr/bin/python3 app.py
