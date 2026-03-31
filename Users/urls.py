from django.urls import path
from . import views

app_name = 'users'

urlpatterns = [
    path('telegram-login/', views.telegram_login, name='telegram_login'),
    path('profile/', views.profile, name='profile'),
] 