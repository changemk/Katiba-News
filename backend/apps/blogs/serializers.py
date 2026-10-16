from rest_framework import serializers
from .models import BlogPost, Comment, Like

class CommentSerializer(serializers.ModelSerializer):
    user_username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = Comment
        fields = ['id', 'post', 'user', 'user_username', 'content', 'created_at', 'updated_at']
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']


class LikeSerializer(serializers.ModelSerializer):
    user_username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = Like
        fields = ['id', 'post', 'user', 'user_username', 'created_at']
        read_only_fields = ['id', 'user', 'created_at']


class BlogPostSerializer(serializers.ModelSerializer):
    author_username = serializers.CharField(source='author.username', read_only=True)
    # Nesting the serializers allows us to see comment lists and like totals automatically
    comments = CommentSerializer(many=True, read_only=True)
    likes_count = serializers.IntegerField(source='likes.count', read_only=True)

    class Meta:
        model = BlogPost
        fields = [
            'id', 
            'title', 
            'slug', 
            'content', 
            'author', 
            'author_username', 
            'likes_count', 
            'comments', 
            'created_at', 
            'updated_at'
        ]
        read_only_fields = ['id', 'slug', 'likes_count', 'comments', 'created_at', 'updated_at']
