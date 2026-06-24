#!/usr/bin/env python3
"""
Simple standalone sensor reader simulator.
Takes an input JSON or CSV of sensor readings and writes a numbered text file suitable for parser ingestion.

JSON input formats supported:
- List of objects: [{"ref":1, "name":"Tire length", "value":345, "unit":"mm"}, ...]
- Object mapping: {"Tire length": {"value":345, "unit":"mm"}, ...}

CSV format: name,value,unit

Usage: python sensor_reader.py input.json output.txt
"""
import sys
import json
import csv
import os
import argparse


def make_line(idx, name, value, unit=None):
    prefix = f"{idx:02d} "
    if unit:
        return f"{prefix}{name} {value} {unit}"
    return f"{prefix}{name} {value}"


def process_json(obj):
    lines = []
    if isinstance(obj, list):
        for i, item in enumerate(obj, start=1):
            name = item.get("name") or item.get("parameter") or item.get("param") or f"param_{i}"
            value = item.get("value")
            unit = item.get("unit")
            lines.append(make_line(i, name, value, unit))
    elif isinstance(obj, dict):
        # mapping name -> {value, unit}
        for i, (k, v) in enumerate(obj.items(), start=1):
            if isinstance(v, dict):
                value = v.get("value")
                unit = v.get("unit")
            else:
                value = v
                unit = None
            lines.append(make_line(i, k, value, unit))
    return lines


def process_csv(path):
    lines = []
    with open(path, newline='', encoding='utf-8') as csvfile:
        reader = csv.reader(csvfile)
        for i, row in enumerate(reader, start=1):
            if not row:
                continue
            name = row[0].strip()
            value = row[1].strip() if len(row) > 1 else ''
            unit = row[2].strip() if len(row) > 2 else None
            lines.append(make_line(i, name, value, unit))
    return lines


def main():
    parser = argparse.ArgumentParser(description="Sensor reader -> checksheet text formatter")
    parser.add_argument('input', help='Input JSON or CSV file path')
    parser.add_argument('output', help='Output text file path')
    args = parser.parse_args()

    inp = args.input
    out = args.output

    if not os.path.exists(inp):
        print(f"Input file not found: {inp}")
        sys.exit(1)

    ext = os.path.splitext(inp)[1].lower()
    lines = []
    try:
        if ext in ('.json',):
            with open(inp, 'r', encoding='utf-8') as f:
                obj = json.load(f)
            lines = process_json(obj)
        elif ext in ('.csv', '.txt'):
            lines = process_csv(inp)
        else:
            # try JSON then CSV
            try:
                with open(inp, 'r', encoding='utf-8') as f:
                    obj = json.load(f)
                lines = process_json(obj)
            except Exception:
                lines = process_csv(inp)
    except Exception as e:
        print(f"Failed to process input: {e}")
        sys.exit(2)

    with open(out, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    print(f"Wrote {len(lines)} lines to {out}")


if __name__ == '__main__':
    main()
