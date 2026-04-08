from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .services import CustomerNotFoundError, get_membership_status


class MembershipCheckAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        phone_number = request.query_params.get('phoneNumber')

        if not phone_number:
            return Response(
                {'error': 'phoneNumber is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            membership_status = get_membership_status(phone_number)
        except CustomerNotFoundError:
            return Response(
                {'error': 'Customer tidak ditemukan'},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(membership_status, status=status.HTTP_200_OK)
