from rest_framework import serializers
from .models import Article

class ArticleSerializer(serializers.ModelSerializer):
    # This grabs the author's real username text string instead of just showing an ID number
    author_username = serializers.CharField(source='author.username', read_only=True)

    class Meta:
        model = Article
        fields = [
            'id', 
            'title', 
            'slug', 
            'content', 
            'status', 
            'author', 
            'author_username', 
            'created_at', 
            'updated_at'
        ]
        # System-managed fields are locked to read-only format
        read_only_fields = ['id', 'slug', 'created_at', 'updated_at']
