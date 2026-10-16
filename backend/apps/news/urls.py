from rest_framework.routers import DefaultRouter
from .api import LeadViewSet, SourceViewSet, AssignmentViewSet, AuthorViewSet, TopicRuleViewSet

router = DefaultRouter()
router.register('leads', LeadViewSet, basename='news-lead')
router.register('sources', SourceViewSet, basename='news-source')
router.register('assignments', AssignmentViewSet, basename='news-assignment')
router.register('authors', AuthorViewSet, basename='news-author')
router.register('topic-rules', TopicRuleViewSet, basename='news-topic-rule')
urlpatterns = router.urls
