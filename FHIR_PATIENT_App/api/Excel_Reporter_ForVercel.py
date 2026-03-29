from flask import Flask, render_template, request, jsonify, send_file, session
from flask_cors import CORS
import pandas as pd
import requests
from datetime import datetime
import json
import os
import random
import plotly.graph_objects as go
from pathlib import Path
import uuid
import tempfile

app = Flask(__name__, 
            template_folder='../templates',
            static_folder='../static')
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-change-in-production')
CORS(app)

# Configure for Vercel - use /tmp for temporary files
TEMP_DIR = tempfile.gettempdir()
REPORTS_DIR = os.path.join(TEMP_DIR, 'reports')
os.makedirs(REPORTS_DIR, exist_ok=True)

# FHIR Servers
HAPI_FHIR = "https://hapi.fhir.org/baseR4"
SMART_FHIR = "https://r4.smarthealthit.org"
OPENMRS = "https://openmrs.org/fhir"
CMS_FHIR = "https://sandbox.cms.gov/fhir"

def generate_random_age():
    """Generate a random realistic age"""
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
    """Generate a random birthdate based on age"""
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

def fetch_fhir_patients(fhir_server: str, limit: int = 50, fill_missing_ages: bool = True):
    """Fetch patients from FHIR server"""
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
                
                # Extract name
                if 'name' in resource and resource['name']:
                    name = resource['name'][0]
                    given = ' '.join(name.get('given', []))
                    family = name.get('family', '')
                    full_name = f"{given} {family}".strip()
                else:
                    full_name = "Unknown"
                
                gender = resource.get('gender', 'unknown')
                birth_date = resource.get('birthDate', None)
                
                # Calculate age
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
                
                if fill_missing_ages and (age is None or birth_date is None):
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
        print(f"Error fetching from {fhir_server}: {e}")
        return None

def generate_synthetic_patients(num_patients: int = 50):
    """Generate synthetic patient data"""
    first_names = ["Franklin", "Mary", "Peter", "Patricia", "Robert", "Jennifer", "Michael", "Linda", 
                   "William", "Lara", "David", "Barbara", "Judge", "Susan", "Joseph", "Jessica", "Keanu",
                   "Angela", "Roy", "Maki", "Naruto", "Gon"]
    
    last_names = ["Smith", "Clinton", "Holden", "Parker", "Jackson", "Gordon", "De Santa", "Davis",
                  "Rodriguez", "Croft", "Rabbit", "Lopez", "Gonzalez", "Sue", "Robertson", "Reeves",
                  "Mamoa", "Mustang", "Zenin", "Uzamaki", "Frecess"]
    
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
    """Generate timeline data for patients"""
    timeline_data = []
    for patient in patients:
        timeline = {
            'patient_id': patient['id'],
            'patient_name': patient['name'],
            'admission_time': f"{random.choice([3,8,9,11,14,16,19,22]):02d}:{random.randint(0,59):02d}",
            'los_days': random.choice([2.5, 3.0, 3.5, 4.5, 5.0, 6.0, 7.0, 9.0]),
            'consult_time': f"{random.choice([3,8,9,11,14,16,19,22]):02d}:{random.randint(0,59):02d}",
            'readmission': random.choice(['Yes', 'No', 'No', 'No']),
            'deceased': random.random() < 0.1
        }
        timeline_data.append(timeline)
    return pd.DataFrame(timeline_data)

