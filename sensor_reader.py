#!/usr/bin/env python3
"""
Industrial Sensor Reader Simulator & Data Exporter.
Features:
- CLI mode: Run with input/output args to format JSON/CSV into numbered text.
- GUI mode: Run without args to open a standalone desktop app.
- GUI Capabilities:
  * Load PDF blueprint checksheet, JSON, or CSV.
  * Auto-generate compliant (PASS) or non-compliant (FAIL) measurements.
  * Manually edit values in a structured table.
  * Export values to a pipe-delimited text file protected by a SHA256 checksum.
"""

import sys
import os
import re
import json
import csv
import argparse
import hashlib
from datetime import datetime

# GUI Imports
try:
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
    GUI_SUPPORTED = True
except ImportError:
    GUI_SUPPORTED = False

# PDF Extraction Imports
try:
    import fitz  # PyMuPDF
    FITZ_AVAILABLE = True
except ImportError:
    try:
        from pypdf import PdfReader
        PYPDF_AVAILABLE = True
        FITZ_AVAILABLE = False
    except ImportError:
        FITZ_AVAILABLE = False
        PYPDF_AVAILABLE = False

# --- Core Parsing Logic (Reused from Main App) ---
UNIT_PATTERN = (
    r"(?<![A-Za-z])Format|(?:°\s*C|deg\s*C|degrees?\s*C|%T|%|"
    r"kOhm|MOhm|ohms?|mV|kV|VDC|VAC|volts?|V|mA|A|CCA|"
    r"mm|cm|nm|kg|RPM|PSI|dB|ABS|kbps|Mbps|GHz|MHz|kHz|Hz|ms|secs?|seconds?|s|m|g)"
    r"(?![A-Za-z])"
)
NUMBER_PATTERN = r"[+-]?(?:\d+(?:\.\d+)?|\.\d+)"

def clean_pdf_text(text):
    text = text or ""
    replacements = {"â€“": "-", "â€”": "-", "−": "-", "–": "-", "—": "-", "Â±": "±", "+/-": "±", "â‰¤": "<=", "≤": "<=", "â‰¥": ">=", "≥": ">="}
    for bad, good in replacements.items():
        text = text.replace(bad, good)
    return text.strip()

def extract_pdf_text(file_path):
    if FITZ_AVAILABLE:
        try:
            doc = fitz.open(file_path)
            return "\n".join(page.get_text() for page in doc).strip()
        except Exception as e:
            print(f"PyMuPDF error: {e}")
    if PYPDF_AVAILABLE:
        try:
            reader = PdfReader(file_path)
            return "\n".join(page.extract_text() or "" for page in reader.pages).strip()
        except Exception as e:
            print(f"pypdf error: {e}")
    return ""

def parse_checksheet_spec_line(line):
    line = clean_pdf_text(line)
    # Simple regex to check for limits
    num_unit = rf"({NUMBER_PATTERN})\s*({UNIT_PATTERN})?"
    
    # Extract unit
    unit_match = re.search(UNIT_PATTERN, line, re.IGNORECASE)
    unit = unit_match.group(0) if unit_match else None
    
    # Extract limits
    min_val, max_val, r_type = None, None, "unknown"
    
    if "between" in line.lower() or re.search(rf"{num_unit}\s*(?:-|to)\s*{num_unit}", line, re.IGNORECASE):
        matches = re.findall(NUMBER_PATTERN, line)
        if len(matches) >= 2:
            left, right = float(matches[0]), float(matches[1])
            min_val, max_val = min(left, right), max(left, right)
            r_type = "range"
    elif "±" in line:
        matches = re.findall(NUMBER_PATTERN, line)
        if len(matches) >= 2:
            center, delta = float(matches[0]), float(matches[1])
            min_val, max_val = center - delta, center + delta
            r_type = "range"
    elif ">=" in line or "min" in line.lower() or "not less than" in line.lower():
        matches = re.findall(NUMBER_PATTERN, line)
        if matches:
            min_val = float(matches[0])
            r_type = "min_only"
    elif "<=" in line or "max" in line.lower() or "not more than" in line.lower():
        matches = re.findall(NUMBER_PATTERN, line)
        if matches:
            max_val = float(matches[0])
            r_type = "max_only"
    elif "equal" in line.lower() or "exact" in line.lower():
        matches = re.findall(NUMBER_PATTERN, line)
        if matches:
            min_val = float(matches[0])
            max_val = min_val
            r_type = "exact"
            
    # Title extraction
    title = re.sub(r"^\d+[\).]?\s*", "", line)
    # Clean suffix values
    title = re.split(r"_{2,}|[±<=]|\bbetween\b", title, maxsplit=1)[0].strip(" :-")
    
    return {
        "title": title,
        "min": min_val,
        "max": max_val,
        "range_type": r_type,
        "unit": unit
    }

