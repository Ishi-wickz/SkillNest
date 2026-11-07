from django.contrib import admin
from .models import Category, Skill, Job, Proposal, Review


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ["name"]


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    # Your moderation tool: filter by status, search, cancel bad listings
    list_display = ["title", "client", "category", "budget_amount", "currency", "status", "created_at"]
    list_filter = ["status", "category", "budget_type"]
    search_fields = ["title", "client__email"]
    list_select_related = ["client", "category"]
    filter_horizontal = ["skills"]


@admin.register(Proposal)
class ProposalAdmin(admin.ModelAdmin):
    list_display = ["job", "freelancer", "bid_amount", "status", "created_at"]
    list_filter = ["status"]
    list_select_related = ["job", "freelancer"]


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ["job", "reviewer", "reviewee", "rating", "created_at"]
