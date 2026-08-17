import requests
import sys

def main():
    print("Starting verification of INGRES AI backend APIs on running server...")
    base_url = "http://127.0.0.1:8085"
    
    try:
        # 1. Check Root Endpoint
        res = requests.get(f"{base_url}/")
        print(f"Root endpoint response: {res.status_code} - {res.json()}")
        assert res.status_code == 200, "Root endpoint failed"
        
        # 2. Try Login with Standard User
        login_data = {
            "email": "user@ingres.gov.in",
            "password": "userpassword"
        }
        res = requests.post(f"{base_url}/api/auth/login", json=login_data)
        print(f"Login endpoint response: {res.status_code}")
        assert res.status_code == 200, "User Login failed"
        
        token = res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # 3. Call Auth Me
        res = requests.get(f"{base_url}/api/auth/me", headers=headers)
        print(f"Auth Me response: {res.status_code} - User name: {res.json().get('name')}")
        assert res.status_code == 200, "Auth Me failed"
        
        # 4. Search Districts
        res = requests.get(f"{base_url}/api/districts/search?query=ananthapuramu", headers=headers)
        print(f"Search district response: {res.status_code}")
        assert res.status_code == 200, "Search district failed"
        data = res.json()
        assert len(data) > 0, "Ananthapuramu not found in search"
        print(f"Ananthapuramu level: {data[0].get('groundwater_level')}%")
        
        # 5. Compare two districts
        # Search Kurnool as well
        res = requests.get(f"{base_url}/api/districts/search?query=kurnool", headers=headers)
        kurnool_id = res.json()[0]["id"]
        ananthapuramu_id = data[0]["id"]
        
        res = requests.get(f"{base_url}/api/compare?district1={ananthapuramu_id}&district2={kurnool_id}", headers=headers)
        print(f"Comparison endpoint response: {res.status_code}")
        assert res.status_code == 200, "Comparison failed"
        comp = res.json()
        print(f"AI comparison text length: {len(comp.get('explanation'))} chars")
        
        # 6. Admin stats check (should block standard user)
        res = requests.get(f"{base_url}/api/admin/statistics", headers=headers)
        print(f"Admin stats call for standard user: {res.status_code}")
        assert res.status_code == 403, "Access control failure: User allowed into admin endpoint"
        
        # 7. Login with Admin
        admin_login = {
            "email": "admin@ingres.gov.in",
            "password": "adminpassword"
        }
        res = requests.post(f"{base_url}/api/auth/login", json=admin_login)
        admin_token = res.json()["access_token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        
        # 8. Check Admin statistics
        res = requests.get(f"{base_url}/api/admin/statistics", headers=admin_headers)
        print(f"Admin stats response: {res.status_code} - Data: {res.json()}")
        assert res.status_code == 200, "Admin stats failed"
        
        print("\nAll backend API checks PASSED successfully!")
        
    except Exception as e:
        print(f"\nVerification FAILED: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
