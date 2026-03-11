from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import AccountDetailView, AccountListCreateView, CurrentUserView, LoginView

urlpatterns = [
    # Authentication
    path("auth/login/", LoginView.as_view(), name="auth-login"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),

    # Current user profile (must be before <int:pk> to avoid "me" matching)
    path("accounts/me/", CurrentUserView.as_view(), name="current-user"),

    # Account management
    path("accounts/", AccountListCreateView.as_view(), name="account-list-create"),
    path("accounts/<int:pk>/", AccountDetailView.as_view(), name="account-detail"),
]
