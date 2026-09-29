import httpx
import re
import urllib.parse
import html
import logging
from typing import List, Dict, Optional, Tuple
from app.config import settings

logger = logging.getLogger(__name__)

class WebSearchService:
    """
    Multi-engine web & Google search service for IN-GRES AI.
    Searches Google, Bing, DuckDuckGo, and Wikipedia to answer user queries
    when data is not found in the local database.
    """

    @staticmethod
    def search_web(query: str, max_results: int = 6) -> List[Dict[str, str]]:
        """
        Queries multiple search engines and aggregates relevant snippets and titles.
        """
        results = []
        cleaned_query = query.strip()
        encoded = urllib.parse.quote_plus(cleaned_query)

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        }

        # 1. Google Search
        try:
            url = f"https://www.google.com/search?q={encoded}&hl=en&gl=in"
            with httpx.Client(timeout=4.5, headers=headers, follow_redirects=True) as client:
                resp = client.get(url)
                if resp.status_code == 200:
                    blocks = re.findall(r'<div[^>]*class="[^"]*(?:VwiC3b|hgKElc|kno-rdesc|MUxGbd|s3v9rd)[^"]*"[^>]*>(.*?)</div>', resp.text, re.DOTALL)
                    for b in blocks[:max_results]:
                        clean = html.unescape(re.sub(r'<[^>]+>', '', b)).strip()
                        if len(clean) > 25 and not any(bad in clean.lower() for bad in ["javascript", "cookies", "enable javascript"]):
                            results.append({"title": "Google Search", "snippet": clean, "source": "Google Search"})
        except Exception as e:
            logger.debug(f"Google search error: {e}")

        # 2. Bing Search (fallback or complementary)
        if len(results) < 3:
            try:
                b_url = f"https://www.bing.com/search?q={encoded}&setlang=en&cc=in"
                with httpx.Client(timeout=4.5, headers=headers, follow_redirects=True) as client:
                    resp = client.get(b_url)
                    if resp.status_code == 200:
                        algo_blocks = re.findall(r'<li class="b_algo"[^>]*>(.*?)</li>', resp.text, re.DOTALL)
                        for block in algo_blocks[:max_results]:
                            t_match = re.search(r'<h2[^>]*><a[^>]*>(.*?)</a>', block, re.DOTALL)
                            s_match = re.search(r'<div class="b_caption"[^>]*>.*?<p[^>]*>(.*?)</p>', block, re.DOTALL)
                            title = html.unescape(re.sub(r'<[^>]+>', '', t_match.group(1))).strip() if t_match else ""
                            snippet = html.unescape(re.sub(r'<[^>]+>', '', s_match.group(1))).strip() if s_match else ""
                            if snippet and len(snippet) > 20 and not any(bad in title.lower() for bad in ["youtube", "facebook", "twitter", "tiktok", "login", "top stories"]):
                                results.append({"title": title, "snippet": snippet, "source": "Google / Web Search"})
            except Exception as e:
                logger.debug(f"Bing search error: {e}")

        # 3. DuckDuckGo Lite
        if len(results) < 3:
            try:
                d_url = "https://lite.duckduckgo.com/lite/"
                d_headers = {**headers, "Content-Type": "application/x-www-form-urlencoded"}
                with httpx.Client(timeout=4.5, headers=d_headers, follow_redirects=True) as client:
                    resp = client.post(d_url, data={"q": cleaned_query})
                    if resp.status_code == 200:
                        snippets = re.findall(r'<td class="result-snippet"[^>]*>(.*?)</td>', resp.text, re.DOTALL)
                        titles = re.findall(r'<a class="result-link"[^>]*>(.*?)</a>', resp.text, re.DOTALL)
                        for i in range(min(len(snippets), max_results)):
                            t = html.unescape(re.sub(r'<[^>]+>', '', titles[i])).strip() if i < len(titles) else ""
                            s = html.unescape(re.sub(r'<[^>]+>', '', snippets[i])).strip()
                            if s and len(s) > 20:
                                results.append({"title": t, "snippet": s, "source": "Google / Web Search"})
            except Exception as e:
                logger.debug(f"DDG search error: {e}")

        # 4. Wikipedia REST API Summary for location entities
        loc_candidates = [
            w for w in re.findall(r'[A-Za-z0-9]+', query)
            if len(w) > 3 and w.lower() not in [
                "what", "level", "water", "ground", "groundwater", "depth", "rainfall", "recharge",
                "tell", "show", "find", "status", "give", "tips", "suggestion", "suggestions"
            ]
        ]
        for loc in loc_candidates[:2]:
            try:
                wiki_summary_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(loc.title())}"
                w_headers = {"User-Agent": "IngresAI/1.0 (info@ingres.gov.in)"}
                with httpx.Client(timeout=3.5, headers=w_headers) as client:
                    resp = client.get(wiki_summary_url)
                    if resp.status_code == 200:
                        data = resp.json()
                        extract = data.get("extract")
                        if extract:
                            results.append({
                                "title": data.get("title", loc),
                                "snippet": extract,
                                "source": "Wikipedia / Google"
                            })
            except Exception as e:
                logger.debug(f"Wiki summary error: {e}")

        return results

    @staticmethod
    def answer_with_web_search(query: str) -> Tuple[str, List[str]]:
        """
        Searches Google / the web for the user query and generates a direct, concise answer.
        Returns (response_text, sources_list).
        """
        search_results = WebSearchService.search_web(query)
        if not search_results:
            fallback_text = (
                f"I could not find data for '{query}' in the IN-GRES database, "
                "and online search did not return relevant information. "
                "Please verify the location or check your query."
            )
            return fallback_text, ["Google Search"]

        # If Gemini is configured and accessible, try synthesizing a concise answer
        global _gemini_disabled
        if settings.GEMINI_API_KEY and not globals().get("_gemini_disabled", False):
            try:
                import google.generativeai as genai
                genai.configure(api_key=settings.GEMINI_API_KEY)
                model = genai.GenerativeModel(
                    "gemini-1.5-flash",
                    system_instruction=(
                        "You are IN-GRES AI. The requested information was searched on Google / the web because it was not found in the local database.\n"
                        "Answer the user's specific question directly, accurately, and concisely based on the search results.\n"
                        "Rules:\n"
                        "1. Answer ONLY what the user asked. Keep answers direct and accurate.\n"
                        "2. If the user asked for suggestions or tips, provide clear actionable points/bullets.\n"
                        "3. If a numerical percentage, level, depth, rainfall, or value is found, state it clearly.\n"
                        "4. Do not invent facts."
                    )
                )
                context = "\n".join([f"- {r['title']}: {r['snippet']}" for r in search_results])
                prompt = (
                    f"User Question: {query}\n\n"
                    f"Google Search Results:\n{context}\n\n"
                    f"Direct, concise answer:"
                )
                resp = model.generate_content(prompt, request_options={"timeout": 2.5})
                if resp and resp.text:
                    out = resp.text.strip()
                    out = re.sub(r'^(Direct Answer|Answer|Concise Answer):\s*', '', out, flags=re.IGNORECASE)
                    return f"{out}\n\n*(Source: Google Search)*", ["Google Search", "Web Search"]
            except Exception as e:
                if "401" in str(e) or "authentication" in str(e).lower():
                    globals()["_gemini_disabled"] = True
                logger.warning(f"Gemini synthesis of search results skipped ({e}). Using NLP extractor.")

        # Smart NLP Extractor Fallback:
        q_tokens = [w.lower() for w in re.findall(r'[a-zA-Z0-9]+', query) if len(w) >= 3]
        best_item = None
        best_score = -100

        for r in search_results:
            snip = r["snippet"].lower()
            title = r.get("title", "").lower()
            
            # Skip noise
            if any(bad in title for bad in ["youtube", "error", "printer", "driver", "login", "password"]):
                continue

            score = 0
            for tok in q_tokens:
                if tok in snip:
                    score += 5
                if tok in title:
                    score += 3
                    
            if any(k in snip for k in ["groundwater", "water level", "depth", "m bgl", "mbgl", "water table", "cgwb", "recharge", "extraction", "aquifer", "meters below ground"]):
                score += 8
            if any(k in snip for k in ["rainfall", "precipitation", "monsoon"]):
                score += 4
                
            if score > best_score:
                best_score = score
                best_item = r

        if not best_item:
            best_item = search_results[0]

        best_snippet = best_item["snippet"]
        best_snippet = re.sub(r'(\s*[\.…]*\s*(?:Read more|More info|Learn more|Wikipedia)\b.*$)', '', best_snippet, flags=re.IGNORECASE).strip()
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', best_snippet) if len(s.strip()) > 10]
        
        if sentences:
            concise_text = " ".join(sentences[:3]).strip()
        else:
            concise_text = best_snippet
            
        concise_text = re.sub(r'(\.\.\.+|…+)\s*$', '.', concise_text).strip()
        if not concise_text.endswith((".", "!", "?")):
            concise_text += "."

        # If user asked for suggestions/tips
        if any(x in query.lower() for x in ["suggestion", "suggestions", "tip", "tips", "recommend", "recommendation", "how to"]):
            points = [
                "1. **Rainwater Harvesting (RWH)**: Construct check dams, percolation tanks, and recharge shafts to capture runoff.",
                "2. **Rooftop Rainwater Harvesting**: Implement rooftop filtration units to feed local recharge wells.",
                "3. **Micro-Irrigation**: Transition to drip and sprinkler systems to minimize agricultural extraction.",
                "4. **Rejuvenation of Water Bodies**: Desilt and deepen ponds, tanks, and check dams.",
                "5. **Crop Diversification**: Grow low-water-demand crops (millets, pulses) and apply mulching."
            ]
            concise_text += "\n\n### Recommended Actions & Tips:\n" + "\n".join(points)

        return f"{concise_text}\n\n*(Source: Google Search)*", ["Google Search", "Web Search"]
