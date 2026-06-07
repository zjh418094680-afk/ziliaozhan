#!/usr/bin/env python3
"""
Training 2: Production REST API
- CRUD operations with validation
- Input sanitization
- Error handling with proper HTTP codes
- Unit tests
- Exit codes

Usage:
  python3 api.py            # Run server
  python3 api.py --test     # Run tests
"""
import json
import sys
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import re

# ── Data Store ─────────────────────────────────────────
DATA_FILE = os.path.join(os.path.dirname(__file__), "api_data.json")

def load_data():
    if not os.path.exists(DATA_FILE):
        return {"payments": [], "next_id": 1}
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

# ── Validation ─────────────────────────────────────────
def validate_payment(body):
    """Validate payment input. Returns (is_valid, error_message)."""
    if not isinstance(body, dict):
        return False, "Request body must be JSON object"
    
    if "amount" not in body:
        return False, "Missing required field: amount"
    if not isinstance(body["amount"], (int, float)) or body["amount"] <= 0:
        return False, "amount must be positive number"
    if body["amount"] > 999999:
        return False, "amount exceeds maximum (999999)"
    
    if "currency" not in body:
        return False, "Missing required field: currency"
    valid_currencies = {"usd", "eur", "gbp", "jpy", "cny"}
    if body["currency"].lower() not in valid_currencies:
        return False, "currency must be one of: " + ", ".join(sorted(valid_currencies))
    
    return True, None

def validate_id(id_str):
    """Validate payment ID. Returns (is_valid, id_int, error_message)."""
    try:
        id_int = int(id_str)
        if id_int < 1:
            return False, None, "ID must be positive"
        return True, id_int, None
    except (ValueError, TypeError):
        return False, None, "ID must be an integer"

# ── Handlers ───────────────────────────────────────────
class APIHandler(BaseHTTPRequestHandler):
    def _send_json(self, status, body, headers=None):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        if headers:
            for k, v in headers.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(json.dumps(body).encode("utf-8"))
    
    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        try:
            return json.loads(self.rfile.read(length))
        except json.JSONDecodeError:
            return None
    
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        
        # GET /payments — list all
        if path == "/payments":
            data = load_data()
            self._send_json(200, {"payments": data["payments"], "count": len(data["payments"])})
            return
        
        # GET /payments/{id} — get one
        match = re.match(r"^/payments/(\d+)$", path)
        if match:
            valid, pid, err = validate_id(match.group(1))
            if not valid:
                self._send_json(400, {"error": err})
                return
            
            data = load_data()
            for p in data["payments"]:
                if p["id"] == pid:
                    self._send_json(200, p)
                    return
            self._send_json(404, {"error": "Payment not found"})
            return
        
        # GET /health
        if path == "/health":
            self._send_json(200, {"status": "ok", "uptime": "running"})
            return
        
        self._send_json(404, {"error": "Not found"})
    
    def do_POST(self):
        if self.path.rstrip("/") != "/payments":
            self._send_json(404, {"error": "Not found"})
            return
        
        body = self._read_body()
        if body is None:
            self._send_json(400, {"error": "Invalid JSON"})
            return
        
        valid, err = validate_payment(body)
        if not valid:
            self._send_json(422, {"error": err})
            return
        
        data = load_data()
        payment = {
            "id": data["next_id"],
            "amount": body["amount"],
            "currency": body["currency"].lower(),
            "status": "created",
            "description": body.get("description", ""),
        }
        data["payments"].append(payment)
        data["next_id"] += 1
        save_data(data)
        
        self._send_json(201, payment, {"Location": "/payments/" + str(payment["id"])})
    
    def do_PUT(self):
        match = re.match(r"^/payments/(\d+)$", self.path.rstrip("/"))
        if not match:
            self._send_json(404, {"error": "Not found"})
            return
        
        valid, pid, err = validate_id(match.group(1))
        if not valid:
            self._send_json(400, {"error": err})
            return
        
        body = self._read_body()
        if body is None:
            self._send_json(400, {"error": "Invalid JSON"})
            return
        
        if "status" not in body:
            self._send_json(422, {"error": "Missing required field: status"})
            return
        
        valid_statuses = {"created", "processing", "succeeded", "failed"}
        if body["status"] not in valid_statuses:
            self._send_json(422, {"error": "status must be one of: " + ", ".join(sorted(valid_statuses))})
            return
        
        data = load_data()
        for p in data["payments"]:
            if p["id"] == pid:
                p["status"] = body["status"]
                if "description" in body:
                    p["description"] = body["description"]
                save_data(data)
                self._send_json(200, p)
                return
        
        self._send_json(404, {"error": "Payment not found"})
    
    def log_message(self, format, *args):
        pass  # Suppress default logging

# ── Tests ──────────────────────────────────────────────
def run_tests():
    """Self-contained unit tests."""
    passed = 0
    failed = 0
    
    # Test 1: validate_payment — valid
    ok, err = validate_payment({"amount": 100, "currency": "usd"})
    if ok:
        passed += 1
    else:
        print("FAIL: test_valid_payment: " + str(err))
        failed += 1
    
    # Test 2: validate_payment — missing field
    ok, err = validate_payment({"amount": 100})
    if not ok and "currency" in str(err):
        passed += 1
    else:
        print("FAIL: test_missing_currency")
        failed += 1
    
    # Test 3: validate_payment — negative amount
    ok, err = validate_payment({"amount": -1, "currency": "usd"})
    if not ok and "positive" in str(err):
        passed += 1
    else:
        print("FAIL: test_negative_amount")
        failed += 1
    
    # Test 4: validate_payment — invalid currency
    ok, err = validate_payment({"amount": 100, "currency": "xyz"})
    if not ok and "one of" in str(err):
        passed += 1
    else:
        print("FAIL: test_invalid_currency")
        failed += 1
    
    # Test 5: validate_payment — amount too large
    ok, err = validate_payment({"amount": 9999999, "currency": "usd"})
    if not ok and "exceeds" in str(err):
        passed += 1
    else:
        print("FAIL: test_amount_too_large")
        failed += 1
    
    # Test 6: validate_id
    ok, pid, err = validate_id("42")
    if ok and pid == 42:
        passed += 1
    else:
        print("FAIL: test_valid_id")
        failed += 1
    
    # Test 7: validate_id — invalid
    ok, pid, err = validate_id("abc")
    if not ok:
        passed += 1
    else:
        print("FAIL: test_invalid_id")
        failed += 1
    
    # Test 8: validate_id — zero
    ok, pid, err = validate_id("0")
    if not ok:
        passed += 1
    else:
        print("FAIL: test_zero_id")
        failed += 1
    
    print("Tests: " + str(passed) + " passed, " + str(failed) + " failed")
    return failed == 0

# ── CLI ────────────────────────────────────────────────
def main():
    if "--test" in sys.argv:
        ok = run_tests()
        sys.exit(0 if ok else 1)
    
    if "--help" in sys.argv or "-h" in sys.argv:
        print(__doc__)
        return 0
    
    port = 8765
    for arg in sys.argv:
        if arg.startswith("--port="):
            port = int(arg.split("=")[1])
    
    server = HTTPServer(("0.0.0.0", port), APIHandler)
    print("API running on http://0.0.0.0:" + str(port))
    print("Endpoints: GET/POST /payments, GET/PUT /payments/{id}, GET /health")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Shutting down...")
        server.server_close()
    return 0

if __name__ == "__main__":
    sys.exit(main())