def make_line(idx, name, value, unit=None):
    if unit:
        return f"{idx:02d} | {name} | {value} | {unit}"
    return f"{idx:02d} | {name} | {value} | "

# --- GUI Application Implementation ---
if GUI_SUPPORTED:
    class SensorReaderApp:
        def __init__(self, root):
            self.root = root
            self.root.title("BEL Standalone Sensor Reader App")
            self.root.geometry("820x600")
            self.root.configure(bg="#0a1424")
            
            self.items = [] # List of parsed dicts: {ref, name, value, unit, min, max, range_type}
            self.template_name = "Comprehensive 20-Point Vehicle Inspection"
            
            # Setup styling
            self.style = ttk.Style()
            self.style.theme_use("clam")
            self.style.configure(".", background="#0a1424", foreground="#f7f9fc", fieldbackground="#0f1c31")
            self.style.configure("Treeview", background="#0f1c31", foreground="#f7f9fc", fieldbackground="#0f1c31", bordercolor="#203450", rowheight=26)
            self.style.configure("Treeview.Heading", background="#1d2e47", foreground="#51b7ff", font=("Segoe UI", 10, "bold"))
            self.style.map("Treeview", background=[("selected", "#1a73e8")], foreground=[("selected", "#ffffff")])
            
            self._create_widgets()
            
        def _create_widgets(self):
            # Top Controls Frame
            top_frame = tk.Frame(self.root, bg="#0a1424", pady=15, px=20)
            top_frame.pack(fill=tk.X)
            
            title_lbl = tk.Label(top_frame, text="⚡ BEL Industrial Sensor Reader Simulator", font=("Segoe UI", 15, "bold"), fg="#51b7ff", bg="#0a1424")
            title_lbl.pack(side=tk.LEFT)
            
            # Action Buttons Frame
            btn_frame = tk.Frame(self.root, bg="#0a1424", padx=20, pady=5)
            btn_frame.pack(fill=tk.X)
            
            load_btn = tk.Button(btn_frame, text="📁 Load PDF Blueprint", command=self.load_pdf, bg="#1a73e8", fg="white", font=("Segoe UI", 9, "bold"), padx=10, pady=5, border=0)
            load_btn.pack(side=tk.LEFT, padx=5)
            
            load_json_btn = tk.Button(btn_frame, text="📂 Load JSON/CSV", command=self.load_data_file, bg="#203450", fg="#bdc9dd", font=("Segoe UI", 9), padx=10, pady=5, border=0)
            load_json_btn.pack(side=tk.LEFT, padx=5)
            
            fill_pass_btn = tk.Button(btn_frame, text="✅ Auto-Fill PASS Values", command=lambda: self.fill_values(True), bg="#1a7344", fg="white", font=("Segoe UI", 9, "bold"), padx=10, pady=5, border=0)
            fill_pass_btn.pack(side=tk.LEFT, padx=5)
            
            fill_fail_btn = tk.Button(btn_frame, text="❌ Auto-Fill FAIL Values", command=lambda: self.fill_values(False), bg="#9b2a2a", fg="white", font=("Segoe UI", 9, "bold"), padx=10, pady=5, border=0)
            fill_fail_btn.pack(side=tk.LEFT, padx=5)
            
            # Treeview Table for values editing
            table_frame = tk.Frame(self.root, bg="#0a1424", padx=20, pady=10)
            table_frame.pack(fill=tk.BOTH, expand=True)
            
            columns = ("ref", "name", "value", "unit", "spec")
            self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=15)
            self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            
            self.tree.heading("ref", text="Ref ID")
            self.tree.heading("name", text="Parameter Name")
            self.tree.heading("value", text="Measured Value")
            self.tree.heading("unit", text="Unit")
            self.tree.heading("spec", text="Range Specifications")
            
            self.tree.column("ref", width=60, anchor=tk.CENTER)
            self.tree.column("name", width=260, anchor=tk.W)
            self.tree.column("value", width=120, anchor=tk.CENTER)
            self.tree.column("unit", width=80, anchor=tk.CENTER)
            self.tree.column("spec", width=220, anchor=tk.W)
            
            sb = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
            sb.pack(side=tk.RIGHT, fill=tk.Y)
            self.tree.configure(yscrollcommand=sb.set)
            
            self.tree.bind("<Double-1>", self.on_double_click)
            
            # Bottom Save Frame
            bottom_frame = tk.Frame(self.root, bg="#0a1424", pady=15, padx=20)
            bottom_frame.pack(fill=tk.X)
            
            # Template name display/selector
            temp_lbl = tk.Label(bottom_frame, text="Active Template Matching:", font=("Segoe UI", 9), fg="#bdc9dd", bg="#0a1424")
            temp_lbl.pack(side=tk.LEFT, padx=5)
            
            self.temp_combo = ttk.Combobox(bottom_frame, values=[
                "Comprehensive 20-Point Vehicle Inspection",
                "Equipment Performance Verification"
            ], width=40)
            self.temp_combo.set(self.template_name)
            self.temp_combo.pack(side=tk.LEFT, padx=5)
            self.temp_combo.bind("<<ComboboxSelected>>", self.on_template_change)
            
            save_btn = tk.Button(bottom_frame, text="💾 Save Checksummed Log (.txt)", command=self.save_log, bg="#2c7be5", fg="white", font=("Segoe UI", 10, "bold"), padx=15, pady=8, border=0)
            save_btn.pack(side=tk.RIGHT, padx=5)
            
        def on_template_change(self, event):
            self.template_name = self.temp_combo.get()
            
        def load_pdf(self):
            file_path = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])
            if not file_path:
                return
            
            text = extract_pdf_text(file_path)
            if not text:
                messagebox.showerror("Error", "Could not extract text from PDF. Make sure PyMuPDF or pypdf is installed.")
                return
                
            lines = text.splitlines()
            self.items = []
            ref_idx = 1
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                # Match line starts with digits
                if re.match(r"^\d+", line):
                    spec = parse_checksheet_spec_line(line)
                    if spec["title"]:
                        self.items.append({
                            "ref": ref_idx,
                            "name": spec["title"],
                            "value": "",
                            "unit": spec["unit"] or "",
                            "min": spec["min"],
                            "max": spec["max"],
                            "range_type": spec["range_type"]
                        })
                        ref_idx += 1
            
            # Match template type based on text content
            if "coolant" in text.lower() or "tyre" in text.lower() or "brake" in text.lower():
                self.template_name = "Comprehensive 20-Point Vehicle Inspection"
            else:
                self.template_name = "Equipment Performance Verification"
            self.temp_combo.set(self.template_name)
            
            self.refresh_table()
            messagebox.showinfo("Success", f"Successfully loaded PDF and parsed {len(self.items)} parameters!")
            
        def load_data_file(self):
            file_path = filedialog.askopenfilename(filetypes=[("JSON/CSV files", "*.json;*.csv")])
            if not file_path:
                return
                
            ext = os.path.splitext(file_path)[1].lower()
            self.items = []
            
            try:
                if ext == ".json":
                    with open(file_path, "r", encoding="utf-8") as f:
                        obj = json.load(f)
                    if isinstance(obj, list):
                        for i, item in enumerate(obj, start=1):
                            self.items.append({
                                "ref": i,
                                "name": item.get("name") or item.get("parameter") or f"param_{i}",
                                "value": str(item.get("value", "")),
                                "unit": item.get("unit") or "",
                                "min": item.get("min"),
                                "max": item.get("max"),
                                "range_type": item.get("range_type", "unknown")
                            })
                    elif isinstance(obj, dict):
                        for i, (k, v) in enumerate(obj.items(), start=1):
                            val = v.get("value", "") if isinstance(v, dict) else v
                            unit = v.get("unit", "") if isinstance(v, dict) else ""
                            self.items.append({
                                "ref": i,
                                "name": k,
                                "value": str(val),
                                "unit": unit,
                                "min": v.get("min") if isinstance(v, dict) else None,
                                "max": v.get("max") if isinstance(v, dict) else None,
                                "range_type": v.get("range_type", "unknown") if isinstance(v, dict) else "unknown"
                            })
                elif ext == ".csv":
                    with open(file_path, newline='', encoding='utf-8') as f:
                        reader = csv.reader(f)
                        for i, row in enumerate(reader, start=1):
                            if not row:
                                continue
                            name = row[0].strip()
                            value = row[1].strip() if len(row) > 1 else ""
                            unit = row[2].strip() if len(row) > 2 else ""
                            self.items.append({
                                "ref": i,
                                "name": name,
                                "value": value,
                                "unit": unit,
                                "min": None,
                                "max": None,
                                "range_type": "unknown"
                            })
                self.refresh_table()
                messagebox.showinfo("Success", f"Loaded data file with {len(self.items)} entries.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load file: {e}")
                
        def fill_values(self, pass_compliance=True):
            import random
            if not self.items:
                messagebox.showwarning("Warning", "No parameters loaded. Load a template PDF first.")
                return
                
            for item in self.items:
                r_type = item.get("range_type", "unknown")
                min_v = item.get("min")
                max_v = item.get("max")
                
                # Visual Check logic
                if r_type == "visual" or not item.get("unit") or item.get("unit") == "":
                    if pass_compliance:
                        # Find valid condition terms
                        item["value"] = "clean / intact / no cracks"
                    else:
                        item["value"] = "dirty / leaking / cracked"
                    continue
                    
                # Numeric checks
                if r_type == "range" and min_v is not None and max_v is not None:
                    if pass_compliance:
                        val = round(random.uniform(min_v, max_v), 1)
                    else:
                        val = round(max_v + random.uniform(1.0, 5.0), 1)
                    item["value"] = str(val)
                elif r_type == "min_only" and min_v is not None:
                    if pass_compliance:
                        val = round(min_v + random.uniform(1.0, 50.0), 1)
                    else:
                        val = round(min_v - random.uniform(1.0, 10.0), 1)
                    item["value"] = str(val)
                elif r_type == "max_only" and max_v is not None:
                    if pass_compliance:
                        val = round(max_v - random.uniform(0.1, 5.0), 2)
                    else:
                        val = round(max_v + random.uniform(0.5, 3.0), 2)
                    item["value"] = str(val)
                elif r_type == "exact" and min_v is not None:
                    if pass_compliance:
                        val = min_v
                    else:
                        val = min_v + 1.0
                    item["value"] = str(val)
                else:
                    # Default mock readings if ranges are unknown
                    if pass_compliance:
                        item["value"] = "1.0"
                    else:
                        item["value"] = "-1.0"
                        
            self.refresh_table()
            
        def refresh_table(self):
            # Clear treeview
            for r in self.tree.get_children():
                self.tree.delete(r)
                
            for item in self.items:
                spec_str = ""
                r_type = item.get("range_type", "unknown")
                min_v = item.get("min")
                max_v = item.get("max")
                unit = item.get("unit", "")
                
                if r_type == "range":
                    spec_str = f"{min_v} to {max_v} {unit}"
                elif r_type == "min_only":
                    spec_str = f">= {min_v} {unit}"
                elif r_type == "max_only":
                    spec_str = f"<= {max_v} {unit}"
                elif r_type == "exact":
                    spec_str = f"== {min_v} {unit}"
                else:
                    spec_str = "Visual inspection"
                    
                self.tree.insert("", tk.END, values=(
                    f"{item['ref']:02d}",
                    item["name"],
                    item["value"],
                    item["unit"],
                    spec_str
                ))
                
        def on_double_click(self, event):
            item_id = self.tree.identify_row(event.y)
            column = self.tree.identify_column(event.x)
            
            if not item_id or column != "#3": # Only edit Measured Value column
                return
                
            # Get values of double clicked row
            vals = self.tree.item(item_id, "values")
            ref_val = vals[0]
            curr_val = vals[2]
            
            # Open a simple dialog window to edit the value
            dialog = tk.Toplevel(self.root)
            dialog.title("Edit Value")
            dialog.geometry("300x120")
            dialog.configure(bg="#0f1c31")
            dialog.transient(self.root)
            dialog.grab_set()
            
            lbl = tk.Label(dialog, text=f"Enter Value for {vals[1]}:", fg="#bdc9dd", bg="#0f1c31", font=("Segoe UI", 9))
            lbl.pack(pady=10)
            
            entry = tk.Entry(dialog, font=("Segoe UI", 10), bg="#0a1424", fg="#f7f9fc", insertbackground="white")
            entry.insert(0, curr_val)
            entry.pack(pady=5, fill=tk.X, padx=20)
            entry.focus_set()
            
            def save_value():
                new_val = entry.get().strip()
                # Find matching item in self.items
                for i in self.items:
                    if f"{i['ref']:02d}" == ref_val:
                        i["value"] = new_val
                        break
                self.refresh_table()
                dialog.destroy()
                
            entry.bind("<Return>", lambda e: save_value())
            
        def save_log(self):
            if not self.items:
                messagebox.showwarning("Warning", "No data to save. Load checksheet and populate readings first.")
                return
                
            file_path = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text files", "*.txt")])
            if not file_path:
                return
                
            # Compile file lines
            lines = [
                f"# BEL Sensor Reader Telemetry Data",
                f"# Template: {self.template_name}",
                f"# Timestamp: {datetime.now().isoformat()}"
            ]
            
            data_lines = []
            for item in self.items:
                data_lines.append(make_line(item["ref"], item["name"], item["value"], item["unit"]))
                
            lines.extend(data_lines)
            
            # Compute SHA256 checksum of data lines
            recomputed_content = "\n".join(data_lines).strip()
            checksum = hashlib.sha256(recomputed_content.encode('utf-8')).hexdigest()
            
            lines.append(f"CHECKSUM: {checksum}")
            
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write("\n".join(lines))
                messagebox.showinfo("Success", f"Data exported with checksum to {os.path.basename(file_path)} successfully!")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save data: {e}")

