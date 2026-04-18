from django.urls import path

from .views import MembershipCheckAPIView


app_name = 'membership'

urlpatterns = [
    path('membership/check', MembershipCheckAPIView.as_view(), name='membership-check'),
]
