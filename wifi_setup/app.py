from flask import Flask, render_template, request, redirect
import subprocess
import os

app = Flask(__name__)

HTML_FORM = """
<!DOCTYPE html>
<html>
<head><title>Pi Setup</title></head>
<body>
    <h2>Connect Pi to WiFi</h2>
    <form method="POST" action="/setup">
        SSID: <input type="text" name="ssid"><br><br>
        Password: <input type="password" name="password"><br><br>
        <input type="submit" value="Connect">
    </form>
</body>
</html>
"""

@app.route('/')
def index():
    return HTML_FORM

@app.route('/setup', methods=['POST'])
def setup():
    ssid = request.form.get('ssid')
    pw = request.form.get('password')
    
    # Command to add the new wifi connection
    # nmcli dev wifi connect <SSID> password <PASSWORD>
    try:
        # We run this in the background or as a detached process 
        # because the connection will drop the hotspot.
        cmd = f"sleep 2 && nmcli dev wifi connect '{ssid}' password '{pw}'"
        subprocess.Popen(cmd, shell=True)
        return "Attempting to connect... The hotspot will now close. Please check your home network."
    except Exception as e:
        return f"Error: {str(e)}"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80)