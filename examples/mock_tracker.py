from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST = "localhost"
PORT = 8799

_ROUTES = {
    "/api/v1/events": {"accepted": 1},
    "/api/v1/push-events": {"accepted": 1},
    "/api/v1/user-properties": {"ok": True},
}


class Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        path = self.path.split("?", 1)[0]
        length = int(self.headers.get("content-length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw)
        except ValueError:
            body = {"_unparsed": raw.decode("utf-8", "replace")}

        auth = self.headers.get("authorization", "")
        sdk = self.headers.get("x-appss-sdk", "")
        print(f"\n=== POST {path}  ({sdk}, auth={auth[:16]}...) ===")
        print(json.dumps(body, indent=2, ensure_ascii=False))

        response = dict(_ROUTES.get(path, {"ok": True}))
        if "accepted" in response and isinstance(body.get("batch"), list):
            response["accepted"] = len(body["batch"])

        payload = json.dumps(response).encode("utf-8")
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *_args) -> None:
        pass


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"mock tracker listening on http://{HOST}:{PORT}")
    print("waiting for SDK batches (Ctrl+C to stop)...")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopping")
        server.shutdown()


if __name__ == "__main__":
    main()
