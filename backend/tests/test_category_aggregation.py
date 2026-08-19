import requests
import sys

base_url = "http://127.0.0.1:8000"

def run_tests():
    print("Testing category aggregation flow...")
    email = "agg_test@example.com"
    password = "Password123!"
    
    # 1. Register user
    reg_url = f"{base_url}/api/auth/register"
    reg_data = {
        "email": email,
        "username": "agg_tester",
        "password": password,
        "name": "AggTester",
        "confirm_password": password
    }
    
    requests.post(reg_url, json=reg_data)

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

    # --- TEST 1: How many states are critical ---
    print("\n--- TEST 1: How many states are critical? (Exclude UTs) ---")
    chat_url = f"{base_url}/api/ai/chat"
    payload1 = {
        "query": "How many states are in critical zone?"
    }
    r_chat1 = requests.post(chat_url, json=payload1, headers=headers)
    assert r_chat1.status_code == 200, f"Call failed: {r_chat1.text}"
    
    res1 = r_chat1.json()
    conv_id = res1["conversation_id"]
    print("States with Critical category units (excluding UTs):")
    print(res1["response"])
    assert "**States with at least one Critical assessment unit:** 9" in res1["response"], "Expected count of 9 states (excluding Delhi UT)!"
    assert "Uttar Pradesh" in res1["response"]
    assert "Andhra Pradesh" in res1["response"]
    assert "Delhi" not in res1["response"], "Expected Delhi UT to be excluded!"

    # --- TEST 2: How many states and Union Territories are critical ---
    print("\n--- TEST 2: How many states and Union Territories are critical? ---")
    payload2 = {
        "query": "How many states and Union Territories are critical?",
        "conversation_id": conv_id
    }
    r_chat2 = requests.post(chat_url, json=payload2, headers=headers)
    assert r_chat2.status_code == 200, f"Call failed: {r_chat2.text}"
    
    res2 = r_chat2.json()
    print("States and UTs with Critical category units:")
    print(res2["response"])
    assert "**States and Union Territories with at least one Critical assessment unit:** 10" in res2["response"], "Expected count of 10 including Delhi UT!"
    assert "Delhi" in res2["response"], "Expected Delhi UT to be listed!"

    # --- TEST 3: Follow-up category carryover ---
    print("\n--- TEST 3: Follow-up: 'What about semi-critical?' ---")
    payload3 = {
        "query": "What about semi-critical?",
        "conversation_id": conv_id
    }
    r_chat3 = requests.post(chat_url, json=payload3, headers=headers)
    assert r_chat3.status_code == 200, f"Call failed: {r_chat3.text}"
    
    res3 = r_chat3.json()
    print("States with Semi-Critical category units:")
    print(res3["response"])
    assert "Semi-Critical" in res3["response"]
    assert "at least one Semi-Critical assessment unit" in res3["response"]

    # --- TEST 4: District-level counts ---
    print("\n--- TEST 4: How many districts are critical? ---")
    payload4 = {
        "query": "How many districts are critical?",
        "conversation_id": conv_id
    }
    r_chat4 = requests.post(chat_url, json=payload4, headers=headers)
    assert r_chat4.status_code == 200, f"Call failed: {r_chat4.text}"
    
    res4 = r_chat4.json()
    print("Districts with Critical category units:")
    print(res4["response"])
    assert "**Districts classified as Critical:** 16" in res4["response"], "Expected count of 16 districts!"

    # --- TEST 5: Assessment unit counts ---
    print("\n--- TEST 5: How many assessment units are critical? ---")
    payload5 = {
        "query": "How many assessment units are critical?",
        "conversation_id": conv_id
    }
    r_chat5 = requests.post(chat_url, json=payload5, headers=headers)
    assert r_chat5.status_code == 200, f"Call failed: {r_chat5.text}"
    
    res5 = r_chat5.json()
    print("Assessment Units with Critical category units:")
    print(res5["response"])
    assert "**Assessment Units classified as Critical:** 16" in res5["response"], "Expected count of 16 units!"

    print("\nCATEGORY AGGREGATION TESTS SUCCESSFUL!")

if __name__ == "__main__":
    run_tests()
