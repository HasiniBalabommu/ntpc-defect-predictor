import pickle
import os
from fuzzywuzzy import process

# Get the correct path regardless of where you run from
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_DIR = os.path.join(BASE_DIR, 'model')

# Load label encoders
label_encoders = pickle.load(open(os.path.join(MODEL_DIR, 'label_encoders.pkl'), 'rb'))
equipment_names = list(label_encoders['equipment'].classes_)

def find_equipment(user_input):
    # Clean user input
    user_input = user_input.strip().upper()
    
    # Find closest match
    best_match, score = process.extractOne(user_input, equipment_names)
    
    # If score is above 60 → good match
    if score >= 60:
        return best_match, score
    else:
        return None, score

# Test it
if __name__ == "__main__":
    name, score = find_equipment("cooling tower 7b")
    print(f"Match : {name}")
    print(f"Score : {score}%")