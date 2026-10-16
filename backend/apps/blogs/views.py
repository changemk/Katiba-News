from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import BlogPost, Comment, Like
from .serializers import BlogPostSerializer, CommentSerializer, LikeSerializer

class BlogPostListCreateAPIView(generics.ListCreateAPIView):
    """
    Handles GET /api/blogs/ (List all community opinions)
    Handles POST /api/blogs/ (Create a new public opinion post)
    """
    queryset = BlogPost.objects.all().order_by('-created_at')
    serializer_class = BlogPostSerializer

    def perform_create(self, serializer):
        # Automatically save the currently active session user profile as the author
        serializer.save(author=self.request.user)


class BlogPostDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    """
    Handles GET /api/blogs/<slug>/ (Read a specific blog post)
    Handles PUT/PATCH /api/blogs/<slug>/ (Modify blog content details)
    Handles DELETE /api/blogs/<slug>/ (Remove a post entry entirely)
    """
    queryset = BlogPost.objects.all()
    serializer_class = BlogPostSerializer
    lookup_field = 'slug'


class CommentListCreateAPIView(generics.ListCreateAPIView):
    """
    Handles GET /api/blogs/<slug>/comments/ (Fetch all discussion items for a post)
    Handles POST /api/blogs/<slug>/comments/ (Submit a new conversation reply)
    """
    serializer_class = CommentSerializer

    def get_queryset(self):
        return Comment.objects.filter(post__slug=self.kwargs['slug']).order_by('created_at')

    def perform_create(self, serializer):
        blog_post = BlogPost.objects.get(slug=self.kwargs['slug'])
        serializer.save(user=self.request.user, post=blog_post)


class LikeToggleAPIView(APIView):
    """
    Handles POST /api/blogs/<slug>/like/ (Add or remove user like metrics)
    """
    def post(self, request, slug):
        blog_post = BlogPost.objects.get(slug=slug)
        like_filter = Like.objects.filter(post=blog_post, user=request.user)

        if like_filter.exists():
            # If the user already liked it, clicking again removes the like record
            like_filter.delete()
            return Response({"detail": "Like removed successfully."}, status=status.HTTP_200_OK)
        
        # Otherwise, insert a unique entry matching this user profile
        Like.objects.create(post=blog_post, user=request.user)
        return Response({"detail": "Like registered successfully."}, status=status.HTTP_201_CREATED)
