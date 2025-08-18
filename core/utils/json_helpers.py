# core/utils/json_helpers.py

from decimal import Decimal

def convert_decimals_to_strings(obj):
    """
    Veri içinde Decimal tipinde alanlar varsa bunları string'e çevirir.
    Bu merkezi fonksiyon, döngüsel import hatalarını önler.
    """
    if isinstance(obj, list):
        return [convert_decimals_to_strings(i) for i in obj]
    elif isinstance(obj, dict):
        return {k: convert_decimals_to_strings(v) for k, v in obj.items()}
    elif isinstance(obj, Decimal):
        return str(obj)
    return obj