from django.urls import path

from . import views

urlpatterns = [
    path("conversations/", views.ConversationListCreateView.as_view()),
    path("conversations/<int:pk>/messages/", views.MessagesView.as_view()),
    path("messages/unread/", views.UnreadCountView.as_view()),
]