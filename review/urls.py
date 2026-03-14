from django.urls import path

from .views import ReviewContextView, ReviewCreateView, ReviewDetailView, ReviewListView

app_name = "review"

urlpatterns = [
    path("reviews/", ReviewCreateView.as_view(), name="review-create"),
    path("reviews/context/", ReviewContextView.as_view(), name="review-context"),
    path("reviews/list/", ReviewListView.as_view(), name="review-list"),
    path("reviews/<int:pk>/", ReviewDetailView.as_view(), name="review-detail"),
]
