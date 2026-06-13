import pickle
import os
import pandas as pd
from datetime import datetime, timedelta

# Get correct paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_DIR = os.path.join(BASE_DIR, 'model')

# Load all saved files
model          = pickle.load(open(os.path.join(MODEL_DIR, 'model.pkl'), 'rb'))
label_encoders = pickle.load(open(os.path.join(MODEL_DIR, 'label_encoders.pkl'), 'rb'))
avg_days       = pickle.load(open(os.path.join(MODEL_DIR, 'avg_days.pkl'), 'rb'))
feature_cols   = pickle.load(open(os.path.join(MODEL_DIR, 'feature_columns.pkl'), 'rb'))

def predict_defect(equipment_name):
    try:
        # Encode equipment name to number
        equipment_encoder = label_encoders['equipment']
        
        # Check if equipment exists
        if equipment_name not in equipment_encoder.classes_:
            return None, "Equipment not found"
        
        equipment_code = equipment_encoder.transform([equipment_name])[0]
        
        # Get current date features
        now = datetime.now()
        
        # Encode other fields with most common values
        priority_code     = label_encoders['Priority'].transform(['Priority A'])[0]
        notif_code        = label_encoders['Notifictn type'].transform(['M2'])[0]
        func_loc_code     = label_encoders['Functional Loc.'].transform(
                            [label_encoders['Functional Loc.'].classes_[0]])[0]
        shift_code        = label_encoders['shift'].transform(['Morning'])[0]

        # Build input for model
        input_data = pd.DataFrame([{
            'equipment'       : equipment_code,
            'Functional Loc.' : func_loc_code,
            'Priority'        : priority_code,
            'Notifictn type'  : notif_code,
            'month'           : now.month,
            'day_of_week'     : now.weekday(),
            'hour'            : now.hour,
            'shift'           : shift_code,
            'year'            : now.year
        }])

        # Predict risk
        risk = model.predict(input_data)[0]

        # Get average days for this equipment and risk
        avg = avg_days.get(equipment_code, {}).get(risk, 30)

        # Calculate predicted date
        predicted_date = now + timedelta(days=int(avg))

        return {
            'equipment'      : equipment_name,
            'risk'           : risk,
            'avg_days'       : int(avg),
            'predicted_date' : predicted_date.strftime('%d %B %Y'),
        }, None

    except Exception as e:
        return None, str(e)

# Test it
if __name__ == "__main__":
    result, error = predict_defect("HEADER COOLING TOWER 7B")
    if error:
        print("Error:", error)
    else:
        print("Equipment    :", result['equipment'])
        print("Risk Level   :", result['risk'])
        print("Avg Days     :", result['avg_days'])
        print("Predicted on :", result['predicted_date'])

def predict_all_equipment():
    """Predict risk for all equipment and return sorted by risk"""
    try:
        results = []
        now     = datetime.now()

        # Get all equipment names
        equipment_list = label_encoders['equipment'].classes_

        for equipment_name in equipment_list:
            try:
                equipment_code    = label_encoders['equipment'].transform([equipment_name])[0]
                priority_code     = label_encoders['Priority'].transform(['Priority A'])[0]
                notif_code        = label_encoders['Notifictn type'].transform(['M2'])[0]
                func_loc_code     = label_encoders['Functional Loc.'].transform(
                                    [label_encoders['Functional Loc.'].classes_[0]])[0]
                shift_code        = label_encoders['shift'].transform(['Morning'])[0]

                input_data = pd.DataFrame([{
                    'equipment'       : equipment_code,
                    'Functional Loc.' : func_loc_code,
                    'Priority'        : priority_code,
                    'Notifictn type'  : notif_code,
                    'month'           : now.month,
                    'day_of_week'     : now.weekday(),
                    'hour'            : now.hour,
                    'shift'           : shift_code,
                    'year'            : now.year
                }])

                risk    = model.predict(input_data)[0]
                avg     = avg_days.get(equipment_code, {}).get(risk, 30)
                pred_dt = now + timedelta(days=int(avg))

                results.append({
                    'equipment'      : equipment_name,
                    'risk'           : risk,
                    'avg_days'       : int(avg),
                    'predicted_date' : pred_dt.strftime('%d %B %Y'),
                    'predicted_month': pred_dt.month,
                    'predicted_year' : pred_dt.year
                })

            except:
                continue

        # Sort by risk priority
        risk_order = {'HIGH': 0, 'MEDIUM': 1, 'LOW': 2}
        results.sort(key=lambda x: (risk_order[x['risk']], x['avg_days']))

        return results

    except Exception as e:
        return []