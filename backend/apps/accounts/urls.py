from django.urls import path

from . import talent, views

urlpatterns = [
    path("auth/csrf/", views.CsrfView.as_view()),
    path("auth/signup/", views.SignupView.as_view()),
    path("auth/login/", views.LoginView.as_view()),
    path("auth/logout/", views.LogoutView.as_view()),
    path("me/", views.MeView.as_view()),
    path("profile/", views.MyProfileView.as_view()),
    path("talent/", talent.TalentListView.as_view()),
    path("talent/<int:pk>/", talent.TalentDetailView.as_view()),
]