
def round_and_format(value: float) -> str:
    """
    Rounds a float to 2 decimal places and formats it as a string.
    If the rounded value is -0.00, it returns 0.00 (removes the negative sign).
    """
    try:
        val = float(value)
        rounded_val = round(val, 2)
        
        # Check for negative zero after rounding
        if rounded_val == 0.0:
            return 0.0
            
        return f"{rounded_val:.2f}"
    except (ValueError, TypeError):
        return str(value)
