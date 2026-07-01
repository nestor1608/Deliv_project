# core/utils/payments.py
import requests
import json
from django.conf import settings
from decimal import Decimal

class MercadoPagoService:
    """Servicio para integración con MercadoPago"""
    
    def __init__(self):
        self.access_token = settings.PAYMENT_SETTINGS['MERCADOPAGO']['ACCESS_TOKEN']
        self.base_url = 'https://api.mercadopago.com'
    
    def create_payment(self, amount, description, payment_method_id, email):
        """Crear pago en MercadoPago"""
        url = f"{self.base_url}/v1/payments"
        
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
        
        data = {
            'transaction_amount': float(amount),
            'description': description,
            'payment_method_id': payment_method_id,
            'payer': {
                'email': email
            }
        }
        
        response = requests.post(url, headers=headers, data=json.dumps(data))
        return response.json()
    
    def get_payment_status(self, payment_id):
        """Consultar estado de pago"""
        url = f"{self.base_url}/v1/payments/{payment_id}"
        
        headers = {
            'Authorization': f'Bearer {self.access_token}'
        }
        
        response = requests.get(url, headers=headers)
        return response.json()

class TripPricingService:
    """Servicio para calcular precios de viajes"""
    
    BASE_FARE = Decimal('200.00')  # Tarifa base
    RATE_PER_KM = Decimal('80.00')  # Por kilómetro
    RATE_PER_MINUTE = Decimal('15.00')  # Por minuto
    
    @classmethod
    def calculate_trip_price(cls, distance_km, duration_minutes, surge_multiplier=1.0):
        """Calcular precio de viaje"""
        distance_fare = Decimal(str(distance_km)) * cls.RATE_PER_KM
        time_fare = Decimal(str(duration_minutes)) * cls.RATE_PER_MINUTE
        
        subtotal = cls.BASE_FARE + distance_fare + time_fare
        total = subtotal * Decimal(str(surge_multiplier))
        
        return {
            'base_fare': cls.BASE_FARE,
            'distance_fare': distance_fare,
            'time_fare': time_fare,
            'subtotal': subtotal,
            'surge_multiplier': Decimal(str(surge_multiplier)),
            'total': total.quantize(Decimal('0.01'))
        }