"""
file_server.py
--------------
Lightweight HTTP server that handles storing and retrieving
encrypted image files and their corresponding keys.
Run this before launching the Streamlit app:
    python file_server.py
"""

import os
import json
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

STORAGE_DIR = "server_storage"
PORT        = 8765

os.makedirs(STORAGE_DIR, exist_ok=True)


class EncryptionServerHandler(BaseHTTPRequestHandler):

    # --- Route dispatcher ---
    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/store":
            self.handle_store()
        else:
            self.send_error(404)

    def do_GET(self):
        path  = urlparse(self.path).path
        query = parse_qs(urlparse(self.path).query)
        if path == "/retrieve":
            self.handle_retrieve(query)
        elif path == "/health":
            self.send_json({"status": "running"})
        else:
            self.send_error(404)

    # --- Store encrypted image and key, return 6-digit code ---
    def handle_store(self):
        length   = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(length)
        payload  = json.loads(raw_body)

        code          = payload.get("code")
        encrypted_hex = payload.get("encrypted")
        key_hex       = payload.get("key")
        shape         = payload.get("shape")

        if not all([code, encrypted_hex, key_hex, shape]):
            self.send_error(400, "Missing fields in payload.")
            return

        record = {
            "encrypted": encrypted_hex,
            "key":       key_hex,
            "shape":     shape
        }

        record_path = os.path.join(STORAGE_DIR, f"{code}.json")
        with open(record_path, "w") as f:
            json.dump(record, f)

        self.send_json({"status": "stored", "code": code})

    # --- Retrieve encrypted image and key by code ---
    def handle_retrieve(self, query):
        code_list = query.get("code")
        if not code_list:
            self.send_error(400, "Missing code parameter.")
            return

        code        = code_list[0]
        record_path = os.path.join(STORAGE_DIR, f"{code}.json")

        if not os.path.exists(record_path):
            self.send_json({"status": "not_found"})
            return

        with open(record_path, "r") as f:
            record = json.load(f)

        self.send_json({"status": "ok", **record})

    # --- JSON response helper ---
    def send_json(self, data):
        body = json.dumps(data).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # --- Suppress default request logging ---
    def log_message(self, format, *args):
        pass


if __name__ == "__main__":
    server = HTTPServer(("localhost", PORT), EncryptionServerHandler)
    print(f"File server running on http://localhost:{PORT}")
    print(f"Storage directory: {os.path.abspath(STORAGE_DIR)}")
    print("Press Ctrl+C to stop.\n")
    server.serve_forever()
