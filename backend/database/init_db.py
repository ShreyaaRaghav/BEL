import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "checksheet.db")

def init():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.executescript("""
    PRAGMA foreign_keys = ON;

    CREATE TABLE IF NOT EXISTS checksheet_templates (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        template_name   TEXT NOT NULL,
        form_ref        TEXT,
        org_name        TEXT,
        checksheet_type TEXT NOT NULL,
        created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS check_items (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        template_id    INTEGER NOT NULL REFERENCES checksheet_templates(id),
        ref_number     INTEGER NOT NULL,
        parameter_name TEXT NOT NULL,
        unit           TEXT,
        range_standard TEXT,
        range_min      REAL,
        range_max      REAL,
        range_type     TEXT DEFAULT 'between'
    );

    CREATE TABLE IF NOT EXISTS inspection_sessions (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        template_id     INTEGER NOT NULL REFERENCES checksheet_templates(id),
        vehicle_model   TEXT,
        vin_chassis     TEXT,
        odometer_km     TEXT,
        instrument_name TEXT,
        model_serial    TEXT,
        location_dept   TEXT,
        next_due_date   TEXT,
        lead_technician TEXT,
        job_card_no     TEXT,
        inspection_date TEXT,
        overall_status  TEXT NOT NULL DEFAULT 'PENDING',
        submitted_at    DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS inspection_results (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id       INTEGER NOT NULL REFERENCES inspection_sessions(id) ON DELETE CASCADE,
        check_item_id    INTEGER NOT NULL REFERENCES check_items(id),
        measured_value   TEXT,
        measured_numeric REAL,
        status           TEXT NOT NULL DEFAULT 'PENDING',
        notes            TEXT
    );

    CREATE INDEX IF NOT EXISTS idx_results_session   ON inspection_results(session_id);
    CREATE INDEX IF NOT EXISTS idx_items_template    ON check_items(template_id);
    CREATE INDEX IF NOT EXISTS idx_sessions_template ON inspection_sessions(template_id);
    """)

    cur.execute("SELECT COUNT(*) FROM checksheet_templates")
    if cur.fetchone()[0] == 0:
        cur.executescript("""
        INSERT INTO checksheet_templates (template_name, form_ref, org_name, checksheet_type)
        VALUES ('Comprehensive 20-Point Vehicle Inspection', 'VMI-REV-2026', 'APEX AUTOMOTIVE SERVICES', 'vehicle');

        INSERT INTO check_items (template_id, ref_number, parameter_name, unit, range_standard, range_min, range_max, range_type) VALUES
        (1,  1,  'Engine Oil Level & Condition',        NULL,  'MIN-MAX Line / Clean',    NULL,   NULL,   'visual'),
        (1,  2,  'Engine Coolant Freeze Point',         'C',   '-25C to -37C',            -37.0,  -25.0,  'between'),
        (1,  3,  'Battery Cold Cranking Amps (CCA)',    'CCA', '>=80% of Rated Value',     80.0,   NULL,   'min_only'),
        (1,  4,  'Alternator Charging Voltage',         'V',   '13.8V - 14.7V',            13.8,   14.7,   'between'),
        (1,  5,  'Brake Fluid Moisture Content',        '%',   '< 2.0% H2O',               NULL,   2.0,    'max_only'),
        (1,  6,  'Front Brake Pad Thickness',           'mm',  '>=4.0 mm',                  4.0,   NULL,   'min_only'),
        (1,  7,  'Rear Brake Pad Thickness',            'mm',  '>=3.0 mm',                  3.0,   NULL,   'min_only'),
        (1,  8,  'Tyre Tread Depth (Front Left)',       'mm',  '>=3.0 mm',                  3.0,   NULL,   'min_only'),
        (1,  9,  'Tyre Tread Depth (Front Right)',      'mm',  '>=3.0 mm',                  3.0,   NULL,   'min_only'),
        (1,  10, 'Tyre Tread Depth (Rear Left)',        'mm',  '>=3.0 mm',                  3.0,   NULL,   'min_only'),
        (1,  11, 'Tyre Tread Depth (Rear Right)',       'mm',  '>=3.0 mm',                  3.0,   NULL,   'min_only'),
        (1,  12, 'Tyre Pressure (Cold - Front)',        'PSI', '32 PSI - 35 PSI',           32.0,  35.0,   'between'),
        (1,  13, 'Tyre Pressure (Cold - Rear)',         'PSI', '32 PSI - 35 PSI',           32.0,  35.0,   'between'),
        (1,  14, 'Serpentine Drive Belt Tension',       NULL,  'No Cracks / Firm',          NULL,  NULL,   'visual'),
        (1,  15, 'Steering Play / Backlash',            'mm',  '<=10 mm',                   NULL,  10.0,   'max_only'),
        (1,  16, 'Suspension Shock Absorber Leaks',     NULL,  'Visual: Dry / Sealed',      NULL,  NULL,   'visual'),
        (1,  17, 'Exhaust Emissions Backpressure',      'PSI', '<=1.2 PSI at Idle',         NULL,  1.2,    'max_only'),
        (1,  18, 'A/C Vent Lowest Temp Output',         'C',   '4.0C - 8.0C',               4.0,   8.0,   'between'),
        (1,  19, 'Windscreen Wiper Blade Condition',    NULL,  'Streak-free / Intact',      NULL,  NULL,   'visual'),
        (1,  20, 'OBD-II Fault Codes Scan',             NULL,  'Zero Active DTCs',          NULL,  NULL,   'visual');

        INSERT INTO checksheet_templates (template_name, form_ref, org_name, checksheet_type)
        VALUES ('Equipment Performance Verification', 'CHK-GEN-004', 'APEX METROLOGY & CALIBRATION LABS', 'instrument');

        INSERT INTO check_items (template_id, ref_number, parameter_name, unit, range_standard, range_min, range_max, range_type) VALUES
        (2,  1,  'Baseline Voltage Stability',           'V',    '4.95V - 5.05V',        4.95,   5.05,   'between'),
        (2,  2,  'Wavelength Accuracy (Deuterium D2)',   'nm',   '656.1nm +/- 0.2nm',    655.9,  656.3,  'between'),
        (2,  3,  'Photometric Linearity (at 1.0 ABS)',   'ABS',  '0.995 - 1.005 ABS',    0.995,  1.005,  'between'),
        (2,  4,  'Stray Light Threshold (at 220 nm)',    '%T',   '<=0.020 %T',            NULL,   0.020,  'max_only'),
        (2,  5,  'Optical Alignment / Lamp Energy',      'mA',   '45.0mA - 52.0mA',      45.0,   52.0,   'between'),
        (2,  6,  'Chamber Core Temperature',             'C',    '23.5 +/- 1.5C',         22.0,   25.0,   'between'),
        (2,  7,  'Cooling Fan Noise / Speed',            'RPM',  '2400 - 2800 RPM',      2400.0, 2800.0, 'between'),
        (2,  8,  'Signal-to-Noise Ratio (RMS)',          'dB',   '>=60.0 dB',             60.0,   NULL,   'min_only'),
        (2,  9,  'Zero-Point Drift (over 30 mins)',      'ABS',  '<=0.001 ABS/hr',        NULL,   0.001,  'max_only'),
        (2,  10, 'Interface/RS232 Data Transmit Rate',   'kbps', '9.6 +/- 0.1 kbps',     9.5,    9.7,    'between');
        """)

    # Check if we need to seed inspection reports (automatic seeding disabled to use real data only)
    # cur.execute("SELECT COUNT(*) FROM inspection_sessions")
    # if cur.fetchone()[0] == 0:
    #     print("Seeding demo inspection data for analytics dashboard...")
    #     seed_demo_data(cur)


    conn.commit()
    conn.close()
    print(f"Database ready at: {DB_PATH}")

