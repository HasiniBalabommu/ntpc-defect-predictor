import pandas as pd
import pickle
import sqlite3
import os
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
from datetime import datetime

# Paths
BASE_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_DIR  = os.path.join(BASE_DIR, 'model')
DATA_DIR   = os.path.join(BASE_DIR, 'data')
DB_PATH    = os.path.join(BASE_DIR, 'database', 'ntpc_records.db')
CSV_PATH   = os.path.join(DATA_DIR, 'clean_ntpc_data.csv')
MODEL_PATH = os.path.join(MODEL_DIR, 'model.pkl')
LOG_PATH   = os.path.join(BASE_DIR, 'scripts', 'retrain_log.txt')

def log(message):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line      = f"[{timestamp}] {message}"
    print(line)
    with open(LOG_PATH, 'a') as f:
        f.write(line + '\n')

def get_risk(days):
    if days <= 30:
        return 'HIGH'
    elif days <= 90:
        return 'MEDIUM'
    else:
        return 'LOW'

def retrain():
    log("Starting model retraining...")

    try:
        # Load original clean data
        df = pd.read_csv(CSV_PATH)
        log(f"Loaded original data: {df.shape[0]} rows")

        # Load new records from database
        conn = sqlite3.connect(DB_PATH)
        c    = conn.cursor()

        try:
            c.execute("SELECT * FROM new_records")
            new_rows = c.fetchall()
            log(f"New records found: {len(new_rows)}")
        except:
            new_rows = []
            log("No new records table found")

        conn.close()

        # Load label encoders
        label_encoders = pickle.load(open(os.path.join(MODEL_DIR, 'label_encoders.pkl'), 'rb'))
        feature_cols   = pickle.load(open(os.path.join(MODEL_DIR, 'feature_columns.pkl'), 'rb'))

        # Process new records and add to dataframe
        if new_rows:
            new_data = []
            for row in new_rows:
                try:
                    # row = (id, equipment, notif_date, notif_time, priority,
                    #        notif_type, functional_loc, completion_date,
                    #        completion_time, description, added_by, added_on)

                    equipment = row[1].strip().upper()
                    priority  = row[4]
                    notif_type= row[5]
                    notif_date= pd.to_datetime(row[2])
                    comp_date = pd.to_datetime(row[7])

                    # Skip if equipment not in encoder
                    if equipment not in label_encoders['equipment'].classes_:
                        log(f"Skipping unknown equipment: {equipment}")
                        continue

                    # Encode
                    eq_code   = label_encoders['equipment'].transform([equipment])[0]
                    pri_code  = label_encoders['Priority'].transform([priority])[0]
                    not_code  = label_encoders['Notifictn type'].transform([notif_type])[0]

                    # Extract time features
                    hour      = pd.to_datetime(row[3], format='%H:%M').hour
                    shift     = 'Morning' if 6 <= hour <= 13 else ('Afternoon' if 14 <= hour <= 21 else 'Night')
                    shift_code= label_encoders['shift'].transform([shift])[0]

                    # Calculate resolution days
                    res_days  = (comp_date - notif_date).days
                    if res_days < 0:
                        res_days = 0

                    new_data.append({
                        'equipment'         : eq_code,
                        'Functional Loc.'   : 0,
                        'Priority'          : pri_code,
                        'Notifictn type'    : not_code,
                        'month'             : notif_date.month,
                        'day_of_week'       : notif_date.dayofweek,
                        'hour'              : hour,
                        'shift'             : shift_code,
                        'year'              : notif_date.year,
                        'days_to_next_defect': res_days if res_days > 0 else 30
                    })

                except Exception as e:
                    log(f"Error processing row: {e}")
                    continue

            if new_data:
                df_new = pd.DataFrame(new_data)
                df     = pd.concat([df, df_new], ignore_index=True)
                log(f"Added {len(new_data)} new records to training data")

        # Prepare features and target
        x = df[feature_cols]
        y = df['days_to_next_defect'].apply(get_risk)

        # Train model
        x_train, x_test, y_train, y_test = train_test_split(
            x, y, test_size=0.2, random_state=42
        )

        model = RandomForestClassifier(n_estimators=100, random_state=42)
        model.fit(x_train, y_train)

        # Check accuracy
        predictions = model.predict(x_test)
        accuracy    = accuracy_score(y_test, predictions) * 100
        log(f"New model accuracy: {round(accuracy, 2)}%")

        # Save new model
        pickle.dump(model, open(MODEL_PATH, 'wb'))
        log("New model saved successfully!")

        # Update last trained date in database
        conn = sqlite3.connect(DB_PATH)
        c    = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS training_log (
                id           INTEGER PRIMARY KEY,
                trained_on   TEXT,
                records_used INTEGER,
                accuracy     REAL
            )
        ''')
        c.execute(
            "INSERT INTO training_log VALUES (NULL, ?, ?, ?)",
            (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), df.shape[0], accuracy)
        )
        conn.commit()
        conn.close()

        log("Retraining complete!")
        return True, accuracy

    except Exception as e:
        log(f"Retraining failed: {e}")
        return False, 0

if __name__ == "__main__":
    retrain()