def normalize_period_with_year(period: str, year: int) -> str:
    if not period:
        return str(year)
        
    period_str = str(period).strip()
    year_str = str(year).strip()
    
    # If period already contains the year, do not append it again
    if year_str in period_str:
        return period_str
        
    return f"{period_str} {year_str}"

def validate_and_normalize_metadata(wl_src: str, obs_period: str, obs_year: int) -> str:
    # Rule 10 Automated Validation
    src_str = str(wl_src or "")
    period_str = str(obs_period or "")
    
    if "January 2026" in src_str:
        period_str = "January"
        obs_year = 2026
    elif "February 2026" in src_str:
        period_str = "February"
        obs_year = 2026
    elif "August 2026" in src_str:
        period_str = "August"
        obs_year = 2026
    elif "Pre-Monsoon 2025" in src_str:
        period_str = "Pre-Monsoon"
        obs_year = 2025
    elif "Post-Monsoon 2025" in src_str:
        period_str = "Post-Monsoon"
        obs_year = 2025
        
    return normalize_period_with_year(period_str, obs_year)
