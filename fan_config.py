"""Fan speed configurations"""

def get_normal_speed(name: str) -> int:
    """Get normal speed based on device name"""
    name_lower = name.lower()
    if 'exaust' in name_lower:
        return 40  # Exhaust fans run at 40%
    return 45  # Regular fans run at 45%

def get_normalize_display_text() -> str:
    """Get display text for normalize button showing both speeds"""
    return "Normalize (E:40%/F:45%)"
