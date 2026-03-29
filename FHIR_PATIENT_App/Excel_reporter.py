from flask import Flask, render_template, request, jsonify, send_file, session, url_for
from flask_cors import CORS
import pandas as pd
import requests
from datetime import datetime
import json
import os
import random
from pathlib import Path
import uuid
import tempfile

# IMPORTANT: Configure Flask with correct static and template paths
app = Flask(__name__, 
            static_folder='../static',      # Path to static folder
            static_url_path='/static',       # URL path for static files
            template_folder='../templates')  # Path to templates folder

app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
CORS(app)

# Use /tmp for temporary files (Vercel allows writing to /tmp)
TEMP_DIR = tempfile.gettempdir()
REPORTS_DIR = os.path.join(TEMP_DIR, 'reports')
os.makedirs(REPORTS_DIR, exist_ok=True)

# FHIR Servers
HAPI_FHIR = "https://hapi.fhir.org/baseR4"
SMART_FHIR = "https://r4.smarthealthit.org"
OPENMRS = "https://openmrs.org/fhir"
CMS_FHIR = "https://sandbox.cms.gov/fhir"

# Helper functions (keep your existing functions here)
def generate_random_age():
    r = random.random()
    if r < 0.20:
        return random.randint(0, 17)
    elif r < 0.50:
        return random.randint(18, 35)
    elif r < 0.80:
        return random.randint(36, 60)
    else:
        return random.randint(61, 100)

def generate_birthdate_from_age(age):
    today = datetime.now()
    birth_year = today.year - age
    birth_month = random.randint(1, 12)
    
    if birth_month in [4, 6, 9, 11]:
        max_days = 30
    elif birth_month == 2:
        if (birth_year % 4 == 0 and birth_year % 100 != 0) or (birth_year % 400 == 0):
            max_days = 29
        else:
            max_days = 28
    else:
        max_days = 31
    
    birth_day = random.randint(1, max_days)
    birth_date = datetime(birth_year, birth_month, birth_day)
    
    if (today.month, today.day) < (birth_month, birth_day):
        birth_date = datetime(birth_year - 1, birth_month, birth_day)
    
    return birth_date.strftime('%Y-%m-%d')

