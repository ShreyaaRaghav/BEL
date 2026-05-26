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

    conn.commit()
    conn.close()
    print(f"Database ready at: {DB_PATH}")

if __name__ == "__main__":
    init()
