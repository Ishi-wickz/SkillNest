from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("apps.accounts.urls")),
    path("api/", include("apps.marketplace.urls")),
    path("", TemplateView.as_view(template_name="home.html"), name="home"),
    path("login/", TemplateView.as_view(template_name="login.html"), name="login"),
    path("signup/", TemplateView.as_view(template_name="choose_account.html"), name="signup"),
    path("signup/details/", TemplateView.as_view(template_name="signup.html"), name="signup-details"),
    path("jobs/", TemplateView.as_view(template_name="jobs.html"), name="jobs"),
    path("jobs/new/", TemplateView.as_view(template_name="post_job.html"), name="post-job"),
    path("jobs/<int:pk>/", TemplateView.as_view(template_name="job_detail.html"), name="job-detail"),
    path("dashboard/", TemplateView.as_view(template_name="dashboard.html"), name="dashboard"),
]