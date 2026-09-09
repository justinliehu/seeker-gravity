#!/usr/bin/env python3
"""Stand-in for the download site's /pay/status endpoint, for the headless paid-revive test.

GET /pay/status?ref=<hex>  ->  {"paid": false} for the first PAID_AFTER polls of that ref, then {"paid": true}.
Anything else -> 404. Usage: python mock_pay_server.py [port] [paid_after]
"""
import json
import sys
from collections import Counter
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
PAID_AFTER = int(sys.argv[2]) if len(sys.argv) > 2 else 2
polls = Counter()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        url = urlparse(self.path)
        if url.path != "/pay/status":
            self.send_response(404)
            self.end_headers()
            return
        ref = (parse_qs(url.query).get("ref") or [""])[0]
        polls[ref] += 1
        body = json.dumps({"paid": polls[ref] > PAID_AFTER, "polls": polls[ref]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        sys.stderr.write("mock pay: ref=%s poll #%d paid=%s\n" % (ref[:8], polls[ref], polls[ref] > PAID_AFTER))

    def log_message(self, *_):
        pass


if __name__ == "__main__":
    HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
