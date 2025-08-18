# core/utils/notifications.py

import logging
from asgiref.sync import async_to_sync
from decimal import Decimal

logger = logging.getLogger(__name__)

def _convert_decimals_to_strings(obj):
    """ Veri içinde Decimal tipinde alanlar varsa bunları string'e çevirir. """
    if isinstance(obj, list):
        return [_convert_decimals_to_strings(i) for i in obj]
    elif isinstance(obj, dict):
        return {k: _convert_decimals_to_strings(v) for k, v in obj.items()}
    elif isinstance(obj, Decimal):
        return str(obj)
    return obj

def send_websocket_notification(business_id, event_type, payload):
    """
    Belirtilen işletme odasına WebSocket üzerinden bildirim gönderir.
    """
    if not business_id:
        logger.error(f"[WEBSOCKET] Bildirim gönderilemedi: business_id eksik. Event: {event_type}")
        return

    try:
        from makarna_project.asgi import sio
        if sio is None:
            logger.error("[WEBSOCKET] Bildirim gönderilemedi: Socket.IO sunucusu (sio) bulunamadı.")
            return
    except ImportError:
        logger.error("[WEBSOCKET] Bildirim gönderilemedi: makarna_project.asgi.sio import edilemedi.")
        return

    room_name = f'business_{business_id}'
    cleaned_payload = _convert_decimals_to_strings(payload)
    
    logger.info(f"--> [WEBSOCKET] Bildirim Gönderiliyor: Oda: {room_name}, Event: {event_type}, Payload: {cleaned_payload}")
    async_to_sync(sio.emit)(event_type, cleaned_payload, room=room_name)