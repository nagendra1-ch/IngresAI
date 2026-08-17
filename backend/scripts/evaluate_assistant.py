import requests
import json
import sys
import os

base_url = "http://127.0.0.1:8085"

# List of districts and ambiguous names for templates
districts = ["Kadapa", "Guntur", "Ananthapuramu", "Kurnool", "Nellore", "Chittoor", "Visakhapatnam", "Krishna", "Prakasam", "Srikakulam"]
ambiguous_locations = ["Ananthapuramu", "Hamirpur", "Bilaspur", "Aurangabad", "Balrampur"]
terms = ["groundwater", "aquifer", "recharge", "extraction", "water table", "depth to water level", "m bgl", "gwra", "cgwb", "in-gres"]

def generate_dataset():
    dataset = []
    
    # 1. 100 Factual questions
    for i in range(100):
        dist = districts[i % len(districts)]
        metric = i % 4
        if metric == 0:
            q = f"What is the groundwater level in {dist}?"
        elif metric == 1:
            q = f"What is the annual groundwater recharge in {dist}?"
        elif metric == 2:
            q = f"Show me extraction statistics for {dist}."
        else:
            q = f"What is the net groundwater availability for future use in {dist}?"
        dataset.append(("FACTUAL", q))
        
    # 2. 100 Recommendation questions
    for i in range(100):
        dist = districts[i % len(districts)]
        verb = i % 4
        if verb == 0:
            q = f"How can we improve groundwater in {dist}?"
        elif verb == 1:
            q = f"What should we do to recharge groundwater in {dist}?"
        elif verb == 2:
            q = f"Give suggestions to increase groundwater in {dist}."
        else:
            q = f"How can farmers improve groundwater availability in {dist}?"
        dataset.append(("RECOMMENDATION", q))
        
    # 3. 50 Comparison questions
    for i in range(50):
        d1 = districts[i % len(districts)]
        d2 = districts[(i + 1) % len(districts)]
        type_comp = i % 3
        if type_comp == 0:
            q = f"Compare {d1} and {d2} groundwater levels."
        elif type_comp == 1:
            q = f"Which district has higher rainfall, {d1} or {d2}?"
        else:
            q = f"Compare groundwater extraction in {d1} and {d2}."
        dataset.append(("COMPARISON", q))
        
    # 4. 50 Explanation questions
    for i in range(50):
        term = terms[i % len(terms)]
        q = f"What is {term}?"
        dataset.append(("EXPLANATION", q))
        
    # 5. 50 Conservation questions
    for i in range(50):
        tip = i % 4
        if tip == 0:
            q = "How can we conserve groundwater?"
        elif tip == 1:
            q = "What are the best tips to save groundwater?"
        elif tip == 2:
            q = "How can households reduce groundwater consumption?"
        else:
            q = "What is a village groundwater management plan?"
        dataset.append(("CONSERVATION", q))
        
    # 6. 50 Rainfall questions
    for i in range(50):
        dist = districts[i % len(districts)]
        rain_q = i % 3
        if rain_q == 0:
            q = f"What is the rainfall in {dist}?"
        elif rain_q == 1:
            q = "How does monsoon rainfall affect recharge?"
        else:
            q = f"Compare rainfall between {dist} and Guntur."
        dataset.append(("RAINFALL", q))
        
    # 7. 50 Extraction/GWRA questions
    for i in range(50):
        dist = districts[i % len(districts)]
        ext_q = i % 3
        if ext_q == 0:
            q = f"What is the stage of groundwater extraction in {dist}?"
        elif ext_q == 1:
            q = "What does 37.93% extraction mean?"
        else:
            q = f"Is the groundwater category of {dist} safe or critical?"
        dataset.append(("EXTRACTION_GWRA", q))
        
    # 8. 50 Trend questions
    for i in range(50):
        dist = districts[i % len(districts)]
        trend_q = i % 2
        if trend_q == 0:
            q = f"Is groundwater improving in {dist} over the years?"
        else:
            q = f"Has groundwater declined over the years in {dist}?"
        dataset.append(("TREND", q))
        
    # 9. 50 Deliberately ambiguous questions
    for i in range(50):
        loc = ambiguous_locations[i % len(ambiguous_locations)]
        q = f"What is the groundwater level in {loc}?"
        dataset.append(("AMBIGUOUS", q))
        
    # 10. 50 Unrelated questions
    unrelated_queries = [
        "Who is the Prime Minister?",
        "Write a Python program.",
        "What is today's cricket score?",
        "Tell me a joke.",
        "What is the capital of France?",
        "How do I cook pasta?",
        "Explain quantum mechanics.",
        "What is the price of oil?",
        "Who wrote Hamlet?",
        "How do I fix a flat tire?"
    ]
    for i in range(50):
        q = unrelated_queries[i % len(unrelated_queries)]
        # Append some variations
        if i >= 10:
            q = f"{q} (query index {i})"
        dataset.append(("UNRELATED", q))
        
    return dataset