# --- CLI Execution Mode ---
def main():
    if len(sys.argv) > 1:
        # CLI Mode
        parser = argparse.ArgumentParser(description="Standalone Sensor Reader Data Formatter")
        parser.add_argument('input', help='Input JSON or CSV file path')
        parser.add_argument('output', help='Output text file path')
        parser.add_argument('--template', default="Comprehensive 20-Point Vehicle Inspection", help='Matched Checkshet Template Name')
        args = parser.parse_args()
        
        inp = args.input
        out = args.output
        
        if not os.path.exists(inp):
            print(f"Input file not found: {inp}")
            sys.exit(1)
            
        ext = os.path.splitext(inp)[1].lower()
        items = []
        try:
            if ext == '.json':
                with open(inp, 'r', encoding='utf-8') as f:
                    obj = json.load(f)
                if isinstance(obj, list):
                    for i, item in enumerate(obj, start=1):
                        items.append((i, item.get("name") or f"param_{i}", item.get("value", ""), item.get("unit")))
                elif isinstance(obj, dict):
                    for i, (k, v) in enumerate(obj.items(), start=1):
                        val = v.get("value") if isinstance(v, dict) else v
                        unit = v.get("unit") if isinstance(v, dict) else None
                        items.append((i, k, val, unit))
            elif ext in ('.csv', '.txt'):
                with open(inp, newline='', encoding='utf-8') as csvfile:
                    reader = csv.reader(csvfile)
                    for i, row in enumerate(reader, start=1):
                        if not row:
                            continue
                        name = row[0].strip()
                        value = row[1].strip() if len(row) > 1 else ''
                        unit = row[2].strip() if len(row) > 2 else None
                        items.append((i, name, value, unit))
        except Exception as e:
            print(f"Failed to parse input: {e}")
            sys.exit(2)
            
        # Write checksummed text
        lines = [
            f"# BEL Sensor Reader Telemetry Data",
            f"# Template: {args.template}",
            f"# Timestamp: {datetime.now().isoformat()}"
        ]
        
        data_lines = []
        for ref, name, val, unit in items:
            data_lines.append(make_line(ref, name, val, unit))
            
        lines.extend(data_lines)
        recomputed_content = "\n".join(data_lines).strip()
        checksum = hashlib.sha256(recomputed_content.encode('utf-8')).hexdigest()
        lines.append(f"CHECKSUM: {checksum}")
        
        try:
            with open(out, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines))
            print(f"Wrote {len(items)} lines with checksum to {out}")
        except Exception as e:
            print(f"Failed to write output: {e}")
            sys.exit(3)
    else:
        # GUI Mode
        if not GUI_SUPPORTED:
            print("GUI modules (tkinter) not supported in this terminal environment. Run with arguments for CLI mode:")
            print("python sensor_reader.py input.json output.txt")
            sys.exit(1)
            
        root = tk.Tk()
        app = SensorReaderApp(root)
        root.mainloop()

if __name__ == '__main__':
    main()