def create_simple_report(patients, timeline_df, include_graphs=True):
    """Generate simple HTML report for Vercel"""
    report_id = str(uuid.uuid4())[:8]
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    patients_df = pd.DataFrame(patients)
    
    # Simple statistics
    total_patients = len(patients_df)
    avg_age = patients_df['age'].mean() if total_patients > 0 else 0
    male_count = len(patients_df[patients_df['gender'] == 'male'])
    female_count = len(patients_df[patients_df['gender'] == 'female'])
    
    html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Patient Report - {timestamp}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 40px;
            color: #333;
        }}
        .report-container {{
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }}
        .report-header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px;
            text-align: center;
        }}
        .report-header h1 {{ font-size: 32px; margin-bottom: 10px; }}
        .report-header .timestamp {{ opacity: 0.9; font-size: 14px; }}
        .report-content {{ padding: 40px; }}
        .section {{ margin-bottom: 40px; }}
        .section-title {{
            font-size: 24px;
            color: #667eea;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #667eea;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        .stat-card {{
            background: #f8f9fa;
            padding: 20px;
            border-radius: 10px;
            text-align: center;
            border-left: 4px solid #667eea;
        }}
        .stat-value {{ font-size: 32px; font-weight: bold; color: #667eea; }}
        .stat-label {{ color: #666; margin-top: 5px; }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background: #667eea;
            color: white;
            font-weight: 600;
        }}
        tr:hover {{ background: #f5f5f5; }}
        .footer {{
            background: #f8f9fa;
            padding: 20px;
            text-align: center;
            color: #666;
            font-size: 12px;
        }}
        @media print {{
            body {{ background: white; padding: 0; }}
            .report-header {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
        }}
    </style>
</head>
<body>
    <div class="report-container">
        <div class="report-header">
            <h1>🏥 Patient Report</h1>
            <div class="timestamp">Generated: {timestamp}</div>
            <div class="timestamp">Report ID: {report_id}</div>
        </div>
        
        <div class="report-content">
            <div class="section">
                <h2 class="section-title">📊 Key Statistics</h2>
                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="stat-value">{total_patients}</div>
                        <div class="stat-label">Total Patients</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">{avg_age:.1f}</div>
                        <div class="stat-label">Average Age</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">{male_count}</div>
                        <div class="stat-label">Male</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">{female_count}</div>
                        <div class="stat-label">Female</div>
                    </div>
                </div>
            </div>
            
            <div class="section">
                <h2 class="section-title">📋 Patient Data</h2>
                {patients_df[['id', 'name', 'gender', 'age', 'birth_date']].head(50).to_html(classes='data-table', index=False)}
            </div>
            
            <div class="section">
                <h2 class="section-title">⏱️ Timeline Data</h2>
                {timeline_df[['patient_name', 'los_days', 'readmission', 'deceased']].head(50).to_html(classes='data-table', index=False)}
            </div>
        </div>
        
        <div class="footer">
            <p>Generated by FHIR Patient Report System | Data source: {'FHIR Servers' if len(patients) <= 50 else 'Synthetic Data'}</p>
            <p>© 2025 - Confidential Medical Data</p>
        </div>
    </div>
</body>
</html>
    """
    
    # Save to temp directory
    report_filename = f"report_{report_id}_{timestamp.replace(' ', '_').replace(':', '-')}.html"
    report_path = os.path.join(REPORTS_DIR, report_filename)
    
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    return report_path, report_filename

# Flask Routes
@app.route('/')
def index():
    """Landing page"""
    return render_template('index.html')

@app.route('/login')
def login():
    """Login page"""
    return render_template('login.html')

@app.route('/patients')
def patients():
    """Patients page"""
    return render_template('patients.html')

@app.route('/api/patients', methods=['GET'])
def get_patients():
    """API endpoint to get patients"""
    limit = request.args.get('limit', 50, type=int)
    gender_filter = request.args.get('gender', 'all')
    age_min = request.args.get('age_min', 0, type=int)
    age_max = request.args.get('age_max', 120, type=int)
    search_term = request.args.get('search', '')
    
    # Try to fetch from FHIR servers
    patients = None
    servers = [HAPI_FHIR, SMART_FHIR, OPENMRS, CMS_FHIR]
    
    for server in servers:
        patients = fetch_fhir_patients(server, limit=limit)
        if patients:
            session['data_source'] = f"FHIR Server: {server}"
            break
    
    # Fallback to synthetic data
    if not patients:
        patients = generate_synthetic_patients(limit)
        session['data_source'] = "Synthetic Data"
    
    # Apply filters
    filtered_patients = []
    for patient in patients:
        if gender_filter != 'all' and patient['gender'] != gender_filter:
            continue
        if patient['age'] < age_min or patient['age'] > age_max:
            continue
        if search_term and search_term.lower() not in patient['name'].lower():
            continue
        filtered_patients.append(patient)
    
    # Store in session for export
    session['current_patients'] = filtered_patients
    
    return jsonify({
        'patients': filtered_patients,
        'total': len(filtered_patients),
        'source': session.get('data_source', 'Unknown')
    })

@app.route('/api/export', methods=['POST'])
def export_report():
    """Export report endpoint"""
    data = request.json
    include_graphs = data.get('include_graphs', True)
    
    patients = session.get('current_patients', [])
    if not patients:
        return jsonify({'error': 'No patients to export'}), 400
    
    # Generate timeline data
    timeline_df = generate_timeline_data(patients)
    
    # Generate report
    report_path, report_filename = generate_simple_report(patients, timeline_df, include_graphs)
    
    return jsonify({
        'success': True,
        'report_url': f'/api/download_report?path={report_path}',
        'message': 'Report created successfully'
    })

@app.route('/api/download_report', methods=['GET'])
def download_report():
    """Download report endpoint"""
    report_path = request.args.get('path', '')
    if not report_path or not os.path.exists(report_path):
        return jsonify({'error': 'Report not found'}), 404
    
    return send_file(report_path, as_attachment=True, download_name=os.path.basename(report_path))

# Vercel handler
def handler(request, context):
    """Vercel serverless function handler"""
    return app(request.environ, context)

# For local development
if __name__ == '__main__':
    app.run(debug=True, port=5000)