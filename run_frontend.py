"""
Simple HTTP server for Mission Intelligence frontend
"""
import http.server
import socketserver
import os

PORT = 5175
DIRECTORY = "frontend"

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

print(f"[Frontend] Starting server on http://localhost:{PORT}")
print(f"[Frontend] Serving files from: {DIRECTORY}/")

with socketserver.TCPServer(("", PORT), Handler) as httpd:
    print(f"[Frontend] Server running at http://localhost:{PORT}")
    httpd.serve_forever()
