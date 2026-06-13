# NTPC Korba Defect Prediction System

An AI-powered predictive maintenance system built for **NTPC Korba Power Station**.
The system predicts equipment failures using Machine Learning and provides a 
conversational AI interface powered by Llama 3.

---

## 📋 Table of Contents
- [Overview]
- [Features]
- [Tech Stack]
- [Project Structure]
- [Installation]
- [How to Run]
- [Default Credentials]
- [How It Works]
- [Model Details]
- [Future Improvements]

---

## Overview

NTPC Korba Power Station generates maintenance notifications for equipment 
defects through SAP Plant Maintenance (PM) module. This system analyzes 
**8943 historical defect records** from 2014 to 2026 to predict:

- When will the next defect occur for any equipment
- Risk level of the equipment (HIGH / MEDIUM / LOW)
- Expected failure date
- Days remaining before next defect

The system features a **ChatGPT-like conversational interface** where engineers 
can ask questions in plain English and get intelligent responses powered by 
Llama 3 running completely offline.

---

## ✨ Features

### 🔐 Security
- Role based authentication (Admin / Viewer)
- Company email domain validation (@ntpckorbaint.com)
- SHA256 password hashing
- Session management

### 🤖 AI Chat Interface
- Conversational AI powered by Llama 3 (runs locally, no internet needed)
- Understands natural language queries
- Fuzzy equipment name matching
- Remembers conversation context

### 📊 ML Predictions
- Random Forest Classifier
- Predicts HIGH / MEDIUM / LOW risk
- Shows expected failure date
- Trained on 6846 cleaned records

### 👤 Admin Features
- Add new defect records
- Edit and delete recent records
- Model retrains automatically on every new record
- View training status and history
- Nightly Excel sync automation

### 👁 Viewer Features
- Query equipment predictions
- View defect history
- Chat interface access

---

## 🛠 Tech Stack

1. ML Model -  Random Forest (scikit-learn) 
2. AI Chat  -  Llama 3.2 1B via Ollama 
3. Conversation Memory  -  LangChain 
4. Backend  - Flask (Python) 
5. Database -  SQLite 
6. Frontend - HTML + CSS + JavaScript 
7. Fuzzy Matching -  FuzzyWuzzy |
8. Data Processing -  Pandas, NumPy 

---

## 📁 Project Structure

```
ntpc_defect_predictor/
│
├── 📁 notebooks/
│   ├── STEP_1_EDA.ipynb          ← Data exploration and visualization
│   ├── STEP2_CLEANING.ipynb      ← Data cleaning and preprocessing
│   └── STEP_3_MODEL.ipynb        ← Model training and evaluation
│
├── 📁 data/
│   ├── korba_defects.xlsx        ← Raw SAP PM data (confidential)
│   └── clean_ntpc_data.csv       ← Cleaned training data
│
├── 📁 model/
│   ├── model.pkl                 ← Trained Random Forest model
│   ├── label_encoders.pkl        ← Column encoders
│   ├── avg_days.pkl              ← Average days per equipment per risk
│   └── feature_columns.pkl       ← Training feature list
│
├── 📁 database/
│   └── ntpc_records.db           ← SQLite database (users + records)
│
├── 📁 scripts/
│   ├── retrain.py                ← Model retraining script
│   ├── excel_to_db.py            ← Nightly Excel sync script
│   ├── retrain_log.txt           ← Auto created on first retrain
│   └── sync_log.txt              ← Auto created on first sync
│
├── 📁 app/
│   ├── server.py                 ← Flask backend + API routes
│   ├── predictor.py              ← ML model prediction logic
│   ├── llama_chat.py             ← Llama 3 conversation logic
│   ├── fuzzy_match.py            ← Equipment name fuzzy matching
│   ├── index.html                ← Login page
│   ├── chat.html                 ← Chat interface
│   ├── add_record.html           ← Add defect record page
│   ├── style.css                 ← NTPC themed styles
│   ├── auth.js                   ← Login/logout logic
│   ├── chat.js                   ← Chat interface logic
│   └── add_record.js             ← Record management logic
│
├── requirements.txt              ← Python dependencies
└── README.md                     ← This file
```

---

## ⚙️ Installation

