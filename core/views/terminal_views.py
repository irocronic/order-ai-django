# core/views/terminal_views.py
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from ..models import PaymentTerminal
from ..serializers import PaymentTerminalSerializer
from ..utils.order_helpers import get_user_business

class PaymentTerminalViewSet(viewsets.ModelViewSet):
    """
    İşletmeye ait ödeme terminallerini yönetmek için API.
    """
    serializer_class = PaymentTerminalSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user_business = get_user_business(self.request.user)
        if user_business:
            return PaymentTerminal.objects.filter(business=user_business)
        return PaymentTerminal.objects.none()

    def perform_create(self, serializer):
        user_business = get_user_business(self.request.user)
        serializer.save(business=user_business)