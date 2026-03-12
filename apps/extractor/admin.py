from django.contrib import admin
from .models import JobPosting, NewsArticle, SocialSignal, CommunityPost, TrendData, AIReport


@admin.register(JobPosting)
class JobPostingAdmin(admin.ModelAdmin):
    list_display = ('title', 'source', 'sector', 'training_type_match', 'relevance_score', 'extracted_at')
    list_filter = ('source', 'sector', 'training_type_match')
    search_fields = ('title', 'raw_description')


@admin.register(NewsArticle)
class NewsArticleAdmin(admin.ModelAdmin):
    list_display = ('title', 'source', 'relevance_score', 'published_at')
    list_filter = ('source',)
    search_fields = ('title', 'summary')


@admin.register(SocialSignal)
class SocialSignalAdmin(admin.ModelAdmin):
    list_display = ('platform', 'content_summary', 'sector', 'sentiment', 'detected_at')
    list_filter = ('platform', 'sentiment', 'sector')


@admin.register(CommunityPost)
class CommunityPostAdmin(admin.ModelAdmin):
    list_display = ('platform', 'title', 'subreddit', 'score', 'comments_count', 'relevance_score', 'published_at')
    list_filter = ('platform', 'sector', 'training_type_match')
    search_fields = ('title', 'content_summary')


@admin.register(TrendData)
class TrendDataAdmin(admin.ModelAdmin):
    list_display = ('source', 'keyword', 'value', 'region', 'category', 'measured_at')
    list_filter = ('source', 'category', 'region')
    search_fields = ('keyword',)


@admin.register(AIReport)
class AIReportAdmin(admin.ModelAdmin):
    list_display = ('title', 'report_type', 'generated_at')
    list_filter = ('report_type',)