### Prerequisites
- Python 3.10+
- Ollama installed (download from https://ollama.com)
- 8GB+ RAM r

### Step 1 — Clone or Download Project
```bash
cd C:/Users/yourname/Downloads
# Place ntpc_defect_predictor folder here
```

### Step 2 — Install Python Libraries
```bash
cd ntpc_defect_predictor
pip install -r requirements.txt
```

### Step 3 — Download Llama 3 Model
```bash
ollama pull llama3.2:1b
```
This is a one time download of approximately 1.3GB.

### Step 4 — Setup Nightly Excel Sync (Optional)
```bash
schtasks /create /tn "NTPC Excel Sync" /tr "python C:\Users\yourname\Downloads\ntpc_defect_predictor\scripts\excel_to_db.py" /sc daily /st 00:00
```

---

## 🚀 How to Run

### Step 1 — Start Ollama
Open Command Prompt and run:
```bash
ollama run llama3.2:1b
```
Keep this running in the background.

### Step 2 — Start Flask Server
Open a new terminal:
```bash
cd ntpc_defect_predictor/app
python server.py
```

### Step 3 — Open in Browser
```
http://127.0.0.1:5000
```

---

## 🔑 Default Credentials

### Admin Login
```
Email    : admin@ntpckorbaint.com
Password : Admin@123
Access   : Full (predictions + record management + retraining)
```

### Viewer Login
```
Email    : viewer@ntpckorbaint.com
Password : Viewer@123
Access   : Limited (predictions + chat only)
```

> Credentials can be changed during the time of deployment

---

## 🔄 How It Works

### Prediction Flow
```
User asks: "When will cooling tower 7B fail next?"
        ↓
Fuzzy matching finds: HEADER COOLING TOWER 7B (95% match)
        ↓
ML model predicts: HIGH risk, 30 days
        ↓
Llama 3 formats response conversationally
        ↓
User sees: Equipment details + Risk level + Expected date
```

### Learning Flow
```
Admin adds new defect record
        ↓
Saved to SQLite database
        ↓
retrain.py runs automatically
        ↓
New record added to training data
        ↓
Random Forest model retrains
        ↓
model.pkl updated
        ↓
Next prediction uses updated model
```

### Nightly Excel Sync
```
Engineer updates korba_defects.xlsx
        ↓
Every night at 12:00 AM
        ↓
excel_to_db.py reads new rows
        ↓
New rows added to database
        ↓
Model retrains automatically
```

---

## 📊 Model Details

 Parameter  Value 

1. Algorithm - Random Forest Classifier 
2. Training Records - 6846 
3. Features Used - 9 
4. Target - Risk Level (HIGH/MEDIUM/LOW) 
5. Current Accuracy - ~50% (baseline) 
6. Date Range - 2014 - 2026 
7. Equipment Count - 447 unique 

### Features Used for Training
```
1. equipment         → encoded equipment ID
2. Functional Loc.   → encoded location
3. Priority          → defect priority level
4. Notifictn type    → notification category
5. month             → month of notification
6. day_of_week       → day of week
7. hour              → hour of notification
8. shift             → Morning/Afternoon/Night
9. year              → year of notification
```

### Why 50% Accuracy?
The current accuracy is a baseline built on available data.
Accuracy will improve significantly with:
- More historical records
- Equipment age data
- Sensor readings (vibration, temperature)
- Load/usage data

---

## 🔮 Future Improvements

```
1. Equipment age as training feature
   → Older equipment fails more frequently

2. Vibration/temperature sensor data
   → Most powerful predictor of imminent failure

3. Separate model per equipment type
   → Each equipment learns its own failure pattern

4. Mobile responsive UI
   → Engineers can query from mobile on plant floor

5. Email/SMS alerts
   → Automatic alerts when HIGH risk detected

6. Dashboard with charts
   → Visual overview of all equipment risk levels

7. Integration with SAP PM
   → Direct sync without Excel intermediate
```

---

## 👨‍💻 Development

Built as an internship project for **NTPC Korba Power Station**.

```
Data Source   : SAP Plant Maintenance (PM) Module
Records       : 8943 notifications (2014-2026)
Plant         : NTPC Korba, Chhattisgarh
Equipment     : 447 unique equipment
```

---

## ⚠️ Important Notes

```
1. Keep korba_defects.xlsx in data/ folder always
   Moving it will break the nightly sync

2. Keep Ollama running before starting server
   Chat will not work without Ollama

3. model.pkl is 30MB — do not delete it
   Deleting requires full retraining

4. database/ntpc_records.db contains user credentials
   Keep it secure and never share publicly

5. Change default passwords before production deployment
```

---

*© 2024 NTPC Korba Power Station. All rights reserved.*
