#!/usr/bin/env python3

import subprocess
import html

from http.server import HTTPServer, BaseHTTPRequestHandler
from cgi import parse_header
from urllib.parse import parse_qs

def _exec(cmd: list) -> subprocess.Popen:
    return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

def _exec_wait(cmd: list) -> (str, bool):
    ret = _exec(cmd)
    (stdout, stderr) = ret.communicate()
    if ret.wait() != 0:
        print("Failed to execute command")
        print("STDOUT: %s\n\nSTDERR: %s" % (stdout, stderr))
        return False
    return stdout

def wpaNetworksList() -> list:
    ret = []
    out = _exec_wait(["wpa_cli", "-i", "wlan0", "list_network"])
    if not out:
        return ret
    for line in out.decode().splitlines()[1:]:
        ret.append(line.split("\t")[1])
    return ret

def wpaCreateConfig(ssid: str, password: str) -> None:
    config = _exec_wait(["wpa_passphrase", ssid, password])
    with open("/etc/wpa_supplicant/wpa_supplicant.conf", "wb") as fd:
        fd.write(b"country=US\n")
        fd.write(b"ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev\n")
        fd.write(config)

index = """<html><head><title>TeleGlobe setup</title></head>
<body>
    <p>TeleGlobe supports only WiFi 2.4GHz b/g/n</p>
    <p style="background-color:#%s; padding:6px">%s</p>
    <form method="POST" action="/">
        <label for="ssid">WiFi SSID: available: %s</label><br/>
        <input id="ssid" name="ssid" /><br/><br/>
        <label for="password">WiFi password:</label><br/>
        <input type="password" id="password" name="password" /><br/><br/>
        <button type="submit">Save &amp; Reboot</button>
    </form>
</body></html>
"""

class Redirect(BaseHTTPRequestHandler):
    def send_index(self, notification, color = "ff6666"):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write((index % (
            html.escape(color, True),
            html.escape(notification),
            html.escape("'"+"', '".join(wpaNetworksList())+"'"),
        )).encode())


    def do_GET(self):
        if self.headers.get('Host') != "setup.teleglobe":
            self.send_response(302)
            self.send_header("Location", "http://setup.teleglobe/")
            self.end_headers()
            return
        self.send_index("Please put the WiFi name and password to connect to Telegram API", "ffff00")

    def do_POST(self):
        ctype, pdict = parse_header(self.headers.get("Content-Type"))
        if ctype != "application/x-www-form-urlencoded":
            self.send_index("ERROR: Incorrect content type")
            return

        length = int(self.headers.get("Content-Length"))
        if length > 10240:
            self.send_index("ERROR: Too big request")

        postvars = parse_qs(self.rfile.read(length), keep_blank_values=1)
        if not postvars[b"ssid"][0]:
            self.send_index("ERROR: WiFi SSID can't be empty.")

        wpaCreateConfig(postvars[b"ssid"][0], postvars[b"password"][0])

        self.send_index("OK config saved. Reboot...", "66ff66")

        _exec(["reboot"])

HTTPServer(("", int(80)), Redirect).serve_forever()
