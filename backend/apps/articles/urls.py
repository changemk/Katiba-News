from django.urls import path
from .views import ArticleListCreateView, ArticleDetailView

urlpatterns = [
    # Matches: GET /api/articles/ and POST /api/articles/
    path("", ArticleListCreateView.as_view(), name="article-list-create"),
    
    # Matches: GET, PUT, PATCH, DELETE /api/articles/<slug>/
    path("<slug:slug>/", ArticleDetailView.as_view(), name="article-detail"),
]
