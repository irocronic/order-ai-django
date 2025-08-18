# core/exceptions.py

from rest_framework.views import exception_handler
from rest_framework.exceptions import AuthenticationFailed

def custom_exception_handler(exc, context):
    """
    Django REST Framework'ün varsayılan hata işleyicisini genişletir.
    """
    # 1. DRF'in standart hata yanıtını oluşturmasını sağla.
    response = exception_handler(exc, context)

    # 2. Eğer bir yanıt oluşturulduysa ve hata tipi `AuthenticationFailed` ise devam et.
    if response is not None and isinstance(exc, AuthenticationFailed):
        
        # 3. Hata nesnesinden özel hata kodunu/kodlarını al.
        auth_code = exc.get_codes()
        
        # ++++++++++++++++++++++++++++++ YENİ VE SAĞLAM KOD ++++++++++++++++++++++++++++++
        # 'code' anahtarını güvenli bir şekilde al.
        # InvalidToken gibi hatalarda exc.detail bir sözlük olabilir.
        if isinstance(exc.detail, dict) and 'code' in exc.detail:
            response.data['code'] = exc.detail['code']
        # Diğer AuthenticationFailed hatalarında get_codes() genellikle bir liste veya string döner.
        elif isinstance(auth_code, str):
            response.data['code'] = auth_code
        elif isinstance(auth_code, list) and auth_code:
            response.data['code'] = auth_code[0]
        # Diğer tüm durumlarda genel bir hata kodu ata ve çökmesini engelle.
        else:
            response.data['code'] = 'authentication_failed'
        # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

    # 5. Değiştirilmiş (veya değiştirilmemiş) yanıtı döndür.
    return response