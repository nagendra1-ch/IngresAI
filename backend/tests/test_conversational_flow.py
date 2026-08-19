import requests
import json
import sys

base_url = "http://127.0.0.1:8000"

def run_tests():
    print("Testing registration and login flow...")
    email = "conv_test@example.com"
    password = "Password123!"
    
    # 1. Register user
    reg_url = f"{base_url}/api/auth/register"
    reg_data = {
        "email": email,
        "username": "conv_tester",
        "password": password,
        "name": "ConvTester",
        "confirm_password": password
    }
    
    try:
        r_reg = requests.post(reg_url, json=reg_data)
        if r_reg.status_code not in (200, 201, 400):
            print(f"Registration failed: {r_reg.status_code} {r_reg.text}")
            sys.exit(1)
    except Exception as e:
        print(f"Failed to connect to backend: {e}")
        sys.exit(1)

    # 2. Login
    login_url = f"{base_url}/api/auth/login"
    login_data = {
        "email": email,
        "password": password
    }
    r_login = requests.post(login_url, json=login_data)
    if r_login.status_code != 200:
        print(f"Login failed: {r_login.status_code} {r_login.text}")
        sys.exit(1)
        
    token = r_login.json()["access_token"]
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    print("Logged in successfully. Obtained access token.")

    # --- TEST 1: AMBIGUOUS QUESTION ---
    print("\n--- TEST 1: Asking ambiguous question 'What is the groundwater level in Ananthapuramu?' ---")
    chat_url = f"{base_url}/api/ai/chat"
    payload = {
        "query": "What is the groundwater level in Ananthapuramu?"
    }
    r_chat = requests.post(chat_url, json=payload, headers=headers)
    print("chat_res status:", r_chat.status_code)
    print("chat_res body:", r_chat.text)
    assert r_chat.status_code == 200, f"Chat call failed: {r_chat.text}"
    
    chat_res = r_chat.json()
    conv_id = chat_res["conversation_id"]
    print("Conversation ID created:", conv_id)
    print("Response text:", chat_res["response"])
    assert "multiple locations" in chat_res["response"].lower(), "Expected clarification question for duplicate name!"
    
    # --- TEST 2: CLARIFICATION RESPONSE ---
    print("\n--- TEST 2: Responding to clarification: 'Ananthapuramu in Andhra Pradesh' ---")
    payload2 = {
        "query": "Ananthapuramu in Andhra Pradesh",
        "conversation_id": conv_id
    }
    r_chat2 = requests.post(chat_url, json=payload2, headers=headers)
    assert r_chat2.status_code == 200, f"Clarification call failed: {r_chat2.text}"
    
    chat_res2 = r_chat2.json()
    print("Factual Response:")
    print(chat_res2["response"])
    assert chat_res2["location"]["district"] == "Ananthapuramu", "Expected resolved location in context!"
    assert chat_res2["location"]["state"] == "Andhra Pradesh", "Expected resolved state in context!"
    assert "Annual Extractable Groundwater Resource" in chat_res2["response"], "Expected factual template layout!"
    assert "34.90%" in chat_res2["response"], "Expected Ananthapuramu stage percentage matched exactly!"

    # --- TEST 3: CONTEXT CARRYOVER / FOLLOW-UP ---
    print("\n--- TEST 3: Follow-up question: 'What about rainfall?' ---")
    payload3 = {
        "query": "What about rainfall?",
        "conversation_id": conv_id
    }
    r_chat3 = requests.post(chat_url, json=payload3, headers=headers)
    assert r_chat3.status_code == 200, f"Follow-up call failed: {r_chat3.text}"
    
    chat_res3 = r_chat3.json()
    print("Factual Response:")
    print(chat_res3["response"])
    assert chat_res3["location"]["district"] == "Ananthapuramu", "Expected location context carried over!"
    assert "Annual Rainfall" in chat_res3["response"], "Expected rainfall section!"

    # --- TEST 4: CONTEXT SWITCHING ---
    print("\n--- TEST 4: Context switch: 'What about Kadapa?' ---")
    payload4 = {
        "query": "What about Kadapa?",
        "conversation_id": conv_id
    }
    r_chat4 = requests.post(chat_url, json=payload4, headers=headers)
    assert r_chat4.status_code == 200, f"Context switch call failed: {r_chat4.text}"
    
    chat_res4 = r_chat4.json()
    print("Factual Response:")
    print(chat_res4["response"])
    assert chat_res4["location"]["district"] == "YSR Kadapa", "Expected location context updated to Kadapa alias!"

    # --- TEST 5: FOLLOW-UP ON KADAPA ---
    print("\n--- TEST 5: Follow-up on Kadapa: 'What about extraction?' ---")
    payload5 = {
        "query": "What about extraction?",
        "conversation_id": conv_id
    }
    r_chat5 = requests.post(chat_url, json=payload5, headers=headers)
    assert r_chat5.status_code == 200, f"Follow-up call failed: {r_chat5.text}"
    
    chat_res5 = r_chat5.json()
    print("Factual Response:")
    print(chat_res5["response"])
    assert chat_res5["location"]["district"] == "YSR Kadapa", "Expected location context preserved as Kadapa!"
    assert "Annual Groundwater Extraction" in chat_res5["response"], "Expected extraction parameters!"

    print("\nCONVERSATIONAL CONTEXT FLOW AND GEMINI BYPASS TESTS SUCCESSFUL!")

if __name__ == "__main__":
    run_tests()
