from django.contrib import admin
from .models import Company, SurveyResponse, TrainingNeed, CriticalIssueRanking


class TrainingNeedInline(admin.TabularInline):
    model = TrainingNeed
    extra = 0


class CriticalIssueRankingInline(admin.TabularInline):
    model = CriticalIssueRanking
    extra = 0


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('name', 'sector', 'size', 'location', 'created_at')
    list_filter = ('sector', 'size')
    search_fields = ('name', 'email')


@admin.register(SurveyResponse)
class SurveyResponseAdmin(admin.ModelAdmin):
    list_display = ('company', 'ai_maturity', 'is_complete', 'submitted_at')
    list_filter = ('is_complete', 'ai_maturity', 'budget')
    inlines = [TrainingNeedInline, CriticalIssueRankingInline]
    readonly_fields = ('share_token', 'created_at', 'updated_at')