def seed_demo_data(cur):
    import random
    from datetime import datetime, timedelta

    # Define some seed helper datasets
    technicians = ["bel_engineer", "bel_admin"]
    
    # --- Template 1: Vehicle Inspections (10 reports) ---
    vehicles = [
        {"model": "Tata Nexon EV", "vin": "MAT612984NEX10029", "odometer": "12540"},
        {"model": "Mahindra XUV700", "vin": "MAH908123XUV77651", "odometer": "34190"},
        {"model": "Maruti Suzuki Swift", "vin": "MAR452812SWI90823", "odometer": "8450"},
        {"model": "Hyundai Creta", "vin": "HYU883012CRE77321", "odometer": "45200"},
        {"model": "Ashok Leyland Dost", "vin": "ASH552918DOS20912", "odometer": "61250"},
        {"model": "Tata Nexon EV", "vin": "MAT612984NEX10088", "odometer": "15300"},
        {"model": "Mahindra XUV700", "vin": "MAH908123XUV77992", "odometer": "22800"},
        {"model": "Hyundai Creta", "vin": "HYU883012CRE77884", "odometer": "11400"},
        {"model": "Maruti Suzuki Swift", "vin": "MAR452812SWI90544", "odometer": "29100"},
        {"model": "Tata Nexon EV", "vin": "MAT612984NEX10123", "odometer": "5200"}
    ]

    dates_t1 = [
        "2026-03-12", "2026-03-28", "2026-04-05", "2026-04-19", "2026-05-02",
        "2026-05-15", "2026-05-30", "2026-06-02", "2026-06-10", "2026-06-14"
    ]

    # Specific failure indicators to make dataset look realistic
    # Let's fail sessions: 2 (index 1), 5 (index 4), 8 (index 7)
    for i in range(10):
        veh = vehicles[i]
        date_str = dates_t1[i]
        tech = technicians[i % len(technicians)]
        job_card = f"JC-90{80 + i}"
        status = "FAIL" if i in [1, 4, 7] else "PASS"
        submitted_at = f"{date_str} 10:15:30"
        
        cur.execute("""
            INSERT INTO inspection_sessions (
                template_id, vehicle_model, vin_chassis, odometer_km, 
                lead_technician, job_card_no, inspection_date, overall_status, submitted_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (1, veh["model"], veh["vin"], veh["odometer"], tech, job_card, date_str, status, submitted_at))
        
        session_id = cur.lastrowid
        
        # Now seed check item results for this session (items 1 to 20)
        # item_id: parameter_name
        # 1: Engine Oil Level (visual)
        # 2: Engine Coolant Temp (between, -37.0 to -25.0)
        # 3: Battery CCA (min, >=80.0)
        # 4: Alternator Voltage (between, 13.8 to 14.7)
        # 5: Brake Fluid Moisture (max, <=2.0)
        # 6-11: Front/Rear pads, Tyre treads (min, >=3.0/4.0)
        # 12-13: Tyre pressure (between, 32.0 to 35.0)
        # 14: Serpentine Belt (visual)
        # 15: Steering Play (max, <=10.0)
        # 16: Suspension Shock (visual)
        # 17: Exhaust Backpressure (max, <=1.2)
        # 18: A/C Vent Temp (between, 4.0 to 8.0)
        # 19: Wiper Blade (visual)
        # 20: OBD-II Scan (visual)

        # Generate parameters: if status is PASS, everything is within limits.
        # If status is FAIL, make 1 or 2 items fail
        fails = []
        if status == "FAIL":
            if i == 1:
                fails = [4, 5]  # Fail alternator voltage and brake moisture
            elif i == 4:
                fails = [3]     # Fail battery CCA
            elif i == 7:
                fails = [15, 17] # Fail steering play and exhaust backpressure

        for item_id in range(1, 21):
            val_str = ""
            val_num = None
            res_status = "PASS"
            notes = ""

            if item_id == 1:
                res_status = "FAIL" if item_id in fails else "PASS"
                val_str = "Dirty / Low" if res_status == "FAIL" else "MIN-MAX Line / Clean"
            elif item_id == 2:
                val_num = -15.0 if item_id in fails else round(random.uniform(-35.0, -27.0), 1)
                val_str = str(val_num)
                res_status = "FAIL" if val_num > -25.0 or val_num < -37.0 else "PASS"
            elif item_id == 3:
                val_num = round(random.uniform(65.0, 78.0), 1) if item_id in fails else round(random.uniform(82.0, 98.0), 1)
                val_str = str(val_num)
                res_status = "FAIL" if val_num < 80.0 else "PASS"
            elif item_id == 4:
                val_num = round(random.uniform(13.0, 13.6), 2) if item_id in fails else round(random.uniform(13.9, 14.5), 2)
                val_str = str(val_num)
                res_status = "FAIL" if val_num < 13.8 or val_num > 14.7 else "PASS"
            elif item_id == 5:
                val_num = round(random.uniform(2.2, 3.8), 2) if item_id in fails else round(random.uniform(0.3, 1.8), 2)
                val_str = str(val_num)
                res_status = "FAIL" if val_num > 2.0 else "PASS"
            elif item_id in [6, 7]:
                limit = 4.0 if item_id == 6 else 3.0
                val_num = round(random.uniform(1.5, limit - 0.2), 1) if item_id in fails else round(random.uniform(limit + 0.5, 9.0), 1)
                val_str = str(val_num)
                res_status = "FAIL" if val_num < limit else "PASS"
            elif item_id in [8, 9, 10, 11]:
                val_num = round(random.uniform(1.0, 2.8), 1) if item_id in fails else round(random.uniform(3.2, 7.5), 1)
                val_str = str(val_num)
                res_status = "FAIL" if val_num < 3.0 else "PASS"
            elif item_id in [12, 13]:
                val_num = round(random.uniform(25.0, 30.0), 1) if item_id in fails else round(random.uniform(32.5, 34.8), 1)
                val_str = str(val_num)
                res_status = "FAIL" if val_num < 32.0 or val_num > 35.0 else "PASS"
            elif item_id == 14:
                res_status = "FAIL" if item_id in fails else "PASS"
                val_str = "Cracked / Loose" if res_status == "FAIL" else "No Cracks / Firm"
            elif item_id == 15:
                val_num = round(random.uniform(11.0, 16.0), 1) if item_id in fails else round(random.uniform(2.0, 8.5), 1)
                val_str = str(val_num)
                res_status = "FAIL" if val_num > 10.0 else "PASS"
            elif item_id == 16:
                res_status = "FAIL" if item_id in fails else "PASS"
                val_str = "Fluid Leaking" if res_status == "FAIL" else "Visual: Dry / Sealed"
            elif item_id == 17:
                val_num = round(random.uniform(1.4, 2.5), 2) if item_id in fails else round(random.uniform(0.2, 0.95), 2)
                val_str = str(val_num)
                res_status = "FAIL" if val_num > 1.2 else "PASS"
            elif item_id == 18:
                val_num = round(random.uniform(9.5, 14.0), 1) if item_id in fails else round(random.uniform(4.5, 7.8), 1)
                val_str = str(val_num)
                res_status = "FAIL" if val_num < 4.0 or val_num > 8.0 else "PASS"
            elif item_id == 19:
                res_status = "FAIL" if item_id in fails else "PASS"
                val_str = "Torn Rubber" if res_status == "FAIL" else "Streak-free / Intact"
            elif item_id == 20:
                res_status = "FAIL" if item_id in fails else "PASS"
                val_str = "MIL Active: P0301 Misfire" if res_status == "FAIL" else "Zero Active DTCs"

            if res_status == "FAIL":
                notes = "Alert: Measured value out of tolerance."
            else:
                notes = "In tolerance."

            cur.execute("""
                INSERT INTO inspection_results (session_id, check_item_id, measured_value, measured_numeric, status, notes)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (session_id, item_id, val_str, val_num, res_status, notes))

    # --- Template 2: Instrument Performance Verification (8 reports) ---
    instruments = [
        {"name": "Agilent HPLC-1260", "sn": "SN-99881", "dept": "Metrology Lab A", "due": "2026-09-12"},
        {"name": "Shimadzu UV-1900i", "sn": "SN-88224", "dept": "Quality Control Dept", "due": "2026-10-02"},
        {"name": "Thermo GC-MS", "sn": "SN-77332", "dept": "R&D Chem Lab", "due": "2026-10-20"},
        {"name": "Mettler Toledo Balance", "sn": "SN-66443", "dept": "Calibration Chamber 2", "due": "2026-11-10"},
        {"name": "Agilent HPLC-1260", "sn": "SN-99881", "dept": "Metrology Lab A", "due": "2026-11-22"},
        {"name": "Shimadzu UV-1900i", "sn": "SN-88224", "dept": "Quality Control Dept", "due": "2026-12-01"},
        {"name": "Thermo GC-MS", "sn": "SN-77332", "dept": "R&D Chem Lab", "due": "2026-12-08"},
        {"name": "Agilent HPLC-1260", "sn": "SN-99881", "dept": "Metrology Lab A", "due": "2026-12-15"}
    ]

    dates_t2 = [
        "2026-03-15", "2026-04-02", "2026-04-20", "2026-05-10", "2026-05-22",
        "2026-06-01", "2026-06-08", "2026-06-15"
    ]

    # Specific failure indicators to make dataset look realistic
    # Let's fail sessions: 3 (index 2) and 6 (index 5)
    for i in range(8):
        inst = instruments[i]
        date_str = dates_t2[i]
        tech = technicians[i % len(technicians)]
        job_card = f"JC-80{80 + i}"
        status = "FAIL" if i in [2, 5] else "PASS"
        submitted_at = f"{date_str} 14:22:00"
        
        cur.execute("""
            INSERT INTO inspection_sessions (
                template_id, instrument_name, model_serial, location_dept, next_due_date,
                lead_technician, job_card_no, inspection_date, overall_status, submitted_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (2, inst["name"], inst["sn"], inst["dept"], inst["due"], tech, job_card, date_str, status, submitted_at))
        
        session_id = cur.lastrowid
        
        # Now seed check item results for this session (items 21 to 30)
        # item_id: parameter_name
        # 21: Baseline Voltage Stability (between, 4.95 to 5.05)
        # 22: Wavelength Accuracy (Deuterium D2) (between, 655.9 to 656.3)
        # 23: Photometric Linearity (between, 0.995 to 1.005)
        # 24: Stray Light Threshold (max, <=0.020)
        # 25: Optical Alignment (between, 45.0 to 52.0)
        # 26: Chamber Core Temp (between, 22.0 to 25.0)
        # 27: Cooling Fan Speed (between, 2400 to 2800)
        # 28: SNR (min, >=60.0)
        # 29: Zero-Point Drift (max, <=0.001)
        # 30: RS232 Rate (between, 9.5 to 9.7)

        fails = []
        if status == "FAIL":
            if i == 2:
                fails = [21, 24]  # Fail voltage stability and stray light
            elif i == 5:
                fails = [28]      # Fail SNR

        for item_id in range(21, 31):
            val_str = ""
            val_num = None
            res_status = "PASS"
            notes = ""

            if item_id == 21:
                val_num = round(random.uniform(4.90, 4.93), 3) if item_id in fails else round(random.uniform(4.96, 5.04), 3)
                val_str = str(val_num)
                res_status = "FAIL" if val_num < 4.95 or val_num > 5.05 else "PASS"
            elif item_id == 22:
                val_num = round(random.uniform(655.4, 655.8), 2) if item_id in fails else round(random.uniform(656.0, 656.2), 2)
                val_str = str(val_num)
                res_status = "FAIL" if val_num < 655.9 or val_num > 656.3 else "PASS"
            elif item_id == 23:
                val_num = round(random.uniform(1.006, 1.015), 3) if item_id in fails else round(random.uniform(0.996, 1.004), 3)
                val_str = str(val_num)
                res_status = "FAIL" if val_num < 0.995 or val_num > 1.005 else "PASS"
            elif item_id == 24:
                val_num = round(random.uniform(0.022, 0.035), 4) if item_id in fails else round(random.uniform(0.005, 0.018), 4)
                val_str = str(val_num)
                res_status = "FAIL" if val_num > 0.020 else "PASS"
            elif item_id == 25:
                val_num = round(random.uniform(40.0, 44.5), 1) if item_id in fails else round(random.uniform(46.0, 51.5), 1)
                val_str = str(val_num)
                res_status = "FAIL" if val_num < 45.0 or val_num > 52.0 else "PASS"
            elif item_id == 26:
                val_num = round(random.uniform(25.5, 27.5), 1) if item_id in fails else round(random.uniform(22.5, 24.5), 1)
                val_str = str(val_num)
                res_status = "FAIL" if val_num < 22.0 or val_num > 25.0 else "PASS"
            elif item_id == 27:
                val_num = round(random.uniform(2000, 2350), 0) if item_id in fails else round(random.uniform(2450, 2750), 0)
                val_str = str(val_num)
                res_status = "FAIL" if val_num < 2400 or val_num > 2800 else "PASS"
            elif item_id == 28:
                val_num = round(random.uniform(52.0, 59.2), 1) if item_id in fails else round(random.uniform(60.5, 68.0), 1)
                val_str = str(val_num)
                res_status = "FAIL" if val_num < 60.0 else "PASS"
            elif item_id == 29:
                val_num = round(random.uniform(0.0012, 0.0028), 5) if item_id in fails else round(random.uniform(0.0001, 0.0008), 5)
                val_str = str(val_num)
                res_status = "FAIL" if val_num > 0.001 else "PASS"
            elif item_id == 30:
                val_num = round(random.uniform(9.2, 9.4), 2) if item_id in fails else round(random.uniform(9.55, 9.68), 2)
                val_str = str(val_num)
                res_status = "FAIL" if val_num < 9.5 or val_num > 9.7 else "PASS"

            if res_status == "FAIL":
                notes = "Metrology Alert: Parameter drift out of tolerance range."
            else:
                notes = "Verified in tolerance."

            cur.execute("""
                INSERT INTO inspection_results (session_id, check_item_id, measured_value, measured_numeric, status, notes)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (session_id, item_id, val_str, val_num, res_status, notes))

if __name__ == "__main__":
    init()

