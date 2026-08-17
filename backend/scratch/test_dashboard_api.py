import requests
import sys

base_url = "http://127.0.0.1:8085"

def test_dashboard():
    # 1. Login to get token
    login_url = f"{base_url}/api/auth/login"
    login_data = {
        "email": "conv_test@example.com",
        "password": "Password123!"
    }
    r_login = requests.post(login_url, json=login_data)
    if r_login.status_code != 200:
        print(f"Login failed: {r_login.status_code} {r_login.text}")
        sys.exit(1)
        
    token = r_login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # 2. Test summary endpoint
    print("Testing /api/dashboard/summary...")
    r_sum = requests.get(f"{base_url}/api/dashboard/summary", headers=headers)
    print("Status:", r_sum.status_code)
    print("Response:", r_sum.text[:500])
    
    # 3. Test state-statistics endpoint
    print("Testing /api/dashboard/state-statistics...")
    r_stats = requests.get(f"{base_url}/api/dashboard/state-statistics", headers=headers)
    print("Status:", r_stats.status_code)
    print("Response:", r_stats.text[:500])

if __name__ == "__main__":
    test_dashboard()
