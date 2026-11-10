from django.urls import path

from . import views

urlpatterns = [
    path("categories/", views.CategoryListView.as_view()),
    path("skills/", views.SkillListView.as_view()),
    path("jobs/", views.JobListCreateView.as_view()),
    path("jobs/mine/", views.MyJobsView.as_view()),
    path("jobs/<int:pk>/", views.JobDetailView.as_view()),
    path("jobs/<int:pk>/complete/", views.CompleteJobView.as_view()),
    path("jobs/<int:job_id>/reviews/", views.JobReviewView.as_view()),
    path("jobs/<int:job_id>/proposals/", views.JobProposalsView.as_view()),
    path("proposals/mine/", views.MyProposalsView.as_view()),
    path("proposals/<int:pk>/accept/", views.AcceptProposalView.as_view()),
    path("proposals/<int:pk>/reject/", views.RejectProposalView.as_view()),
]