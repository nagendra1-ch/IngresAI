def absolute_difference(val1: float, val2: float) -> float:
    """
    Computes absolute difference between two floats. Returns None if either is None.
    """
    if val1 is None or val2 is None:
        return None
    return round(abs(val1 - val2), 5)


def calculate_stage_of_extraction(recharge_ham: float, extraction_ham: float) -> float:
    """
    Priority 2 Calculation: dynamic stage computation.
    stage (%) = extraction / recharge * 100
    """
    if recharge_ham is None or extraction_ham is None:
        return None
    if recharge_ham <= 0:
        return 0.0
    return round((extraction_ham / recharge_ham) * 100, 2)

def convert_resource_unit(value: float, from_unit: str, to_unit: str = "ham") -> float:
    """
    Converts resource value between units (BCM, MCM, ham).
    BCM: Billion Cubic Meters
    MCM: Million Cubic Meters
    ham: Hectare Meters
    
    Conversions:
    1 BCM = 1,000,000,000 m3
    1 MCM = 1,000,000 m3
    1 ham = 10,000 m3
    
    So:
    1 BCM = 100,000 ham
    1 MCM = 100 ham
    """
    if value is None:
        return None
    
    u_from = from_unit.strip().lower()
    u_to = to_unit.strip().lower()
    
    if u_from == u_to:
        return value
        
    if u_from == "bcm" and u_to == "ham":
        return value * 100000.0
    elif u_from == "mcm" and u_to == "ham":
        return value * 100.0
    elif u_from == "ham" and u_to == "bcm":
        return value / 100000.0
    elif u_from == "ham" and u_to == "mcm":
        return value / 100.0
        
    raise ValueError(f"Unsupported unit conversion from {from_unit} to {to_unit}")

def validate_depth(value) -> bool:
    """
    Validates depth. Must be numeric, positive, and NOT represented as percentage.
    """
    if value is None:
        return True
    try:
        val = float(value)
        return val >= 0
    except (ValueError, TypeError):
        return False

def validate_stage(value) -> bool:
    """
    Validates stage of extraction. Must be numeric percentage.
    """
    if value is None:
        return True
    try:
        val = float(value)
        return val >= 0
    except (ValueError, TypeError):
        return False

def validate_rainfall(value) -> bool:
    """
    Validates rainfall in mm. Must be numeric and non-negative.
    """
    if value is None:
        return True
    try:
        val = float(value)
        return val >= 0
    except (ValueError, TypeError):
        return False

def validate_resource_value(value) -> bool:
    """
    Validates recharge/extraction volumetric metrics.
    """
    if value is None:
        return True
    try:
        val = float(value)
        return val >= 0
    except (ValueError, TypeError):
        return False

def format_depth(value: float) -> float:
    """
    Formats depth to 2 decimal places.
    """
    if value is None:
        return None
    return round(value, 2)

def format_resource(value: float) -> float:
    """
    Formats recharge/extraction to 2 decimal places.
    """
    if value is None:
        return None
    return round(value, 2)

def format_rainfall(value: float) -> float:
    """
    Formats rainfall to 1 decimal place.
    """
    if value is None:
        return None
    return round(value, 1)
