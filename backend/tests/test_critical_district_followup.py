import requests
import sys

base_url = "http://127.0.0.1:8000"

def run_followup_tests():
    print("Testing critical district follow-up flow...")
    email = "followup_test@example.com"
    password = "Password123!"
    
    # 1. Register user
    reg_url = f"{base_url}/api/auth/register"
    reg_data = {
        "email": email,
        "username": "followup_tester",
        "password": password,
        "name": "FollowupTester",
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
    chat_url = f"{base_url}/api/ai/chat"

    # --- Step 1: How many states are in the critical zone? ---
    print("\n--- Step 1: How many states are in the critical zone? ---")
    p1 = {"query": "How many states are in the critical zone?"}
    r1 = requests.post(chat_url, json=p1, headers=headers)
    assert r1.status_code == 200, f"Failed: {r1.text}"
    res1 = r1.json()
    conv_id = res1["conversation_id"]
    print(res1["response"])
    assert "**States with at least one Critical assessment unit:** 9" in res1["response"]

    # --- Step 2: What are the district names? ---
    print("\n--- Step 2: What are the district names? ---")
    p2 = {"query": "What are the district names?", "conversation_id": conv_id}
    r2 = requests.post(chat_url, json=p2, headers=headers)
    assert r2.status_code == 200, f"Failed: {r2.text}"
    res2 = r2.json()
    print(res2["response"])
    assert "### Critical Assessment Districts" in res2["response"]
    assert "**Total districts containing at least one Critical assessment unit:** 16" in res2["response"]
    assert "Uttar Pradesh" in res2["response"]
    assert "Rajasthan" in res2["response"]

    # --- Step 3: How many are there? ---
    print("\n--- Step 3: How many are there? ---")
    p3 = {"query": "How many are there?", "conversation_id": conv_id}
    r3 = requests.post(chat_url, json=p3, headers=headers)
    assert r3.status_code == 200, f"Failed: {r3.text}"
    res3 = r3.json()
    print(res3["response"])
    assert "**Total districts containing at least one Critical assessment unit:** 16" in res3["response"]
    assert "| State | District |" not in res3["response"], "Expected count-only format without full table list!"

    # --- Step 4: Which state has the most? ---
    print("\n--- Step 4: Which state has the most? ---")
    p4 = {"query": "Which state has the most?", "conversation_id": conv_id}
    r4 = requests.post(chat_url, json=p4, headers=headers)
    assert r4.status_code == 200, f"Failed: {r4.text}"
    res4 = r4.json()
    print(res4["response"])
    assert "Uttar Pradesh" in res4["response"]
    assert "4" in res4["response"]

    # --- Step 5: What about semi-critical? ---
    print("\n--- Step 5: What about semi-critical? ---")
    p5 = {"query": "What about semi-critical?", "conversation_id": conv_id}
    r5 = requests.post(chat_url, json=p5, headers=headers)
    assert r5.status_code == 200, f"Failed: {r5.text}"
    res5 = r5.json()
    print(res5["response"])
    assert "### Semi-Critical Assessment Districts" in res5["response"]

    print("\nCRITICAL DISTRICT FOLLOW-UP CONTEXT TESTS SUCCESSFUL!")

if __name__ == "__main__":
    run_followup_tests()
