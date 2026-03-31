from django.urls import path
from .views import *
from django.views.generic import DetailView, TemplateView
from .models import Rabota

app_name = 'home'

urlpatterns = [
    path('', home, name='home'),
    path('otziv/', OtzivListView.as_view(), name='otzivs'),
    path('otziv/<int:pk>/', OtzivDetailView.as_view(), name='otziv-detail'),
    path('otzivs/create/', OtzivCreateView.as_view(), name='otziv-create'),
    path('otziv/<int:otziv_id>/comment/', add_comment_to_otziv, name='add-comment'),
    path('otziv/<int:otziv_id>/comments/', get_comments_for_otziv, name='get-comments'),
    path('contact/', contact_form, name='contact-form'),
    # Detail view для Rabota
    path('rabota/<int:pk>/', DetailView.as_view(model=Rabota, template_name='home/rabota_detail.html', context_object_name='rabota'), name='rabota'),
    # Страницы услуг
    path('services/', ServiceListView.as_view(), name='service-list'),
    path('services/<int:pk>/', ServiceDetailView.as_view(), name='service-detail'),
    # Страницы дополнительных услуг
    path('extra-services/', StandaloneExtraServiceListView.as_view(), name='extra-service-list'),
    path('extra-services/<int:pk>/', StandaloneExtraServiceDetailView.as_view(), name='extra-service-detail'),
    # Система заказов
    path('cart/', cart_view, name='cart'),
    path('cart/add/', add_to_cart, name='add-to-cart'),
    path('cart/update/<int:item_id>/', update_cart_item, name='update-cart-item'),
    path('cart/remove/<int:item_id>/', remove_from_cart, name='remove-from-cart'),
    path('checkout/', checkout, name='checkout'),
    path('order/<int:order_id>/questionnaire/', order_questionnaire, name='order_questionnaire'),
    path('order/<int:order_id>/success/', order_success, name='order_success'),
    path('order/<int:order_id>/', order_detail, name='order_detail'),
    # YooKassa оплата
    path('order/<int:order_id>/pay/', pay_order, name='order_pay'),
    path('yookassa/webhook/', yookassa_webhook, name='yookassa_webhook'),
    path('cookie-consent/', cookie_consent, name='cookie-consent'),
    path('privacy-policy/', privacy_policy, name='privacy_policy'),
    path('payment/success/<int:order_id>/', payment_success, name='payment_success'),
    path('legal-info/', legal_info, name='legal_info'),
    path('legal-info/edit/', edit_legal_info, name='edit_legal_info'),
    
    # ==================== ЛИЧНЫЙ КАБИНЕТ ====================
    # Регистрация и вход
    path('customer/register/', customer_register, name='customer_register'),
    path('customer/login/', customer_login, name='customer_login'),
    path('customer/vkid/complete/', customer_vkid_complete, name='customer_vkid_complete'),
    path('customer/logout/', customer_logout, name='customer_logout'),
    
    # Личный кабинет заказчика
    path('customer/dashboard/', customer_dashboard, name='customer_dashboard'),
    path('customer/profile/', customer_profile, name='customer_profile'),
    path('customer/profile/edit/', customer_edit_profile, name='customer_edit_profile'),
    path('customer/orders/', customer_orders, name='customer_orders'),
    path('customer/order/<int:order_id>/', customer_order_detail, name='customer_order_detail'),
    
    # Админ панель для заказов
    path('admin/orders/', admin_orders, name='admin_orders'),
    path('admin/order/<int:order_id>/', admin_order_detail, name='admin_order_detail'),

    # Дашборд Портфолио
    path('portfolio/dashboard/', PortfolioDashboardView.as_view(), name='portfolio_dashboard'),
    path('portfolio/create/', RabotaCreateView.as_view(), name='portfolio_create'),
    path('portfolio/<int:pk>/edit/', RabotaUpdateView.as_view(), name='portfolio_update'),
]
