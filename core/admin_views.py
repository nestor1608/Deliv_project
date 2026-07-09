from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes

from .analytics import get_dashboard_data

@extend_schema(
    summary='Admin Dashboard Analytics',
    description='Obtiene métricas agregadas para el dashboard administrativo.',
    tags=['admin'],
    parameters=[
        OpenApiParameter(name='days', type=OpenApiTypes.INT, description='Días a analizar (default: 30)'),
    ],
)
@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def admin_dashboard(request):
    days = int(request.query_params.get('days', 30))
    data = get_dashboard_data(days)
    return Response(data)
