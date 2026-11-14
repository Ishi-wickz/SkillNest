from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("apps.accounts.urls")),
    path("api/", include("apps.marketplace.urls")),
    path("api/", include("apps.chat.urls")),
    path("", TemplateView.as_view(template_name="home.html"), name="home"),
    path("about/", TemplateView.as_view(template_name="about.html"), name="about"),
    path("login/", TemplateView.as_view(template_name="login.html"), name="login"),
    path("forgot-password/", TemplateView.as_view(template_name="forgot_password.html"), name="forgot-password"),
    path("reset-password/", TemplateView.as_view(template_name="reset_password.html"), name="reset-password"),
    path("verify-email/", TemplateView.as_view(template_name="verify_email.html"), name="verify-email"),
    path("signup/", TemplateView.as_view(template_name="choose_account.html"), name="signup"),
    path("signup/details/", TemplateView.as_view(template_name="signup.html"), name="signup-details"),
    path("jobs/", TemplateView.as_view(template_name="jobs.html"), name="jobs"),
    path("jobs/new/", TemplateView.as_view(template_name="post_job.html"), name="post-job"),
    path("jobs/<int:pk>/", TemplateView.as_view(template_name="job_detail.html"), name="job-detail"),
    path("dashboard/", TemplateView.as_view(template_name="dashboard.html"), name="dashboard"),
    path("messages/", TemplateView.as_view(template_name="messages.html"), name="messages"),
    path("profile/", TemplateView.as_view(template_name="profile.html"), name="profile"),
    path("talent/", TemplateView.as_view(template_name="talent.html"), name="talent"),
    path("talent/<int:pk>/", TemplateView.as_view(template_name="talent_detail.html"), name="talent-detail"),
]