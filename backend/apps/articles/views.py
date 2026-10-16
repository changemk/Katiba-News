from rest_framework import generics, permissions
from .models import Article
from .serializers import ArticleSerializer

class ArticleListCreateView(generics.ListCreateAPIView):
    """
    Handles GET /api/articles/ (List all published updates)
    Handles POST /api/articles/ (Submit a new constitutional draft)
    """
    serializer_class = ArticleSerializer

    def get_queryset(self):
        # Normal citizens visiting the platform should only see 'published' updates
        if self.request.method == 'GET':
            return Article.objects.filter(status='published').order_by('-created_at')
        # Authors and staff can see all items (including drafts) when preparing edits
        return Article.objects.all().order_by('-created_at')

    def perform_create(self, serializer):
        # Automatically attach the currently logged-in user profile as the author
        serializer.save(author=self.request.user)


class ArticleDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Handles GET /api/articles/<slug>/ (Read a specific article via its clean link text)
    Handles PUT/PATCH /api/articles/<slug>/ (Modify article content details)
    Handles DELETE /api/articles/<slug>/ (Remove an article entry entirely)
    """
    queryset = Article.objects.all()
    serializer_class = ArticleSerializer
    lookup_field = 'slug'  # Tells Django to find records matching their unique URL strings
