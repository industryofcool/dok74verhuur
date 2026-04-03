import http.server, os, socketserver

PORT = 8051
os.chdir('/Users/Frans/Documents/ClaudeCodeZandbak/huurgemak')

Handler = http.server.SimpleHTTPRequestHandler
with socketserver.TCPServer(('127.0.0.1', PORT), Handler) as httpd:
    httpd.serve_forever()
