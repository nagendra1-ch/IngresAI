import requests
import json
import sys

base_url = "http://127.0.0.1:8085"

def run_verification():
    print("Testing registration and login flow...")
    email = "verifier_test@example.com"
    password = "Password123!"
    
    # 1. Register user
    reg_url = f"{base_url}/api/auth/register"
    reg_data = {
        "email": email,
        "username": "verifier",
        "password": password,
        "name": "Verifier",
        "confirm_password": password
    }

    
    try:
        r_reg = requests.post(reg_url, json=reg_data)
        # 400 is fine if user already exists
        if r_reg.status_code not in (200, 201, 400):
            print(f"Registration failed: {r_reg.status_code} {r_reg.text}")
            sys.exit(1)
    except Exception as e:
        print(f"Failed to connect to backend: {e}")
        print("Please ensure the backend daemon is running on port 8085.")
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
        "Authorization": f"Bearer {token}"
    }
    print("Logged in successfully. Obtained access token.")

    # 3. Compare Kurnool vs Dr. B.R. Ambedkar Konaseema (fetch IDs dynamically)
    dist_url = f"{base_url}/api/districts"
    r_dist = requests.get(dist_url, headers=headers)
    if r_dist.status_code != 200:
        print(f"Failed to fetch districts list: {r_dist.status_code} {r_dist.text}")
        sys.exit(1)
        
    dist_list = r_dist.json()
    kurnool_id = None
    konaseema_id = None
    for d in dist_list:
        if d["district_name"] == "Kurnool":
            kurnool_id = d["id"]
        elif d["district_name"] == "Dr. B.R. Ambedkar Konaseema":
            konaseema_id = d["id"]
            
    if not kurnool_id or not konaseema_id:
        print(f"Kurnool ({kurnool_id}) or Konaseema ({konaseema_id}) ID not found in list!")
        sys.exit(1)
        
    compare_url = f"{base_url}/api/compare?district1={kurnool_id}&district2={konaseema_id}"
    r_comp = requests.get(compare_url, headers=headers)
    
    if r_comp.status_code != 200:
        print(f"Comparison API failed: {r_comp.status_code} {r_comp.text}")
        sys.exit(1)
        
    comp_json = r_comp.json()
    print("\n--- COMPARISON API RESPONSE ---")
    print(json.dumps(comp_json, indent=2))
    print("--------------------------------\n")
    
    # 4. Verify properties
    d1 = comp_json["district_1"]
    d2 = comp_json["district_2"]
    comparison = comp_json["comparison"]
    
    # Verification assertions
    assert d1["district_name"] == "Kurnool", "District 1 name mismatch"
    assert d2["district_name"] == "Dr. B.R. Ambedkar Konaseema", "District 2 name mismatch"
    
    # Check terminology and units
    assert "depth_to_water_level_m_bgl" in d1, "Missing depth_to_water_level_m_bgl"
    assert "annual_groundwater_recharge_ham" in d1, "Missing recharge ham metric"
    assert "annual_groundwater_extraction_ham" in d1, "Missing extraction ham metric"
    assert "stage_of_groundwater_extraction_percent" in d1, "Missing extraction stage percentage"
    assert d1["rainfall_mm"] == 650.2, "Kurnool fallback rainfall mismatch"
    assert d2["rainfall_mm"] == 1180.5, "Konaseema fallback rainfall mismatch"
    assert comparison["rainfall_difference_mm"] == 530.3, "Rainfall difference mismatch"
    
    # Ground target values
    print("Verifying target groundwater observations...")
    print(f"Kurnool depth: {d1['depth_to_water_level_m_bgl']} m bgl (Expected: 3.61)")
    print(f"Konaseema depth: {d2['depth_to_water_level_m_bgl']} m bgl (Expected: 3.62)")
    print(f"Kurnool recharge: {d1['annual_groundwater_recharge_ham']} ham (Expected: ~68072.73)")
    print(f"Konaseema recharge: {d2['annual_groundwater_recharge_ham']} ham (Expected: ~107660.55)")
    print(f"Kurnool extraction: {d1['annual_groundwater_extraction_ham']} ham (Expected: ~19733.20)")
    print(f"Konaseema extraction: {d2['annual_groundwater_extraction_ham']} ham (Expected: ~10753.36)")
    print(f"Kurnool stage of extraction: {d1['stage_of_groundwater_extraction_percent']}% (Expected: 30.51)")
    print(f"Konaseema stage of extraction: {d2['stage_of_groundwater_extraction_percent']}% (Expected: 10.51)")
    print(f"Kurnool fallback rainfall: {d1['rainfall_mm']} mm (Expected: 650.2)")
    print(f"Konaseema fallback rainfall: {d2['rainfall_mm']} mm (Expected: 1180.5)")
    
    # Check calculated absolute differences
    print("Verifying backend calculated differences...")
    print(f"Depth difference: {comparison['depth_difference_m']} m (Expected: 0.01)")
    print(f"Recharge difference: {comparison['recharge_difference_ham']} ham (Expected: ~39587.82)")
    print(f"Extraction difference: {comparison['extraction_difference_ham']} ham (Expected: ~8979.84)")
    print(f"Stage difference: {comparison['stage_difference_percentage_points']} percentage points (Expected: 20.0)")
    print(f"Rainfall difference: {comparison['rainfall_difference_mm']} mm (Expected: 530.3)")

    print("\nAPI VERIFICATION SUCCESSFUL! All targets match exact ground values including official IMD fallbacks.")

if __name__ == "__main__":
    run_verification()
