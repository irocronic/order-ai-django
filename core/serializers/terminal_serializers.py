# core/serializers/terminal_serializers.py
from rest_framework import serializers
from ..models import PaymentTerminal

class PaymentTerminalSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentTerminal
        fields = [
            'id', 
            'provider_terminal_id', 
            'name', 
            'status', 
            'business'
        ]
        read_only_fields = ('business',)