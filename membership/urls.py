from django.urls import path

from .views import (
    MembershipAdminView,
    MembershipCheckAPIView,
    MembershipExportCSVView,
)


app_name = 'membership'

urlpatterns = [
    path('membership/check', MembershipCheckAPIView.as_view(), name='membership-check'),
    path('membership/admin', MembershipAdminView.as_view(), name='membership-admin'),
    path('membership/admin/export', MembershipExportCSVView.as_view(), name='membership-export'),
]
