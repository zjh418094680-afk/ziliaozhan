#!/usr/bin/env python3
"""
Training 3: CLI Data Processor
- Read CSV/JSON, process, output
- Error handling for every failure mode
- --dry-run, --validate, --output flags
- Exit codes: 0=success, 1=validation, 2=io_error, 3=parse_error

Usage:
  python3 proc.py data.csv --output result.json
  python3 proc.py data.json --validate
  python3 proc.py data.csv --stats
"""
import sys
import os
import json
import csv
import io
from pathlib import Path

EXIT_OK = 0
EXIT_VALIDATION = 1
EXIT_IO = 2
EXIT_PARSE = 3

def read_file(path):
    """Read file, auto-detect format. Returns (data, format, error)."""
    if not os.path.exists(path):
        return None, None, "File not found: " + path
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = f.read()
    except PermissionError:
        return None, None, "Permission denied: " + path
    except Exception as e:
        return None, None, "Read error: " + str(e)
    
    if not raw.strip():
        return None, None, "File is empty: " + path
    
    # Try JSON
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return data, "json", None
        if isinstance(data, dict) and "data" in data:
            return data["data"], "json", None
        return None, None, "JSON must be array or {data: [...]}"
    except json.JSONDecodeError:
        pass
    
    # Try CSV
    try:
        reader = csv.DictReader(io.StringIO(raw))
        rows = [row for row in reader]
        if rows:
            return rows, "csv", None
        return None, None, "CSV has no data rows"
    except Exception:
        pass
    
    return None, None, "Cannot parse file (not valid JSON or CSV)"

def validate_row(row, index):
    """Validate a single data row. Returns list of error strings."""
    errors = []
    
    if "amount" in row:
        try:
            val = float(row["amount"])
            if val <= 0:
                errors.append("Row " + str(index) + ": amount must be positive")
            if val > 1000000:
                errors.append("Row " + str(index) + ": amount too large")
        except (ValueError, TypeError):
            errors.append("Row " + str(index) + ": amount is not a number")
    
    if "currency" in row and row["currency"]:
        valid = {"usd", "eur", "gbp", "jpy", "cny"}
        if row["currency"].lower() not in valid:
            errors.append("Row " + str(index) + ": invalid currency '" + row["currency"] + "'")
    
    if "email" in row and row["email"]:
        if "@" not in row["email"]:
            errors.append("Row " + str(index) + ": invalid email format")
    
    return errors

def compute_stats(data):
    """Compute summary statistics."""
    stats = {"total_rows": len(data), "numeric_fields": {}}
    
    for row in data:
        for key, val in row.items():
            try:
                num = float(val)
                if key not in stats["numeric_fields"]:
                    stats["numeric_fields"][key] = {"count": 0, "sum": 0, "min": num, "max": num}
                s = stats["numeric_fields"][key]
                s["count"] += 1
                s["sum"] += num
                if num < s["min"]:
                    s["min"] = num
                if num > s["max"]:
                    s["max"] = num
            except (ValueError, TypeError):
                pass
    
    for key in stats["numeric_fields"]:
        s = stats["numeric_fields"][key]
        s["avg"] = round(s["sum"] / s["count"], 2) if s["count"] > 0 else 0
    
    return stats

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = [a for a in sys.argv[1:] if a.startswith("--")]
    
    if "--help" in flags or "-h" in flags:
        print(__doc__)
        return EXIT_OK
    
    if not args:
        print("ERROR: No input file specified. Use --help for usage.", file=sys.stderr)
        return EXIT_IO
    
    input_path = args[0]
    output_path = None
    for f in flags:
        if f.startswith("--output="):
            output_path = f.split("=", 1)[1]
    
    # Read
    data, fmt, err = read_file(input_path)
    if err:
        print("ERROR: " + err, file=sys.stderr)
        return EXIT_IO
    
    print("Read " + str(len(data)) + " rows from " + input_path + " (" + fmt + ")")
    
    # Validate
    if "--validate" in flags:
        all_errors = []
        for i, row in enumerate(data):
            errors = validate_row(row, i + 1)
            all_errors.extend(errors)
        
        if all_errors:
            for e in all_errors:
                print("  " + e, file=sys.stderr)
            print("VALIDATION FAILED: " + str(len(all_errors)) + " error(s)", file=sys.stderr)
            return EXIT_VALIDATION
        print("VALIDATION PASSED: " + str(len(data)) + " rows valid")
    
    # Stats
    if "--stats" in flags:
        stats = compute_stats(data)
        print(json.dumps(stats, indent=2))
    
    # Output
    if output_path:
        if "--dry-run" in flags:
            print("DRY RUN: would write " + str(len(data)) + " rows to " + output_path)
        else:
            try:
                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                print("Wrote " + str(len(data)) + " rows to " + output_path)
            except Exception as e:
                print("ERROR: Cannot write " + output_path + ": " + str(e), file=sys.stderr)
                return EXIT_IO
    
    return EXIT_OK

if __name__ == "__main__":
    sys.exit(main())