def fetch_fhir_patients(fhir_server: str, limit: int = 50):
    url = f"{fhir_server}/Patient"
    params = {"_count": limit, "_format": "json"}
    
    try:
        response = requests.get(url, params=params, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            patients = []
            
            for entry in data.get('entry', []):
                resource = entry.get('resource', {})
                patient_id = resource.get('id', 'Unknown')
                
                if 'name' in resource and resource['name']:
                    name = resource['name'][0]
                    given = ' '.join(name.get('given', []))
                    family = name.get('family', '')
                    full_name = f"{given} {family}".strip()
                else:
                    full_name = "Unknown"
                
                gender = resource.get('gender', 'unknown')
                birth_date = resource.get('birthDate', None)
                
                age = None
                if birth_date:
                    try:
                        birth_year = int(birth_date.split('-')[0])
                        current_year = datetime.now().year
                        age = current_year - birth_year
                        if age < 0 or age > 120:
                            age = None
                            birth_date = None
                    except:
                        age = None
                        birth_date = None
                
                if age is None or birth_date is None:
                    age = generate_random_age()
                    birth_date = generate_birthdate_from_age(age)
                
                patient = {
                    'id': patient_id,
                    'name': full_name,
                    'gender': gender,
                    'age': age,
                    'birth_date': birth_date
                }
                patients.append(patient)
            
            return patients[:limit]
        else:
            return None
            
    except Exception as e:
        print(f"Error: {e}")
        return None

def generate_synthetic_patients(num_patients: int = 50):
    first_names = ["Franklin", "Mary", "Peter", "Patricia", "Robert", "Jennifer", 
                   "Michael", "Linda", "William", "Lara", "David", "Barbara"]
    
    last_names = ["Smith", "Clinton", "Holden", "Parker", "Jackson", "Gordon", 
                  "Davis", "Rodriguez", "Lopez", "Gonzalez", "Robertson"]
    
    genders = ["male", "female", "other"]
    
    patients = []
    for i in range(num_patients):
        age = generate_random_age()
        first_name = random.choice(first_names)
        last_name = random.choice(last_names)
        name = f"{first_name} {last_name}"
        birth_date = generate_birthdate_from_age(age)
        
        patient = {
            'id': f"SYN-{str(i+1).zfill(4)}",
            'name': name,
            'gender': random.choice(genders),
            'age': age,
            'birth_date': birth_date
        }
        patients.append(patient)
    
    return patients

def generate_timeline_data(patients):
    timeline_data = []
    for patient in patients:
        timeline = {
            'patient_id': patient['id'],
            'patient_name': patient['name'],
            'los_days': random.choice([2.5, 3.0, 3.5, 4.5, 5.0, 6.0, 7.0, 9.0]),
            'readmission': random.choice(['Yes', 'No', 'No', 'No']),
            'deceased': random.random() < 0.1
        }
        timeline_data.append(timeline)
    return pd.DataFrame(timeline_data)

def generate_report(patients, timeline_df):
    report_id = str(uuid.uuid4())[:8]
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    patients_df = pd.DataFrame(patients)
    
    total_patients = len(patients_df)
    avg_age = patients_df['age'].mean() if total_patients > 0 else 0
    male_count = len(patients_df[patients_df['gender'] == 'male'])
    female_count = len(patients_df[patients_df['gender'] == 'female'])
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Patient Report - {timestamp}</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; background: #f0f0f0; }}
            .container {{ max-width: 1200px; margin: auto; background: white; padding: 20px; }}
            .header {{ background: #667eea; color: white; padding: 20px; text-align: center; }}
            .stats {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; margin: 20px 0; }}
            .stat-card {{ background: #f8f9fa; padding: 15px; text-align: center; border-left: 4px solid #667eea; }}
            .stat-value {{ font-size: 28px; font-weight: bold; color: #667eea; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
            th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }}
            th {{ background: #667eea; color: white; }}
            .footer {{ margin-top: 30px; text-align: center; color: #666; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🏥 Patient Report</h1>
                <p>Generated: {timestamp}</p>
                <p>Report ID: {report_id}</p>
            </div>
            
            <div class="stats">
                <div class="stat-card">
                    <div class="stat-value">{total_patients}</div>
                    <div>Total Patients</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{avg_age:.1f}</div>
                    <div>Average Age</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{male_count}</div>
                    <div>Male</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{female_count}</div>
                    <div>Female</div>
                </div>
            </div>
            
            <h2>Patient Data</h2>
            {patients_df[['id', 'name', 'gender', 'age', 'birth_date']].head(50).to_html(index=False)}
            
            <h2>Timeline Data</h2>
            {timeline_df[['patient_name', 'los_days', 'readmission', 'deceased']].head(50).to_html(index=False)}
            
            <div class="footer">
                <p>Generated by FHIR Patient Report System</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    report_filename = f"report_{report_id}.html"
    report_path = os.path.join(REPORTS_DIR, report_filename)
    
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    return report_path, report_filename

# Flask Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/patients')
def patients():
    return render_template('patients.html')

# Add a route to serve static files explicitly (optional, for debugging)
@app.route('/static/<path:filename>')
def serve_static(filename):
    """Serve static files - this helps with debugging"""
    return send_from_directory(app.static_folder, filename)

@app.route('/api/patients', methods=['GET'])
def get_patients():
    limit = request.args.get('limit', 50, type=int)
    gender_filter = request.args.get('gender', 'all')
    age_min = request.args.get('age_min', 0, type=int)
    age_max = request.args.get('age_max', 120, type=int)
    search_term = request.args.get('search', '')
    
    patients = None
    servers = [HAPI_FHIR, SMART_FHIR, OPENMRS, CMS_FHIR]
    
    for server in servers:
        patients = fetch_fhir_patients(server, limit=limit)
        if patients:
            session['data_source'] = f"FHIR Server: {server}"
            break
    
    if not patients:
        patients = generate_synthetic_patients(limit)
        session['data_source'] = "Synthetic Data"
    
    filtered_patients = []
    for patient in patients:
        if gender_filter != 'all' and patient['gender'] != gender_filter:
            continue
        if patient['age'] < age_min or patient['age'] > age_max:
            continue
        if search_term and search_term.lower() not in patient['name'].lower():
            continue
        filtered_patients.append(patient)
    
    session['current_patients'] = filtered_patients
    
    return jsonify({
        'patients': filtered_patients,
        'total': len(filtered_patients),
        'source': session.get('data_source', 'Unknown')
    })

@app.route('/api/export', methods=['POST'])
def export_report():
    patients = session.get('current_patients', [])
    if not patients:
        return jsonify({'error': 'No patients to export'}), 400
    
    timeline_df = generate_timeline_data(patients)
    report_path, report_filename = generate_report(patients, timeline_df)
    
    return jsonify({
        'success': True,
        'report_url': f'/api/download_report?path={report_path}',
        'message': 'Report created successfully'
    })

@app.route('/api/download_report', methods=['GET'])
def download_report():
    report_path = request.args.get('path', '')
    if not report_path or not os.path.exists(report_path):
        return jsonify({'error': 'Report not found'}), 404
    
    return send_file(report_path, as_attachment=True, download_name=os.path.basename(report_path))

# Vercel handler
def handler(request, context):
    return app(request.environ, context)

if __name__ == '__main__':
    app.run(debug=True, port=5000)