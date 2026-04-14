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
    path('order/<int:order_id>/pay/mock/', pay_order_mock, name='order_pay_mock'),
    path('yookassa/webhook/', yookassa_webhook, name='yookassa_webhook'),
    path('cookie-consent/', cookie_consent, name='cookie-consent'),
    path('privacy-policy/', privacy_policy, name='privacy_policy'),
    path('payment/success/<int:order_id>/', payment_success, name='payment_success'),
    path('legal-info/', legal_info, name='legal_info'),
    path('legal-info/edit/', edit_legal_info, name='edit_legal_info'),
    
    # ==================== ЛИЧНЫЙ КАБИНЕТ ====================
    # Вход, регистрация, OAuth — см. identity_auth.urls (подключено в ALUKINTERLAB/urls.py).

    # Личный кабинет заказчика
    path('customer/dashboard/', customer_dashboard, name='customer_dashboard'),
    path('customer/profile/', customer_profile, name='customer_profile'),
    path('customer/profile/edit/', customer_edit_profile, name='customer_edit_profile'),
    path('customer/orders/', customer_orders, name='customer_orders'),
    path('customer/order/<int:order_id>/', customer_order_detail, name='customer_order_detail'),
    path('customer/support/', customer_support, name='customer_support'),
    path('customer/support/<int:thread_id>/', customer_support_thread, name='customer_support_thread'),
    
    # Внутренние дашборды под /manage/ — не использовать префикс /admin/ (коллизия с Django Admin).
    path('manage/support/', admin_support_list, name='admin_support_list'),
    path('manage/support/<int:thread_id>/', admin_support_thread, name='admin_support_thread'),
    path('manage/orders/', admin_orders, name='admin_orders'),
    path('manage/order/<int:order_id>/', admin_order_detail, name='admin_order_detail'),

    # Дашборд Портфолио
    path('portfolio/dashboard/', PortfolioDashboardView.as_view(), name='portfolio_dashboard'),
    path('portfolio/create/', RabotaCreateView.as_view(), name='portfolio_create'),
    path('portfolio/<int:pk>/edit/', RabotaUpdateView.as_view(), name='portfolio_update'),
    path('portfolio/<int:pk>/toggle-visibility/', portfolio_toggle_visibility, name='portfolio_toggle_visibility'),
    
    # ==================== ПАНЕЛЬ УПРАВЛЕНИЯ (/manage/) ====================
    path('manage/statistics/dashboard/', admin_statistics_dashboard, name='admin_statistics_dashboard'),
    path('manage/statistics/subscribers/', admin_subscribers_view, name='admin_subscribers'),
    path('manage/statistics/purchases/', admin_purchases_view, name='admin_purchases'),
    path('manage/statistics/transactions/', admin_transactions_view, name='admin_transactions'),
    
    path('manage/tariffs/dashboard/', admin_tariffs_dashboard, name='admin_tariffs_dashboard'),
    path('manage/tariffs/service/create/', admin_service_create, name='admin_service_create'),
    path('manage/tariffs/service/<int:pk>/edit/', admin_service_edit, name='admin_service_edit'),
    path('manage/tariffs/service/<int:pk>/delete/', admin_service_delete, name='admin_service_delete'),
    path('manage/tariffs/extra-service/create/', admin_extra_service_create, name='admin_extra_service_create'),
    path('manage/tariffs/extra-service/<int:pk>/edit/', admin_extra_service_edit, name='admin_extra_service_edit'),
    path('manage/tariffs/extra-service/<int:pk>/delete/', admin_extra_service_delete, name='admin_extra_service_delete'),
    path('manage/tariffs/payments/', admin_payment_settings, name='admin_payment_settings'),

    path('manage/marketing/', admin_marketing_settings, name='admin_marketing_settings'),
]
