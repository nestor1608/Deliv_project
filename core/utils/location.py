# core/utils/location.py
import math
from decimal import Decimal

def calculate_distance(lat1, lon1, lat2, lon2):
    """
    Calcular distancia entre dos puntos usando fórmula de Haversine
    Retorna distancia en kilómetros
    """
    # Convertir a radianes
    lat1, lon1, lat2, lon2 = map(math.radians, [float(lat1), float(lon1), float(lat2), float(lon2)])
    
    # Fórmula de Haversine
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    r = 6371  # Radio de la Tierra en km
    return c * r

def calculate_delivery_fee(distance_km, base_fee=150):
    """
    Calcular tarifa de delivery basada en distancia
    """
    if distance_km <= 2:
        return Decimal(str(base_fee))
    elif distance_km <= 5:
        return Decimal(str(base_fee + (distance_km - 2) * 50))
    else:
        return Decimal(str(base_fee + 150 + (distance_km - 5) * 75))

def find_nearby_vendors(customer_lat, customer_lon, radius_km=10):
    """
    Encontrar comercios cercanos al cliente
    """
    from vendors.models import Vendor
    
    nearby_vendors = []
    vendors = Vendor.objects.filter(status='approved', is_open=True)
    
    for vendor in vendors:
        distance = calculate_distance(
            customer_lat, customer_lon,
            vendor.latitude, vendor.longitude
        )
        if distance <= radius_km:
            nearby_vendors.append({
                'vendor': vendor,
                'distance': round(distance, 2)
            })
    
    # Ordenar por distancia
    nearby_vendors.sort(key=lambda x: x['distance'])
    return nearby_vendors