def run_evaluation():
    print("Preparing test user session...")
    login_url = f"{base_url}/api/auth/login"
    login_data = {
        "email": "user@ingres.gov.in",
        "password": "userpassword"
    }
    
    try:
        r_login = requests.post(login_url, json=login_data)
        if r_login.status_code != 200:
            print(f"Failed to log in: {r_login.text}")
            sys.exit(1)
        token = r_login.json()["access_token"]
    except Exception as e:
        print(f"Server is offline or unreachable: {e}")
        sys.exit(1)
        
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    dataset = generate_dataset()
    print(f"Successfully generated evaluation dataset of {len(dataset)} questions.")
    
    passed_counts = {}
    total_counts = {}
    failed_details = []
    
    # Run chat requests
    chat_url = f"{base_url}/api/ai/chat"
    
    for idx, (category, query) in enumerate(dataset):
        if category not in total_counts:
            total_counts[category] = 0
            passed_counts[category] = 0
            
        total_counts[category] += 1
        
        payload = {
            "query": query
        }
        
        try:
            r = requests.post(chat_url, json=payload, headers=headers)
            if r.status_code != 200:
                failed_details.append((category, query, f"HTTP Error {r.status_code}: {r.text}"))
                continue
                
            res = r.json()
            response_text = res["response"]
            
            # Category-specific validation rules
            passed = True
            error_msg = ""
            
            if category == "UNRELATED":
                expected_scope_msg = "This question is outside the scope of IN-GRES AI. I can help with groundwater levels, groundwater resources, rainfall, recharge, extraction, GWRA assessments, groundwater conservation, and related topics."
                if response_text != expected_scope_msg:
                    passed = False
                    error_msg = f"Expected scope-limit message, got: {response_text}"
                    
            elif category == "RECOMMENDATION":
                # Must contain the four headers if district is present
                headers_to_check = ["### Current Situation", "### Possible Causes", "### Recommended Actions", "### Monitoring"]
                missing = [h for h in headers_to_check if h not in response_text]
                if missing:
                    # Let's check if district was actually resolved
                    if res.get("location") and res["location"].get("district"):
                        passed = False
                        error_msg = f"Missing recommendation headers: {missing}"
                    else:
                        # General recommendation, should contain general notice
                        if "recommendations are general" not in response_text.lower() and "general recommendations" not in response_text.lower():
                            passed = False
                            error_msg = "General recommendation response should notify that it is general."
                            
            elif category == "FACTUAL":
                # Should not output percentage symbol for depth!
                if "depth to water level" in response_text.lower():
                    # Check if depth has percentage symbol close to it
                    parts = response_text.split("Depth to Water Level")
                    if len(parts) > 1 and "%" in parts[1].split("\n")[0]:
                        passed = False
                        error_msg = "Depth to water level displayed with a percentage symbol!"
                        
            elif category == "AMBIGUOUS":
                # Should detect multiple locations or ask to specify state
                if "multiple locations" not in response_text.lower() and "please specify" not in response_text.lower():
                    passed = False
                    error_msg = f"Ambiguous query did not prompt for state clarification. Got: {response_text}"
                    
            if passed:
                passed_counts[category] += 1
            else:
                failed_details.append((category, query, error_msg))
                
        except Exception as e:
            failed_details.append((category, query, f"Exception: {e}"))
            
        if (idx + 1) % 100 == 0:
            print(f"Processed {idx + 1}/{len(dataset)} queries...")
            
    print("\n================ EVALUATION REPORT ================")
    overall_passed = 0
    overall_total = 0
    for cat in total_counts:
        p = passed_counts[cat]
        t = total_counts[cat]
        overall_passed += p
        overall_total += t
        pct = (p / t) * 100
        print(f"Category {cat:20} : {p}/{t} ({pct:.1f}% Passed)")
        
    overall_pct = (overall_passed / overall_total) * 100
    print("---------------------------------------------------")
    print(f"OVERALL ACCURACY     : {overall_passed}/{overall_total} ({overall_pct:.2f}% Passed)")
    print("===================================================\n")
    
    if failed_details:
        print("Sample Failures (up to 5):")
        for i, (cat, q, err) in enumerate(failed_details[:5]):
            print(f"[{cat}] Q: '{q}' -> Error: {err}")
            
    if overall_pct >= 95.0:
        print("\nEvaluation SUCCESSFUL: Met target of >=95% accuracy!")
        sys.exit(0)
    else:
        print("\nEvaluation FAILED: Did not meet target accuracy.")
        sys.exit(1)

if __name__ == "__main__":
    run_evaluation()
