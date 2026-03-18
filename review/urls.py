from django.urls import path

from .views import ReviewCollectionView, ReviewContextView, ReviewDetailView

app_name = "review"

urlpatterns = [
    path("reviews/", ReviewCollectionView.as_view(), name="review-collection"),
    path("reviews/context/", ReviewContextView.as_view(), name="review-context"),
    path("reviews/list/", ReviewCollectionView.as_view(), name="review-list"),
    path("reviews/<int:pk>/", ReviewDetailView.as_view(), name="review-detail"),
]
