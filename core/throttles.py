from rest_framework.throttling import UserRateThrottle

class LocationRateThrottle(UserRateThrottle):
    rate = '20/min'
    scope = 'location_updates'
