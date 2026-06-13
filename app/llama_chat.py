import ollama
import os

# Conversation history — stores the full chat
# This is how Llama remembers previous messages
conversation_history = []

def chat_with_llama(user_message, prediction_result=None):
    
    # System prompt — tells Llama how to behave
    system_prompt = """You are an intelligent assistant for NTPC Korba Power Plant maintenance team.
When given a prediction result, respond in this exact format:

Equipment: [name]
Risk Level: [HIGH/MEDIUM/LOW]
Expected Failure: [date]
Days Remaining: [days]

Then in 1 line mention the recommended action.
Then ask ONE follow up question from these options based on context:
- Would you like to see the defect history for this equipment?
- Would you like to check other equipment in the same area?
- Would you like to add a new maintenance record for this equipment?
- Would you like to see all HIGH risk equipment right now?

Keep responses short, professional and data focused.
Never ask the engineer what they are doing or planning.
Only offer to show more data or records."""

    # Add prediction result to message if available
    if prediction_result:
        user_message = f"{user_message}\n\nPrediction Result: {prediction_result}"

    # Add user message to history
    conversation_history.append({
        "role": "user",
        "content": user_message
    })

    # Call Llama with full conversation history
    response = ollama.chat(
        model='llama3.2:1b',
        messages=[{"role": "system", "content": system_prompt}] + conversation_history
    )

    # Get reply
    reply = response['message']['content']

    # Add reply to history
    conversation_history.append({
        "role": "assistant",
        "content": reply
    })

    return reply

def clear_history():
    # Clear conversation history
    global conversation_history
    conversation_history = []

# Test it
if __name__ == "__main__":
    print("Testing Llama connection...")
    reply = chat_with_llama("Hello! Can you introduce yourself?")
    print("Llama says:", reply)