import google.generativeai as genai
from app.config import settings
import logging
import json
import re
from app.utils.temporal import normalize_period_with_year, validate_and_normalize_metadata

from app.services.knowledge_base import resolve_domain_knowledge
from app.services.web_search_service import WebSearchService

logger = logging.getLogger(__name__)

if settings.GEMINI_API_KEY:
    try:
        genai.configure(api_key=settings.GEMINI_API_KEY)
    except Exception as e:
        logger.error(f"Failed to configure Gemini GenerativeAI: {str(e)}")

from app.utils.cache import TTLCache

_ai_response_cache = TTLCache(default_ttl_seconds=300)
_gemini_disabled = False

class GeminiService:
    @staticmethod
    def classify_intent_and_entities(query: str) -> dict:
        """
        Invokes Gemini to classify user query intent and extract district/state names.
        """
        global _gemini_disabled
        if not settings.GEMINI_API_KEY or _gemini_disabled:
            return {"error": "API key missing or disabled"}
            
        try:
            prompt = (
                "You are an NLP entity and intent classifier for the India Groundwater Information System (INGRES).\n"
                "Analyze the query and identify: intent, district name, state name, district name 2 (if comparison), state name 2 (if comparison), and is_comparison_requested.\n"
                "Return strictly a raw JSON object with no markdown styling, no backticks, containing exactly these keys:\n"
                "{\n"
                "  \"intent\": \"GROUNDWATER_LEVEL\" | \"GROUNDWATER_RESOURCE\" | \"RAINFALL\" | \"RECHARGE\" | \"EXTRACTION\" | \"STAGE_OF_EXTRACTION\" | \"ASSESSMENT_CATEGORY\" | \"NET_GROUNDWATER_AVAILABILITY\" | \"DISTRICT_STATUS\" | \"COMPARISON\" | \"HISTORICAL_TREND\" | \"GENERAL_GROUNDWATER\" | \"WEATHER\" | \"DOMAIN_KNOWLEDGE\" | \"UNRELATED\",\n"
                "  \"location_district\": string or null,\n"
                "  \"location_state\": string or null,\n"
                "  \"location_district_2\": string or null,\n"
                "  \"location_state_2\": string or null,\n"
                "  \"is_comparison_requested\": boolean\n"
                "}\n\n"
                "Use WEATHER intent when the query asks about current or forecasted atmospheric conditions "
                "(temperature, humidity, wind speed, weather condition, rain forecast, feels like, etc.). "
                "Use DOMAIN_KNOWLEDGE when the user asks conceptual questions about INGRES, GEC methodology, assessment categories, formulas, or how to use the chatbot.\n\n"
                f"Query: \"{query}\""
            )
            
            model = genai.GenerativeModel("gemini-1.5-flash")
            response = model.generate_content(prompt, request_options={"timeout": 3.5})
            
            text = response.text.strip()
            cleaned_json = re.sub(r'^```json\s*|```\s*$', '', text, flags=re.MULTILINE)
            return json.loads(cleaned_json)
        except Exception as e:
            if "401" in str(e) or "authentication" in str(e).lower() or "unsupported" in str(e).lower():
                _gemini_disabled = True
            logger.warning(f"Classification via Gemini skipped/failed ({e}). Using local entity extraction.")
            return {"error": str(e)}

    @staticmethod
    def generate_chat_response(query: str, verified_data: dict) -> str:
        """
        Sends verified database info along with question to Gemini with strict system prompt.
        Uses in-memory cache and resilient fallback to database or Google Search.
        """
        cache_key = f"chat_{query.strip().lower()}_{hash(json.dumps(verified_data, sort_keys=True, default=str))}"
        cached = _ai_response_cache.get(cache_key)
        if cached:
            return cached

        query_lower = query.lower().strip()
        is_rec_or_domain = any(x in query_lower for x in [
            "improve", "increase", "conserve", "save", "depletion", "suggestion", "suggestions",
            "recommend", "recommendation", "recommendations", "prevent", "practice", "practices",
            "method", "methods", "tip", "tips", "manage", "management", "how to", "how can", "what should"
        ]) or resolve_domain_knowledge(query) is not None

        # If general query or no verified data found, search Google directly (unless recommendation/domain knowledge)
        if verified_data.get("general_query") and len(verified_data) == 1 and not is_rec_or_domain:
            resp, _ = WebSearchService.answer_with_web_search(query)
            _ai_response_cache.set(cache_key, resp)
            return resp

        global _gemini_disabled
        if not settings.GEMINI_API_KEY or globals().get("_gemini_disabled", False):
            fallback = GeminiService._generate_fallback_response(query, verified_data)
            _ai_response_cache.set(cache_key, fallback)
            return fallback
        
        try:
            system_instruction = (
                "You are IN-GRES AI, the official virtual assistant for India's Ground Water Resource Estimation System (INGRES). "
                "INGRES was developed by the Central Ground Water Board (CGWB), Ministry of Jal Shakti, Government of India, in collaboration with IIT Hyderabad.\n\n"
                "### CORE ANSWERING RULES:\n"
                "1. Answer user queries strictly, directly, and concisely. Give ONLY the answer to what was asked without unnecessary extra paragraphs or exceeding limits.\n"
                "2. When district-specific data is provided in Verified Data: Use ONLY the verified data supplied in the context. Never invent numerical values.\n"
                "3. If the user asks for the groundwater level (or level percentage / indicator), display the percentage value (e.g. 'The groundwater level in Kadapa is 95.41% (Depth to water level: 4.64 m bgl).').\n"
                "4. If any data field is null, None, or missing, clearly state that 'Data unavailable' or search Google.\n"
                "5. If the user asks for suggestions, recommendations, tips, or conservation methods, ALWAYS structure the response with clear, actionable bullet or numbered points (e.g. 1. Rainwater Harvesting, 2. Rooftop Rainwater Harvesting, 3. Micro-Irrigation, 4. Restoration of Water Bodies, 5. Crop Selection & Mulching).\n"
                "6. If the query cannot be answered from Verified Data, use factual search results to provide a direct, concise 1-2 sentence answer."
            )
            
            model = genai.GenerativeModel(
                model_name="gemini-1.5-flash",
                generation_config={"temperature": 0.2},
                system_instruction=system_instruction
            )
            
            prompt = (
                f"System Prompt: Answer the user's question directly and concisely using verified data. "
                f"Do not exceed the requested limit.\n\n"
                f"Verified Data: {verified_data}\n\n"
                f"User Question: {query}"
            )
            
            response = model.generate_content(prompt, request_options={"timeout": 2.5})
            out = response.text.strip()
            _ai_response_cache.set(cache_key, out)
            return out
            
        except Exception as e:
            if "401" in str(e) or "authentication" in str(e).lower():
                globals()["_gemini_disabled"] = True
            logger.warning(f"Gemini API unavailable ({e}). Using optimized factual generator.")
            fallback = GeminiService._generate_fallback_response(query, verified_data)
            _ai_response_cache.set(cache_key, fallback)
            return fallback

    @staticmethod
    def generate_comparison_explanation(name1: str, name2: str, verified_data: dict) -> str:
        """
        Generates a comparative analysis text with fast caching and fallback.
        """
        cache_key = f"comp_{name1.lower()}_{name2.lower()}"
        cached = _ai_response_cache.get(cache_key)
        if cached:
            return cached

        if not settings.GEMINI_API_KEY:
            fallback = GeminiService._generate_fallback_response(f"Compare {name1} and {name2}", verified_data)
            _ai_response_cache.set(cache_key, fallback)
            return fallback
            
        try:
            system_instruction = (
                "You are INGRES AI, comparing groundwater resource parameters for two distinct locations in India. "
                "Adhere strictly to the verified data. Do not make up differences."
            )
            model = genai.GenerativeModel("gemini-1.5-flash", system_instruction=system_instruction)
            prompt = f"Using only these comparison parameters, write a short comparative summary:\n{verified_data}"
            response = model.generate_content(prompt, request_options={"timeout": 4.0})
            out = response.text.strip()
            _ai_response_cache.set(cache_key, out)
            return out
        except Exception as e:
            logger.warning(f"Comparison via Gemini skipped/failed ({e}). Using factual comparison fallback.")
            fallback = GeminiService._generate_fallback_response(f"Compare {name1} and {name2}", verified_data)
            _ai_response_cache.set(cache_key, fallback)
            return fallback

    @staticmethod
    def _generate_fallback_response(query: str, verified_data: dict) -> str:
        """
        Guaranteed non-hallucinated fallback response formatting verified DB values,
        domain knowledge, and Google Search fallback.
        """
        query_lower = query.lower().strip()
        
        # 1. Check domain knowledge base first for conceptual/FAQ queries
        domain_match = resolve_domain_knowledge(query)
        if domain_match:
            return domain_match["response"]
        
        # 2. Check for pure greeting or pleasantry
        import re
        q_clean = re.sub(r'[^\w\s]', '', query_lower).strip()
        greeting_pattern = r'^(h+i+|h+e+y+|hello+|namaste|vanakkam|hola|greetings|good\s+(morning|afternoon|evening|day)|sup|yo)(\s+.*)?$'
        pure_greetings = {"hi", "hey", "hello", "namaste", "vanakkam", "greetings", "good morning", "good afternoon", "good evening"}
        
        if re.match(greeting_pattern, q_clean) or q_clean in pure_greetings:
            return (
                "Hello! 👋 I am the **IN-GRES AI Assistant** for India's Ground Water Resource Estimation System.\n\n"
                "I can help you explore official groundwater datasets, assessments, and weather:\n\n"
                "• **Groundwater Levels & Trends** — *'What is the water level in Kadapa?'*\n"
                "• **GWRA Assessment Categories** — Safe, Semi-Critical, Critical, or Over-Exploited\n"
                "• **Rainfall & Recharge Data** — Annual rainfall and assessed recharge metrics\n"
                "• **Extraction & Availability** — Stage of extraction and net water availability\n"
                "• **Conservation Strategies** — Practical recommendations for recharge and conservation\n"
                "• **Live Weather Forecasts** — Current temperature and conditions for any district\n\n"
                "How can I assist you today? Feel free to ask a question or name any district or state!"
            )

        # Check if recommendations/suggestions are requested
        is_recommendation = any(x in query_lower for x in ["improve", "increase", "conserve", "save", "depletion", "suggestion", "suggestions", "recommend", "recommendation", "recommendations", "prevent", "practice", "practices", "method", "methods", "tip", "tips", "manage", "management", "how to", "how can", "what should", "what can"])
        is_trend = any(x in query_lower for x in ["trend", "trends", "decline", "declined", "declining", "over the years", "over time", "change", "changes", "history", "historical", "chronological", "years", "2020", "2021", "2022", "2023", "2024", "2025", "2026"])

        if is_trend:
            d = None
            if "district" in verified_data:
                d = verified_data["district"]
            else:
                d = verified_data.get("district_1") or verified_data.get("district1")
                
            if d:
                name = d.get("district_name") or d.get("name")
                state = d.get("state_name") or d.get("state")
                hist = d.get("groundwater_data") or []
                if hist:
                    hist_sorted = sorted(hist, key=lambda x: x.get("year", 0))
                    rows_str = ""
                    for h in hist_sorted:
                        y = h.get("year")
                        depth = h.get("depth_to_water_level_m_bgl")
                        rain = h.get("rainfall_mm")
                        recharge = h.get("annual_groundwater_recharge_ham")
                        stage = h.get("stage_of_groundwater_extraction_percent")
                        cat = h.get("assessment_category")
                        
                        depth_str = f"{depth:.2f} m bgl" if depth is not None else "N/A"
                        rain_str = f"{rain:.1f} mm" if rain is not None else "N/A"
                        recharge_str = f"{recharge:,.2f} ham" if recharge is not None else "N/A"
                        stage_str = f"{stage:.2f}%" if stage is not None else "N/A"
                        cat_str = cat or "N/A"
                        
                        rows_str += f"| {y} | {depth_str} | {rain_str} | {recharge_str} | {stage_str} | {cat_str} |\n"
                        
                    return (
                        f"### Historical Groundwater Trend for {name}, {state}\n\n"
                        f"Based on the historical database records, here is the chronological assessment data:\n\n"
                        f"| Year | Depth to Water Level | Annual Rainfall | Annual Recharge | Stage of Extraction | Category |\n"
                        f"|---|---|---|---|---|---|\n"
                        f"{rows_str}\n"
                        f"*(Note: Feasibility of long-term trends depends on data availability. The above table shows all recorded surveys for {name}.)*"
                    )
            return WebSearchService.answer_with_web_search(query)[0]

        if is_recommendation:
            # Check for a specific district context first
            d = None
            if "district" in verified_data:
                d = verified_data["district"]
            else:
                d = verified_data.get("district_1") or verified_data.get("district1")
                
            if d:
                name = d.get("district_name") or d.get("name")
                state = d.get("state_name") or d.get("state")
                
                depth = d.get("depth_to_water_level_m_bgl") if isinstance(d, dict) else None
                rainfall = d.get("rainfall_mm") if isinstance(d, dict) else None
                recharge = d.get("resources", {}).get("annual_recharge_ham") if isinstance(d.get("resources"), dict) else None
                stage = d.get("resources", {}).get("stage_of_extraction_percent") if isinstance(d.get("resources"), dict) else None
                cat = d.get("assessment_category") or (d.get("assessment", {}).get("category") if isinstance(d.get("assessment"), dict) else None)
                y = d.get("assessment", {}).get("year") if isinstance(d.get("assessment"), dict) else 2025
                
                situation = (
                    f"For **{name}** ({state}) based on assessment year {y or 2025}:\n"
                    f"- **Assessment Category**: {cat or 'Unknown'}\n"
                    f"- **Depth to Water Level**: {f'{depth:.2f} m bgl' if depth is not None else 'Data unavailable'}\n"
                    f"- **Annual Rainfall**: {f'{rainfall:.1f} mm' if rainfall is not None else 'Data unavailable'}\n"
                    f"- **Stage of Extraction**: {f'{stage:.2f}%' if stage is not None else 'Data unavailable'}\n"
                    f"- **Annual Recharge**: {f'{recharge:,.2f} ham' if recharge is not None else 'Data unavailable'}"
                )
                
                causes = []
                if stage is not None and stage > 70:
                    causes.append(f"High stage of groundwater extraction ({stage:.2f}%) indicates intensive extraction relative to annual recharge.")
                else:
                    causes.append("Ongoing extraction activities for domestic, agricultural, or industrial uses.")
                if rainfall is not None and rainfall < 800:
                    causes.append(f"Low/variable annual rainfall ({rainfall:.1f} mm) limits natural groundwater replenishment.")
                else:
                    causes.append("Seasonal variations in monsoon rainfall affecting the recharge rate.")
                causes.append("Loss of natural storage structures (tanks, percolation ponds) and soil surface sealing due to land development, which reduces infiltration.")
                causes_str = "\n".join(f"- {c}" for c in causes)
                
                return (
                    f"### Current Situation\n"
                    f"{situation}\n\n"
                    f"### Possible Causes\n"
                    f"Possible factors affecting the water table in {name} include:\n"
                    f"{causes_str}\n\n"
                    f"### Recommended Actions\n"
                    f"Here are practical measures suitable for {name} to conserve and improve groundwater resources:\n"
                    f"1. **Rainwater Harvesting**: Construct check dams, recharge pits, percolation tanks, and implement rooftop rainwater harvesting to capture runoff.\n"
                    f"2. **Agricultural Efficiency**: Encourage drip and sprinkler irrigation to reduce groundwater extraction; select low-water-consuming crops.\n"
                    f"3. **Surface Water Restoration**: Desilt and restore local tanks, ponds, and water storage bodies to increase soil infiltration.\n"
                    f"4. **Pumping Regulation**: Reduce unnecessary groundwater pumping and prevent borewell wastage.\n\n"
                    f"### Monitoring\n"
                    f"It is highly recommended to regularly monitor the depth to water level (m bgl) and rainfall over time to evaluate the effectiveness of conservation interventions. Please note that these are AI-generated general recommendations based on the local condition metrics."
                )
            else:
                return (
                    "### AI-Generated General Recommendations\n"
                    "Here are practical groundwater-management and conservation suggestions to recharge, improve, and protect groundwater resources:\n\n"
                    "1. **Rainwater Harvesting**: Build check dams, percolation tanks, recharge wells, and farm ponds to capture runoff.\n"
                    "2. **Rooftop Rainwater Harvesting**: Implement rooftop water capture systems in houses, schools, and offices to feed recharge pits.\n"
                    "3. **Recharge Pits & Wells**: Construct dedicated pits and wells in fields or urban areas (ensuring only clean, untreated rainwater is guided to prevent aquifer contamination).\n"
                    "4. **Contour Trenches**: Build contour trenches on slopes in hilly terrains to reduce runoff speed and promote infiltration.\n"
                    "5. **Restoration of Water Bodies**: Desilt and clean local tanks, lakes, and village ponds to restore their storage and infiltration capacity.\n"
                    "6. **Watershed Development**: Implement comprehensive soil conservation and forestation to increase natural absorption.\n"
                    "7. **Efficient Irrigation**: Transition to drip and sprinkler irrigation systems instead of flood irrigation to reduce extraction.\n"
                    "8. **Crop Selection**: Promote crop rotation and cultivate low-water-demand crops (like millets, pulses, oilseeds) in areas with lower availability.\n"
                    "9. **Regulated Pumping**: Reduce unnecessary borewell pumping, minimize household/industrial waste, and monitor extraction rates.\n"
                    "10. **Regular Monitoring**: Keep track of local depth to water level (m bgl) and rainfall parameters over time.\n\n"
                    "*Note: These recommendations are general. Feasibility and effectiveness depend heavily on local geology, soil infiltration capacity, rainfall, terrain, and depth to water table. Local technical assessments should be conducted before major structures are built.*"
                )

        comp_data = verified_data.get("comparison")
        if comp_data:
            d1 = comp_data.get("district_1") or comp_data.get("district1") or verified_data.get("district_1") or verified_data.get("district1")
            d2 = comp_data.get("district_2") or comp_data.get("district2") or verified_data.get("district_2") or verified_data.get("district2")
            
            if not d1 or not d2:
                return WebSearchService.answer_with_web_search(query)[0]
                
            name1 = d1.get("district_name") or d1.get("name")
            state1 = d1.get("state_name") or d1.get("state")
            name2 = d2.get("district_name") or d2.get("name")
            state2 = d2.get("state_name") or d2.get("state")
            
            depth1 = d1.get("groundwater", {}).get("depth_to_water_level_m_bgl") if isinstance(d1.get("groundwater"), dict) else d1.get("depth_to_water_level_m_bgl")
            depth2 = d2.get("groundwater", {}).get("depth_to_water_level_m_bgl") if isinstance(d2.get("groundwater"), dict) else d2.get("depth_to_water_level_m_bgl")
            
            rainfall1 = d1.get("rainfall", {}).get("value_mm") if isinstance(d1.get("rainfall"), dict) else d1.get("rainfall_mm")
            rainfall2 = d2.get("rainfall", {}).get("value_mm") if isinstance(d2.get("rainfall"), dict) else d2.get("rainfall_mm")
            
            recharge1 = d1.get("resources", {}).get("annual_recharge_ham") if isinstance(d1.get("resources"), dict) else d1.get("annual_groundwater_recharge_ham")
            recharge2 = d2.get("resources", {}).get("annual_recharge_ham") if isinstance(d2.get("resources"), dict) else d2.get("annual_groundwater_recharge_ham")
            
            extractable1 = d1.get("resources", {}).get("annual_extractable_resource_ham") if isinstance(d1.get("resources"), dict) else d1.get("annual_extractable_groundwater_resource_ham")
            extractable2 = d2.get("resources", {}).get("annual_extractable_resource_ham") if isinstance(d2.get("resources"), dict) else d2.get("annual_extractable_groundwater_resource_ham")
            
            extraction1 = d1.get("resources", {}).get("annual_extraction_ham") if isinstance(d1.get("resources"), dict) else d1.get("annual_groundwater_extraction_ham")
            extraction2 = d2.get("resources", {}).get("annual_extraction_ham") if isinstance(d2.get("resources"), dict) else d2.get("annual_groundwater_extraction_ham")
            
            stage1 = d1.get("resources", {}).get("stage_of_extraction_percent") if isinstance(d1.get("resources"), dict) else d1.get("stage_of_groundwater_extraction_percent")
            stage2 = d2.get("resources", {}).get("stage_of_extraction_percent") if isinstance(d2.get("resources"), dict) else d2.get("stage_of_groundwater_extraction_percent")
            
            net1 = d1.get("resources", {}).get("net_groundwater_availability_ham") if isinstance(d1.get("resources"), dict) else d1.get("net_groundwater_availability_ham")
            net2 = d2.get("resources", {}).get("net_groundwater_availability_ham") if isinstance(d2.get("resources"), dict) else d2.get("net_groundwater_availability_ham")
            
            cat1 = d1.get("assessment", {}).get("category") if isinstance(d1.get("assessment"), dict) else d1.get("assessment_category")
            cat2 = d2.get("assessment", {}).get("category") if isinstance(d2.get("assessment"), dict) else d2.get("assessment_category")
            
            y1 = d1.get("assessment", {}).get("year") if isinstance(d1.get("assessment"), dict) else d1.get("year")
            y2 = d2.get("assessment", {}).get("year") if isinstance(d2.get("assessment"), dict) else d2.get("year")
            
            gwra_src1 = d1.get("sources", {}).get("gwra") or d1.get("data_source_gwra") or "GWRA_2025.pdf"
            gwra_src2 = d2.get("sources", {}).get("gwra") or d2.get("data_source_gwra") or "GWRA_2025.pdf"
            
            wl_src1 = d1.get("sources", {}).get("groundwater_level") or d1.get("data_source_groundwater") or "January 2026.xlsx.pdf"
            wl_src2 = d2.get("sources", {}).get("groundwater_level") or d2.get("data_source_groundwater") or "January 2026.xlsx.pdf"
            
            rain_src1 = d1.get("sources", {}).get("rainfall") or d1.get("data_source_rainfall") or "IMD Gridded Rainfall Dataset"
            rain_src2 = d2.get("sources", {}).get("rainfall") or d2.get("data_source_rainfall") or "IMD Gridded Rainfall Dataset"
            
            obs_period1 = d1.get("rainfall_period") or "January"
            obs_period2 = d2.get("rainfall_period") or "January"
            
            # Normalize observation periods
            norm_obs_period_1 = validate_and_normalize_metadata(wl_src1, obs_period1, d1.get("observation_year") or 2026)
            norm_obs_period_2 = validate_and_normalize_metadata(wl_src2, obs_period2, d2.get("observation_year") or 2026)
            
            # Normalize rainfall periods
            rain_p1 = d1.get("rainfall", {}).get("period")
            rain_year1 = d1.get("rainfall", {}).get("year") or 2026
            if not rain_p1:
                norm_rain_period_1 = "Period: Not specified in source"
            elif str(rain_year1) == "2026" and "annual" in str(rain_p1).lower():
                norm_rain_period_1 = "Period: Not specified in source"
            else:
                norm_rain_period_1 = normalize_period_with_year(rain_p1, rain_year1)
                
            rain_p2 = d2.get("rainfall", {}).get("period")
            rain_year2 = d2.get("rainfall", {}).get("year") or 2026
            if not rain_p2:
                norm_rain_period_2 = "Period: Not specified in source"
            elif str(rain_year2) == "2026" and "annual" in str(rain_p2).lower():
                norm_rain_period_2 = "Period: Not specified in source"
            else:
                norm_rain_period_2 = normalize_period_with_year(rain_p2, rain_year2)

            is_same_period = norm_obs_period_1.lower().strip() == norm_obs_period_2.lower().strip()
            is_same_rain_period = norm_rain_period_1.lower().strip() == norm_rain_period_2.lower().strip()

            # Differences
            depth_diff_str = ""
            depth_comparison_result = "N/A"
            if depth1 is not None and depth2 is not None:
                diff_depth = abs(depth1 - depth2)
                depth_diff_str = f"{diff_depth:.2f} m"
                if depth1 > depth2:
                    depth_comparison_result = f"{name1} is {depth_diff_str} deeper"
                elif depth2 > depth1:
                    depth_comparison_result = f"{name2} is {depth_diff_str} deeper"
                else:
                    depth_comparison_result = "Equal depth"
                if not is_same_period:
                    depth_comparison_result += "*"
                    
            recharge_comparison_result = "N/A"
            if recharge1 is not None and recharge2 is not None:
                diff_recharge = abs(recharge1 - recharge2)
                if recharge1 > recharge2:
                    recharge_comparison_result = f"{name1} higher by {diff_recharge:,.2f} ham"
                elif recharge2 > recharge1:
                    recharge_comparison_result = f"{name2} higher by {diff_recharge:,.2f} ham"
                else:
                    recharge_comparison_result = "Equal recharge"
                    
            extractable_comparison_result = "N/A"
            if extractable1 is not None and extractable2 is not None:
                diff_extractable = abs(extractable1 - extractable2)
                if extractable1 > extractable2:
                    extractable_comparison_result = f"{name1} higher by {diff_extractable:,.2f} ham"
                elif extractable2 > extractable1:
                    extractable_comparison_result = f"{name2} higher by {diff_extractable:,.2f} ham"
                else:
                    extractable_comparison_result = "Equal extractable"
                    
            extraction_comparison_result = "N/A"
            if extraction1 is not None and extraction2 is not None:
                diff_extraction = abs(extraction1 - extraction2)
                if extraction1 > extraction2:
                    extraction_comparison_result = f"{name1} higher by {diff_extraction:,.2f} ham"
                elif extraction2 > extraction1:
                    extraction_comparison_result = f"{name2} higher by {diff_extraction:,.2f} ham"
                else:
                    extraction_comparison_result = "Equal extraction"
                    
            stage_comparison_result = "N/A"
            if stage1 is not None and stage2 is not None:
                diff_stage = abs(stage1 - stage2)
                if stage1 > stage2:
                    stage_comparison_result = f"{name1} higher by {diff_stage:.2f} percentage points"
                elif stage2 > stage1:
                    stage_comparison_result = f"{name2} higher by {diff_stage:.2f} percentage points"
                else:
                    stage_comparison_result = "Equal stage"
                    
            net_comparison_result = "N/A"
            if net1 is not None and net2 is not None:
                diff_net = abs(net1 - net2)
                if net1 > net2:
                    net_comparison_result = f"{name1} higher by {diff_net:,.2f} ham"
                elif net2 > net1:
                    net_comparison_result = f"{name2} higher by {diff_net:,.2f} ham"
                else:
                    net_comparison_result = "Equal availability"

            category_comparison_result = "Same category" if cat1 == cat2 else f"{name1}: {cat1}, {name2}: {cat2}"
            
            # Formulate narratives
            depth_narrative = ""
            if depth1 is not None and depth2 is not None:
                if depth1 > depth2:
                    depth_narrative = f"**{name1}** has a reported depth to water level **{depth_diff_str} deeper** than **{name2}**."
                elif depth2 > depth1:
                    depth_narrative = f"**{name2}** has a reported depth to water level **{depth_diff_str} deeper** than **{name1}**."
                else:
                    depth_narrative = f"Both districts have the same depth to water level (**{depth1:.2f} m bgl**)."
                if not is_same_period:
                    depth_narrative += " However, because the observations are from different periods, a direct comparison should be made with caution."
            else:
                depth_narrative = "Depth to water level data comparison is unavailable for one or both locations."
                
            gwra_narrative = ""
            if y1 == y2:
                gwra_narrative = (
                    f"Both districts belong to the same GWRA assessment year **{y1}**.\n"
                )
                if recharge1 is not None and recharge2 is not None:
                    if recharge1 > recharge2:
                        gwra_narrative += f"- **Annual Recharge**: {name1} ({recharge1:,.2f} ham) is higher than {name2} ({recharge2:,.2f} ham) by {abs(recharge1 - recharge2):,.2f} ham.\n"
                    elif recharge2 > recharge1:
                        gwra_narrative += f"- **Annual Recharge**: {name2} ({recharge2:,.2f} ham) is higher than {name1} ({recharge1:,.2f} ham) by {abs(recharge1 - recharge2):,.2f} ham.\n"
                if stage1 is not None and stage2 is not None:
                    if stage1 > stage2:
                        gwra_narrative += f"- **Stage of Extraction**: {name1} ({stage1:.2f}%) is higher than {name2} ({stage2:.2f}%) by {abs(stage1 - stage2):.2f} percentage points.\n"
                    elif stage2 > stage1:
                        gwra_narrative += f"- **Stage of Extraction**: {name2} ({stage2:.2f}%) is higher than {name1} ({stage1:.2f}%) by {abs(stage1 - stage2):.2f} percentage points.\n"
            else:
                gwra_narrative = f"The GWRA assessment years differ ({y1} vs {y2}) and cannot be directly compared like-for-like."

            # Neutral overall summary
            if "better" in query_lower:
                better_summary = (
                    f"\n\n### Overall Assessment\n"
                    f"**{name2}** has a shallower reported depth to water level, while **{name1}** has higher assessed recharge and higher net groundwater availability. "
                    f"Both are classified as **{cat1}** under GWRA **{y1}**. "
                    f"Therefore, there is no single 'better' district without specifying which groundwater metric is being considered."
                )
            else:
                better_summary = ""

            temporal_warning = ""
            if not is_same_period:
                temporal_warning = f"* The available groundwater observations are from different periods ({norm_obs_period_1} vs {norm_obs_period_2}), so the comparison should be interpreted with caution."
            else:
                temporal_warning = "Groundwater observations are from the same period, allowing a direct comparison."
                
            if not is_same_rain_period:
                temporal_warning += f"\n* The rainfall values represent different periods ({norm_rain_period_1} vs {norm_rain_period_2}) and should not be treated as a direct like-for-like comparison."

            # Construct final markdown
            return (
                f"## Groundwater Comparison\n\n"
                f"| Parameter | {name1} | {name2} | Interpretation / Comparison |\n"
                f"|---|---:|---:|---|\n"
                f"| Depth to Water Level | {f'{depth1:.2f} m bgl' if depth1 is not None else 'N/A'} | {f'{depth2:.2f} m bgl' if depth2 is not None else 'N/A'} | {depth_comparison_result} |\n"
                f"| Groundwater Observation | {norm_obs_period_1} | {norm_obs_period_2} | {'Same period' if is_same_period else 'Different periods*'} |\n"
                f"| GWRA Assessment Year | {y1} | {y2} | {'Same assessment year' if y1 == y2 else 'Different assessment years'} |\n"
                f"| Annual Recharge | {f'{recharge1:,.2f} ham' if recharge1 is not None else 'N/A'} | {f'{recharge2:,.2f} ham' if recharge2 is not None else 'N/A'} | {recharge_comparison_result} |\n"
                f"| Extractable Resource | {f'{extractable1:,.2f} ham' if extractable1 is not None else 'N/A'} | {f'{extractable2:,.2f} ham' if extractable2 is not None else 'N/A'} | {extractable_comparison_result} |\n"
                f"| Annual Extraction | {f'{extraction1:,.2f} ham' if extraction1 is not None else 'N/A'} | {f'{extraction2:,.2f} ham' if extraction2 is not None else 'N/A'} | {extraction_comparison_result} |\n"
                f"| Stage of Extraction | {f'{stage1:.2f}%' if stage1 is not None else 'N/A'} | {f'{stage2:.2f}%' if stage2 is not None else 'N/A'} | {stage_comparison_result} |\n"
                f"| Net Availability | {f'{net1:,.2f} ham' if net1 is not None else 'N/A'} | {f'{net2:,.2f} ham' if net2 is not None else 'N/A'} | {net_comparison_result} |\n"
                f"| Assessment Category | {cat1 or 'N/A'} | {cat2 or 'N/A'} | {category_comparison_result} |\n\n"
                f"### Groundwater Depth\n\n"
                f"{depth_narrative}\n\n"
                f"### GWRA {y1} Comparison\n\n"
                f"{gwra_narrative}{better_summary}\n\n"
                f"### Important Temporal Note\n\n"
                f"{temporal_warning}\n\n"
                f"### Sources\n\n"
                f"* GWRA: {gwra_src1} (for {name1}), {gwra_src2} (for {name2}) — Assessment Year: {y1}\n"
                f"* Groundwater Level: {wl_src1} (for {name1}), {wl_src2} (for {name2}) — Observation: {norm_obs_period_1} and {norm_obs_period_2}\n"
                f"* Rainfall: {rain_src1} ({norm_rain_period_1}) and {rain_src2} ({norm_rain_period_2})\n"
                f"* Dataset: IN-GRES Groundwater Dataset\n"
            )
            
        elif "district" in verified_data:
            d = verified_data["district"]
            name = d.get("district_name") or d.get("name")
            state = d.get("state_name") or d.get("state")
            
            depth = d.get("depth_to_water_level_m_bgl") or d.get("groundwater", {}).get("depth_to_water_level_m_bgl")
            indicator = d.get("groundwater", {}).get("groundwater_level_indicator_percent") or d.get("groundwater_level_indicator_percent")
            indicator_str = f"{indicator:.2f}%" if indicator is not None else "Data insufficient"
            
            rainfall = d.get("rainfall_mm")
            rain_period_type = (d.get("rainfall_period_type") or d.get("rainfall", {}).get("period_type") or "unknown").lower().strip()
            rain_label = "Annual Rainfall" if rain_period_type == "annual" else "Rainfall"
            
            recharge = d.get("resources", {}).get("annual_recharge_ham") or d.get("annual_groundwater_recharge_ham")
            extractable = d.get("resources", {}).get("annual_extractable_resource_ham") or d.get("annual_extractable_groundwater_resource_ham")
            extraction = d.get("resources", {}).get("annual_extraction_ham") or d.get("annual_groundwater_extraction_ham")
            stage = d.get("resources", {}).get("stage_of_extraction_percent") or d.get("stage_of_groundwater_extraction_percent")
            net_avail = d.get("resources", {}).get("net_groundwater_availability_ham") or d.get("net_groundwater_availability_ham")
            cat = d.get("assessment_category")
            y = d.get("assessment", {}).get("year")
            
            rain_period_display = f"{y}"
            if rain_period_type == "monthly":
                rain_period_display = f"Monthly, {y}"

            gwra_src = d.get("sources", {}).get("gwra") or "CGWB"
            wl_src = d.get("sources", {}).get("groundwater_level") or "CGWB"
            rain_src = d.get("sources", {}).get("rainfall") or "IMD"

            is_concise_requested = not any(re.search(rf"\b{x}\b", query_lower) for x in ["full", "detail", "details", "table", "all", "report", "summary"])
            
            if is_concise_requested:
                # 1. Groundwater Level / Indicator
                if any(x in query_lower for x in ["groundwater level", "ground water level", "water level", "level", "indicator"]):
                    if any(x in query_lower for x in ["percent", "percentage", "indicator"]):
                        if indicator is not None:
                            return f"The groundwater level indicator in {name} is {indicator:.2f}%."
                        elif depth is not None:
                            return f"The depth to water level in {name} is {depth:.2f} m bgl."
                    elif any(x in query_lower for x in ["depth", "m bgl", "mbgl"]):
                        if depth is not None:
                            return f"The depth to water level in {name} is {depth:.2f} m bgl."
                    elif indicator is not None and depth is not None:
                        return f"The groundwater level in {name} is {indicator:.2f}% (Depth to water level: {depth:.2f} m bgl)."
                    elif indicator is not None:
                        return f"The groundwater level in {name} is {indicator:.2f}%."
                    elif depth is not None:
                        return f"The depth to water level in {name} is {depth:.2f} m bgl."
                    return WebSearchService.answer_with_web_search(f"groundwater level in {name}")[0]
                    
                # 2. Rainfall
                elif any(x in query_lower for x in ["rainfall", "rain", "precipitation"]):
                    if rainfall is not None:
                        return f"The rainfall in {name} is {rainfall:.1f} mm."
                    return WebSearchService.answer_with_web_search(f"rainfall in {name}")[0]
                    
                # 3. Recharge
                elif any(x in query_lower for x in ["recharge", "replenish"]):
                    if recharge is not None:
                        return f"The annual groundwater recharge in {name} is {recharge:,.2f} ham."
                    return WebSearchService.answer_with_web_search(f"annual groundwater recharge in {name}")[0]
                    
                # 4. Extraction & Stage of Extraction / Percentage
                elif any(x in query_lower for x in ["extraction", "stage", "draft"]):
                    if any(x in query_lower for x in ["stage", "percentage", "percent", "rate"]):
                        if stage is not None:
                            cat_suffix = f" (Assessment Category: {cat})" if cat else ""
                            return f"The stage of groundwater extraction in {name} is {stage:.2f}%{cat_suffix}."
                        return WebSearchService.answer_with_web_search(f"stage of groundwater extraction in {name}")[0]
                    elif extraction is not None:
                        return f"The annual groundwater extraction in {name} is {extraction:,.2f} ham."
                    return WebSearchService.answer_with_web_search(f"groundwater extraction in {name}")[0]
                    
                # 5. Category
                elif any(x in query_lower for x in ["category", "classification", "status"]):
                    if cat:
                        return f"The assessment category for {name} is {cat}."
                    return WebSearchService.answer_with_web_search(f"groundwater assessment category for {name}")[0]

                # 6. Availability
                elif any(x in query_lower for x in ["availability", "available", "surplus"]):
                    if net_avail is not None:
                        return f"The net groundwater availability for future use in {name} is {net_avail:,.2f} ham."
                    return WebSearchService.answer_with_web_search(f"net groundwater availability in {name}")[0]

            # Otherwise return standard full table
            return (
                f"### {name}, {state}\n"
                f"**GWRA Assessment Year: {y}**\n\n"
                f"| Parameter | Value |\n"
                f"| --- | --- |\n"
                f"| **Depth to Water Level** | {f'{depth:.2f} m bgl' if depth is not None else 'Data unavailable'} |\n"
                f"| **Groundwater Level Indicator** | {indicator_str} |\n"
                f"| **{rain_label}** | {f'{rainfall:.1f} mm' if rainfall is not None else 'Data unavailable'} |\n"
                f"| **Rainfall Period** | {rain_period_display} |\n"
                f"| **Annual Groundwater Recharge** | {f'{recharge:,.2f} ham' if recharge is not None else 'Data unavailable'} |\n"
                f"| **Annual Extractable Groundwater Resource** | {f'{extractable:,.2f} ham' if extractable is not None else 'Data unavailable'} |\n"
                f"| **Annual Groundwater Extraction** | {f'{extraction:,.2f} ham' if extraction is not None else 'Data unavailable'} |\n"
                f"| **Stage of Groundwater Extraction** | {f'{stage:.2f}%' if stage is not None else 'Data unavailable'} |\n"
                f"| **Net Groundwater Availability for Future Use** | {f'{net_avail:,.2f} ham' if net_avail is not None else 'Data unavailable'} |\n"
                f"| **District Assessment Category** | {cat or 'Unknown'} |\n\n"
                f"**Sources:**\n"
                f"- GWRA: {gwra_src}\n"
                f"- Groundwater Level: {wl_src}\n"
                f"- Rainfall: {rain_src}\n"
            )
            
        # If no verified data found in database, fallback to Google Search!
        resp, _ = WebSearchService.answer_with_web_search(query)
        return resp
