from django.urls import path

from identity_auth.oauth_views import customer_oauth_callback, customer_oauth_start
from identity_auth import views

app_name = 'identity_auth'

urlpatterns = [
    path('customer/register/', views.customer_register, name='customer_register'),
    path('customer/login/', views.customer_login, name='customer_login'),
    path('customer/vkid/complete/', views.customer_vkid_complete, name='customer_vkid_complete'),
    path('customer/oauth/<str:provider>/start/', customer_oauth_start, name='customer_oauth_start'),
    path('customer/oauth/<str:provider>/callback/', customer_oauth_callback, name='customer_oauth_callback'),
    path('customer/logout/', views.customer_logout, name='customer_logout'),
    path(
        'manage/auth/oauth/',
        views.admin_customer_auth_oauth_settings,
        name='admin_customer_auth_oauth_settings',
    ),
]
