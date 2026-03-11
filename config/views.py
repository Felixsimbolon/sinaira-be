"""
Auth views for API (e.g. obtain token for Postman).
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from django.contrib.auth import authenticate


@api_view(['POST'])
@permission_classes([AllowAny])
def obtain_token(request):
    """
    POST with username + password (JSON or form) to get an auth token.
    Use in Postman: Authorization header "Token <token>".
    """
    username = request.data.get('username') or request.POST.get('username')
    password = request.data.get('password') or request.POST.get('password')

    if not username or not password:
        return Response(
            {'error': 'Provide username and password.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user = authenticate(request, username=username, password=password)
    if user is None:
        return Response(
            {'error': 'Invalid credentials.'},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    token, _ = Token.objects.get_or_create(user=user)
    return Response({'token': token.key}, status=status.HTTP_200_OK)
