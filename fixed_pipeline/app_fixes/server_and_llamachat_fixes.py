"""
server_and_llamachat_fixes.py

Two pieces to paste into your app:

1. NEW /api/chat route for server.py (replaces the old one) -- routes by
   intent instead of blindly fuzzy-matching the whole sentence.
2. NEW system_prompt for llama_chat.py -- explicitly branches on what kind
   of context block (if any) was provided, and forbids inventing
   equipment/risk/dates when none was.

This directly targets the three failure modes found during evaluation:
  - comparison/ranking questions getting pinned to one arbitrary equipment
  - history questions getting answered with fabricated defect counts/records
  - generic questions getting a fully-invented Equipment/Risk/Date block
"""

# ============================================================
# 1. server.py -- replace the existing /api/chat route with this
# ============================================================
SERVER_PY_CHAT_ROUTE = '''
from query_router import classify_intent, extract_equipment, extract_top_n, extract_zone_filter
from predictor import predict_defect, predict_all_equipment, predict_top_n, get_history

@app.route('/api/chat', methods=['POST'])
def chat():
    if 'email' not in session:
        return jsonify({'error': 'Not logged in'}), 401

    user_message = request.json.get('message', '')
    context_block = None

    equipment_names = list(label_encoders['equipment'].classes_)
    intent = classify_intent(user_message)

    if intent == "comparison":
        n = extract_top_n(user_message, default_n=5)
        zone = extract_zone_filter(user_message)
        top = predict_top_n(n=n, zone_filter=zone)
        if top:
            lines = [f"{r['equipment']} | {r['risk']} | {r['predicted_date']}" for r in top]
            context_block = (
                f"Equipment Risk Table (top {len(top)}"
                f"{' in ' + zone if zone else ''}, this is the COMPLETE and ONLY "
                f"data available -- do not add, remove, or invent equipment):\\n"
                + "\\n".join(lines)
            )
        else:
            context_block = "NO_DATA: No equipment matched the requested filter."

    elif intent == "history":
        equipment_name, score = extract_equipment(user_message, equipment_names)
        if equipment_name:
            history = get_history(equipment_name, n=5)
            if history is None:
                context_block = f"NO_DATA: Notification history is not tracked in this system for {equipment_name}."
            elif len(history) == 0:
                context_block = f"Notification History for {equipment_name}: no past records found."
            else:
                context_block = (
                    f"Notification History for {equipment_name} "
                    f"(most recent {len(history)} records, this is the COMPLETE list -- "
                    f"do not invent additional records):\\n" + "\\n".join(history)
                )
        else:
            context_block = "NO_DATA: No specific equipment could be identified in this question."

    else:  # maybe_single_equipment
        equipment_name, score = extract_equipment(user_message, equipment_names)
        if equipment_name:
            result, error = predict_defect(equipment_name)
            if result:
                context_block = (
                    f"ML Model Prediction Result:\\n"
                    f"Equipment    : {result['equipment']}\\n"
                    f"Risk Level   : {result['risk']}\\n"
                    f"Days to next : {result['avg_days']} days\\n"
                    f"Expected date: {result['predicted_date']}"
                )
        else:
            context_block = "NO_DATA: No specific equipment could be identified in this question."

    reply = chat_with_llama(user_message, context_block)
    return jsonify({'reply': reply})
'''

# ============================================================
# 2. llama_chat.py -- replace the existing system_prompt with this
# ============================================================
NEW_SYSTEM_PROMPT = '''You are an intelligent assistant for NTPC Korba Power Plant maintenance team.
You will be given one of four kinds of context along with the question. Follow the matching rule exactly.

1. If given "ML Model Prediction Result": report ONLY that equipment/risk/date, in this format:
Equipment: [name]
Risk Level: [HIGH/MEDIUM/LOW]
Expected Failure: [date]
Days Remaining: [days]
Then one line of recommended action, then one follow-up question.

2. If given "Equipment Risk Table": summarize ONLY the equipment listed in that table, in the
order given. Do not add, remove, reorder based on assumptions, or invent any equipment not listed.

3. If given "Notification History": summarize ONLY the records listed. If it says no past
records were found, say that plainly. Never invent a defect count, date, or record that
was not explicitly given to you.

4. If given anything starting with "NO_DATA:": you do NOT have equipment-specific data for
this question. State plainly that you don't have specific data available, then give only
general maintenance best-practice advice. Do NOT invent an equipment name, risk level,
expected failure date, or days-remaining number under any circumstance in this case.

Keep responses short, professional and data-focused. Never ask the engineer what they are
doing or planning -- only offer to show more data or records.'''
