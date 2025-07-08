import http.server
import socketserver


class WebhookHandler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)

        print('=== WEBHOOK RECEIVED ===')
        print(f'Headers: {dict(self.headers)}')
        print(f'Body: {post_data.decode()}')
        print('========================')

        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(b'{\"status\": \"received\"}')

with socketserver.TCPServer(('', 3001), WebhookHandler) as httpd:
    print('Webhook server running on http://localhost:3001')
    httpd.serve_forever()
