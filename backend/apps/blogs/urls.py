from django.urls import path
from .views import (
    BlogPostListCreateAPIView, 
    BlogPostDetailAPIView, 
    CommentListCreateAPIView, 
    LikeToggleAPIView
)

urlpatterns = [
    # Matches: GET /api/blogs/ and POST /api/blogs/
    path("", BlogPostListCreateAPIView.as_view(), name="blog-list-create"),
    
    # Matches: GET, PUT, PATCH, DELETE /api/blogs/<slug>/
    path("<slug:slug>/", BlogPostDetailAPIView.as_view(), name="blog-detail"),
    
    # Matches: GET /api/blogs/<slug>/comments/ and POST /api/blogs/<slug>/comments/
    path("<slug:slug>/comments/", CommentListCreateAPIView.as_view(), name="blog-comment-list-create"),
    
    # Matches: POST /api/blogs/<slug>/like/
    path("<slug:slug>/like/", LikeToggleAPIView.as_view(), name="blog-like-toggle"),
]
