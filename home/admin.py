from django.contrib import admin
from django.utils.safestring import mark_safe
from django.utils.html import format_html
from django.urls import reverse
from .models import (
    Otziv, Rabota, OtzivComment, ContactMessage, SEOModel, SectionBackground,
    Service, ExtraService, StandaloneExtraService,
    Customer, Cart, CartItem, Order, OrderItem, OrderQuestionnaire, OrderFile, OrderComment,
    LegalInfo, SiteMarketingSettings, CustomerSupportThread, CustomerSupportMessage,
)


@admin.register(Otziv)
class OtzivAdmin(admin.ModelAdmin):
    list_display = ['name', 'firma', 'active', 'otziv_photo', 'created']
    list_filter = ['created', 'active']
    search_fields = ['name', 'body']
    date_hierarchy = 'created'
    ordering = ['created']
    save_on_top = True

    @admin.display(description="Изображение", ordering='body')
    def otziv_photo(self, home: Otziv):
        if home.foto:
            return mark_safe(f"<img src='{home.foto.url}' width=50>")
        return "Без фото"


@admin.register(OtzivComment)
class OtzivCommentAdmin(admin.ModelAdmin):
    list_display = ['author_name', 'otziv', 'parent', 'is_admin_reply', 'active', 'created']
    list_filter = ['created', 'active', 'is_admin_reply']
    search_fields = ['author_name', 'content', 'otziv__name']
    date_hierarchy = 'created'
    ordering = ['-created']
    save_on_top = True
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('otziv', 'parent', 'content')
        }),
        ('Информация об авторе', {
            'fields': ('author_name', 'author_email', 'author_company')
        }),
        ('Модерация', {
            'fields': ('active', 'is_admin_reply'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Rabota)
class RabotaAdmin(admin.ModelAdmin):
    list_display = [
        'name', 
        'category', 
        'status', 
        'featured', 
        'order',
        'rabota_image', 
        'created'
    ]
    list_filter = [
        'category', 
        'status', 
        'featured', 
        'created'
    ]
    search_fields = ['name', 'body', 'technologies']
    date_hierarchy = 'created'
    ordering = ['order', '-created']
    save_on_top = True
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('name', 'category', 'status', 'featured', 'order')
        }),
        ('Контент', {
            'fields': ('body', 'technologies', 'image')
        }),
        ('Ссылки', {
            'fields': ('adres',)
        }),
        ('Метаданные', {
            'fields': ('created', 'updated'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['created', 'updated']
    
    list_editable = ['featured', 'order']
    
    actions = ['mark_as_featured', 'mark_as_completed']
    
    @admin.display(description="Изображение", ordering='name')
    def rabota_image(self, obj: Rabota):
        if obj.image:
            return mark_safe(f"<img src='{obj.image.url}' width=50 height=50 style='object-fit: cover; border-radius: 4px;'>")
        return "Без фото"
    
    @admin.action(description="Отметить как рекомендуемые")
    def mark_as_featured(self, request, queryset):
        updated = queryset.update(featured=True)
        self.message_user(request, f"{updated} проект(ов) отмечен(ы) как рекомендуемые.")
    
    @admin.action(description="Отметить как завершенные")
    def mark_as_completed(self, request, queryset):
        updated = queryset.update(status='completed')
        self.message_user(request, f"{updated} проект(ов) отмечен(ы) как завершенные.")


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'created', 'is_read', 'is_spam', 'has_attachment']
    list_filter = ['is_read', 'is_spam', 'created']
    search_fields = ['name', 'email', 'message', 'ip_address']
    readonly_fields = ['created', 'ip_address', 'user_agent']
    list_editable = ['is_read', 'is_spam']
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('name', 'email', 'message', 'attachment')
        }),
        ('Техническая информация', {
            'fields': ('ip_address', 'user_agent', 'created'),
            'classes': ('collapse',)
        }),
        ('Статус', {
            'fields': ('is_read', 'is_spam')
        }),
    )
    
    def has_attachment(self, obj):
        return bool(obj.attachment)
    has_attachment.boolean = True
    has_attachment.short_description = "Вложение"
    
    def mark_as_read(self, request, queryset):
        queryset.update(is_read=True)
    mark_as_read.short_description = "Отметить как прочитанные"
    
    def mark_as_unread(self, request, queryset):
        queryset.update(is_read=False)
    mark_as_unread.short_description = "Отметить как непрочитанные"
    
    def mark_as_spam(self, request, queryset):
        queryset.update(is_spam=True)
    mark_as_spam.short_description = "Отметить как спам"
    
    def mark_as_not_spam(self, request, queryset):
        queryset.update(is_spam=False)
    mark_as_not_spam.short_description = "Отметить как не спам"
    
    actions = [mark_as_read, mark_as_unread, mark_as_spam, mark_as_not_spam]


@admin.register(SEOModel)
class SEOModelAdmin(admin.ModelAdmin):
    list_display = ['page_url', 'title', 'created', 'updated']
    list_filter = ['created', 'updated']
    search_fields = ['page_url', 'title', 'description', 'keywords']
    readonly_fields = ['created', 'updated']
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('page_url', 'title', 'description', 'keywords')
        }),
        ('Open Graph', {
            'fields': ('og_title', 'og_description', 'og_image'),
            'classes': ('collapse',)
        }),
        ('Дополнительно', {
            'fields': ('canonical_url', 'h1'),
            'classes': ('collapse',)
        }),
        ('Система', {
            'fields': ('created', 'updated'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).order_by('page_url')


@admin.register(SectionBackground)
class SectionBackgroundAdmin(admin.ModelAdmin):
    list_display = ['section', 'background_type', 'is_active', 'preview_background', 'created']
    list_filter = ['background_type', 'is_active', 'section']
    search_fields = ['section']
    readonly_fields = ['created', 'updated']
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('section', 'background_type', 'is_active')
        }),
        ('Изображение', {
            'fields': ('background_image',),
            'classes': ('collapse',),
            'description': 'Настройки для фонового изображения'
        }),
        ('Видео', {
            'fields': ('background_video',),
            'classes': ('collapse',),
            'description': 'Настройки для фонового видео'
        }),
        ('Градиент', {
            'fields': ('gradient_start', 'gradient_end', 'gradient_direction'),
            'classes': ('collapse',),
            'description': 'Настройки для градиентного фона'
        }),
        ('Наложение', {
            'fields': ('overlay_color', 'overlay_opacity'),
            'classes': ('collapse',),
            'description': 'Настройки наложения поверх фона'
        }),
        ('Система', {
            'fields': ('created', 'updated'),
            'classes': ('collapse',)
        }),
    )
    
    list_editable = ['is_active']
    
    @admin.display(description="Предпросмотр")
    def preview_background(self, obj):
        if obj.background_type == 'image' and obj.background_image:
            return mark_safe(f'<img src="{obj.background_image.url}" width="100" height="60" style="object-fit: cover; border-radius: 4px;">')
        elif obj.background_type == 'video' and obj.background_video:
            return mark_safe(f'<video width="100" height="60" style="object-fit: cover; border-radius: 4px;" muted><source src="{obj.background_video.url}" type="video/mp4"></video>')
        elif obj.background_type == 'gradient':
            return mark_safe(f'<div style="width: 100px; height: 60px; background: linear-gradient({obj.gradient_direction}, {obj.gradient_start}, {obj.gradient_end}); border-radius: 4px;"></div>')
        return "Нет фона"
    
    def save_model(self, request, obj, form, change):
        # Автоматически создаем записи для всех секций, если их нет
        if not change:  # Только при создании новой записи
            existing_sections = SectionBackground.objects.values_list('section', flat=True)
            all_sections = [choice[0] for choice in SectionBackground.SECTION_CHOICES]
            
            for section in all_sections:
                if section not in existing_sections and section != obj.section:
                    SectionBackground.objects.create(
                        section=section,
                        background_type='gradient',
                        gradient_start='#f3f4f6',
                        gradient_end='#e5e7eb',
                        is_active=False
                    )
        
        super().save_model(request, obj, form, change)


class ExtraServiceInline(admin.TabularInline):
    model = ExtraService
    extra = 1
    fields = ('title', 'description', 'price', 'order', 'is_active')
    ordering = ('order',)
    verbose_name = "Дополнительная услуга в составе"
    verbose_name_plural = "Дополнительные услуги в составе"


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ('title', 'price', 'order', 'is_active', 'service_icon', 'created')
    list_filter = ('is_active', 'created')
    search_fields = ('title', 'description')
    list_editable = ('order', 'is_active')
    ordering = ('order',)
    save_on_top = True
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('title', 'description', 'price', 'order', 'is_active')
        }),
        ('Медиа', {
            'fields': ('icon',),
            'classes': ('collapse',)
        }),
        ('Система', {
            'fields': ('created', 'updated'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('created', 'updated')
    inlines = [ExtraServiceInline]
    
    @admin.display(description="Иконка")
    def service_icon(self, obj):
        if obj.icon:
            return mark_safe(f'<img src="{obj.icon.url}" width="50" height="50" style="object-fit: cover; border-radius: 4px;">')
        return "Без иконки"
    
    actions = ['activate_services', 'deactivate_services']
    
    @admin.action(description="Активировать услуги")
    def activate_services(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} услуг(и) активированы.")
    
    @admin.action(description="Деактивировать услуги")
    def deactivate_services(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} услуг(и) деактивированы.")


@admin.register(ExtraService)
class ExtraServiceAdmin(admin.ModelAdmin):
    list_display = ('title', 'service', 'price', 'order', 'is_active', 'created')
    list_filter = ('service', 'is_active', 'created')
    search_fields = ('title', 'description', 'service__title')
    list_editable = ('order', 'is_active')
    ordering = ('service', 'order')
    save_on_top = True
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('service', 'title', 'description', 'price', 'order', 'is_active')
        }),
        ('Система', {
            'fields': ('created', 'updated'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('created', 'updated')
    
    actions = ['activate_extra_services', 'deactivate_extra_services']
    
    @admin.action(description="Активировать доп. услуги в составе")
    def activate_extra_services(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} дополнительных услуг(и) в составе активированы.")
    
    @admin.action(description="Деактивировать доп. услуги в составе")
    def deactivate_extra_services(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} дополнительных услуг(и) в составе деактивированы.")


@admin.register(StandaloneExtraService)
class StandaloneExtraServiceAdmin(admin.ModelAdmin):
    list_display = ('title', 'price', 'order', 'is_active', 'created')
    list_filter = ('is_active', 'created')
    search_fields = ('title', 'description')
    list_editable = ('order', 'is_active')
    ordering = ('order',)
    save_on_top = True
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('title', 'description', 'price', 'order', 'is_active')
        }),
        ('Система', {
            'fields': ('created', 'updated'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('created', 'updated')
    
    actions = ['activate_standalone_services', 'deactivate_standalone_services']
    
    @admin.action(description="Активировать доп. услуги")
    def activate_standalone_services(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} дополнительных услуг(и) активированы.")
    
    @admin.action(description="Деактивировать доп. услуги")
    def deactivate_standalone_services(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} дополнительных услуг(и) деактивированы.")


# ==================== УПРАВЛЕНИЕ КЛИЕНТАМИ ====================

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('get_full_name', 'get_email', 'phone', 'company', 'total_orders', 'created')
    list_filter = ('created',)
    search_fields = ('user__username', 'user__email', 'user__first_name', 'user__last_name', 'phone', 'company')
    readonly_fields = ('created', 'updated')
    
    fieldsets = (
        ('Пользователь', {
            'fields': ('user',)
        }),
        ('Контактная информация', {
            'fields': ('phone', 'company', 'avatar')
        }),
        ('Система', {
            'fields': ('created', 'updated'),
            'classes': ('collapse',)
        }),
    )
    
    def get_full_name(self, obj):
        return obj.get_full_name()
    get_full_name.short_description = 'ФИО'
    
    def get_email(self, obj):
        return obj.get_email()
    get_email.short_description = 'Email'
    
    def total_orders(self, obj):
        count = obj.order_set.count()
        if count > 0:
            url = reverse('admin:home_order_changelist') + f'?customer__id__exact={obj.id}'
            return format_html('<a href="{}">{} заказ(ов)</a>', url, count)
        return '0 заказов'
    total_orders.short_description = 'Заказов'


class CustomerSupportMessageInline(admin.TabularInline):
    model = CustomerSupportMessage
    extra = 0
    readonly_fields = ('created_at', 'author', 'is_staff')


@admin.register(CustomerSupportThread)
class CustomerSupportThreadAdmin(admin.ModelAdmin):
    list_display = ('id', 'subject', 'user', 'status', 'updated_at')
    list_filter = ('status',)
    search_fields = ('subject', 'user__username', 'user__email')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [CustomerSupportMessageInline]


# ==================== УПРАВЛЕНИЕ КОРЗИНАМИ ====================

class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0
    fields = ('service_type', 'title', 'price', 'quantity')
    readonly_fields = ('service_type', 'title', 'price', 'quantity')
    can_delete = True
    
    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ('id', 'session_key', 'items_count', 'total_display', 'created')
    list_filter = ('created',)
    search_fields = ('session_key',)
    readonly_fields = ('created', 'updated', 'get_total_price')
    inlines = [CartItemInline]
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('session_key',)
        }),
        ('Итого', {
            'fields': ('get_total_price',)
        }),
        ('Система', {
            'fields': ('created', 'updated'),
            'classes': ('collapse',)
        }),
    )
    
    def items_count(self, obj):
        return obj.items.count()
    items_count.short_description = 'Товаров'
    
    def total_display(self, obj):
        return f"{obj.get_total_price():.0f} ₽"
    total_display.short_description = 'Сумма'
    
    actions = ['delete_old_carts']
    
    @admin.action(description="Удалить старые корзины (>30 дней)")
    def delete_old_carts(self, request, queryset):
        from django.utils import timezone
        from datetime import timedelta
        old_date = timezone.now() - timedelta(days=30)
        deleted = queryset.filter(created__lt=old_date).delete()
        self.message_user(request, f"Удалено {deleted[0]} старых корзин.")


# ==================== УПРАВЛЕНИЕ ЗАКАЗАМИ ====================

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    fields = ('service_type', 'title', 'price', 'quantity')
    readonly_fields = ('service_type', 'service_id', 'title', 'price', 'quantity')
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        return False


class OrderFileInline(admin.TabularInline):
    model = OrderFile
    extra = 0
    fields = ('filename', 'file', 'description', 'uploaded_at')
    readonly_fields = ('uploaded_at',)


class OrderCommentInline(admin.TabularInline):
    model = OrderComment
    extra = 1
    fields = ('author', 'content', 'is_admin_comment', 'created')
    readonly_fields = ('created',)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'order_number', 
        'customer_link', 
        'customer_name', 
        'total_price_display',
        'status_badge', 
        'payment_status_badge',
        'created'
    )
    list_filter = (
        'status', 
        'payment_status', 
        'created',
        ('customer', admin.RelatedOnlyFieldListFilter)
    )
    search_fields = (
        'order_number', 
        'customer_name', 
        'customer_email', 
        'customer_phone',
        'customer__user__username',
        'customer__user__email'
    )
    readonly_fields = ('order_number', 'created', 'updated', 'payment_id')
    date_hierarchy = 'created'
    ordering = ('-created',)
    save_on_top = True
    
    fieldsets = (
        ('Информация о заказе', {
            'fields': ('order_number', 'customer', 'status')
        }),
        ('Контактная информация клиента', {
            'fields': ('customer_name', 'customer_email', 'customer_phone')
        }),
        ('Финансы', {
            'fields': ('total_price', 'payment_status', 'payment_id')
        }),
        ('Система', {
            'fields': ('created', 'updated'),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [OrderItemInline, OrderFileInline, OrderCommentInline]
    
    actions = [
        'mark_as_processing',
        'mark_as_confirmed', 
        'mark_as_in_progress',
        'mark_as_completed',
        'mark_as_paid',
        'export_orders_csv'
    ]
    
    def customer_link(self, obj):
        if obj.customer:
            url = reverse('admin:home_customer_change', args=[obj.customer.id])
            return format_html('<a href="{}">{}</a>', url, obj.customer.get_full_name())
        return 'Гость'
    customer_link.short_description = 'Клиент'
    
    def total_price_display(self, obj):
        return format_html('<strong>{} ₽</strong>', f'{obj.total_price:.0f}')
    total_price_display.short_description = 'Сумма'
    
    def status_badge(self, obj):
        colors = {
            'new': '#3b82f6',
            'processing': '#f59e0b',
            'confirmed': '#8b5cf6',
            'in_progress': '#10b981',
            'completed': '#059669',
            'cancelled': '#ef4444',
        }
        color = colors.get(obj.status, '#6b7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 12px; font-size: 11px; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Статус заказа'
    
    def payment_status_badge(self, obj):
        colors = {
            'pending': '#f59e0b',
            'paid': '#10b981',
            'failed': '#ef4444',
        }
        color = colors.get(obj.payment_status, '#6b7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 12px; font-size: 11px; font-weight: bold;">{}</span>',
            color,
            obj.get_payment_status_display()
        )
    payment_status_badge.short_description = 'Статус оплаты'
    
    @admin.action(description="Отметить как 'В обработке'")
    def mark_as_processing(self, request, queryset):
        updated = queryset.update(status='processing')
        self.message_user(request, f"{updated} заказ(ов) отмечены как 'В обработке'.")
    
    @admin.action(description="Отметить как 'Подтвержден'")
    def mark_as_confirmed(self, request, queryset):
        updated = queryset.update(status='confirmed')
        self.message_user(request, f"{updated} заказ(ов) отмечены как 'Подтвержден'.")
    
    @admin.action(description="Отметить как 'В работе'")
    def mark_as_in_progress(self, request, queryset):
        updated = queryset.update(status='in_progress')
        self.message_user(request, f"{updated} заказ(ов) отмечены как 'В работе'.")
    
    @admin.action(description="Отметить как 'Завершен'")
    def mark_as_completed(self, request, queryset):
        updated = queryset.update(status='completed')
        self.message_user(request, f"{updated} заказ(ов) отмечены как 'Завершен'.")
    
    @admin.action(description="Отметить как 'Оплачен'")
    def mark_as_paid(self, request, queryset):
        updated = queryset.update(payment_status='paid')
        self.message_user(request, f"{updated} заказ(ов) отмечены как 'Оплачен'.")
    
    @admin.action(description="Экспорт в CSV")
    def export_orders_csv(self, request, queryset):
        import csv
        from django.http import HttpResponse
        from django.utils import timezone
        
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="orders_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'
        response.write('\ufeff')  # BOM для корректного отображения в Excel
        
        writer = csv.writer(response)
        writer.writerow([
            'Номер заказа', 'Клиент', 'Email', 'Телефон', 
            'Сумма', 'Статус заказа', 'Статус оплаты', 'Дата создания'
        ])
        
        for order in queryset:
            writer.writerow([
                order.order_number,
                order.customer_name,
                order.customer_email,
                order.customer_phone,
                order.total_price,
                order.get_status_display(),
                order.get_payment_status_display(),
                order.created.strftime('%d.%m.%Y %H:%M')
            ])
        
        return response


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('order', 'title', 'service_type', 'price', 'quantity')
    list_filter = ('service_type',)
    search_fields = ('title', 'order__order_number')
    readonly_fields = ('order', 'service_type', 'service_id', 'title', 'price', 'quantity')
    
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(OrderQuestionnaire)
class OrderQuestionnaireAdmin(admin.ModelAdmin):
    list_display = ('order', 'project_name', 'deadline', 'budget_range', 'created')
    list_filter = ('created', 'deadline')
    search_fields = ('order__order_number', 'project_name', 'project_description')
    readonly_fields = ('order', 'created', 'updated')
    
    fieldsets = (
        ('Заказ', {
            'fields': ('order',)
        }),
        ('О проекте', {
            'fields': ('project_name', 'project_description', 'target_audience', 'competitors')
        }),
        ('Требования', {
            'fields': ('technical_requirements', 'design_preferences', 'functionality_requirements')
        }),
        ('Сроки и бюджет', {
            'fields': ('deadline', 'budget_range')
        }),
        ('Дополнительно', {
            'fields': ('additional_requirements', 'preferred_contact_method', 'additional_contacts'),
            'classes': ('collapse',)
        }),
        ('Система', {
            'fields': ('created', 'updated'),
            'classes': ('collapse',)
        }),
    )


@admin.register(OrderFile)
class OrderFileAdmin(admin.ModelAdmin):
    list_display = ('filename', 'order', 'description', 'uploaded_at')
    list_filter = ('uploaded_at',)
    search_fields = ('filename', 'description', 'order__order_number')
    readonly_fields = ('uploaded_at',)
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('order', 'filename', 'file', 'description')
        }),
        ('Система', {
            'fields': ('uploaded_at',),
            'classes': ('collapse',)
        }),
    )


@admin.register(OrderComment)
class OrderCommentAdmin(admin.ModelAdmin):
    list_display = ('order', 'author', 'is_admin_comment', 'short_content', 'created')
    list_filter = ('is_admin_comment', 'created')
    search_fields = ('order__order_number', 'author__username', 'content')
    readonly_fields = ('created', 'updated')
    date_hierarchy = 'created'
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('order', 'author', 'content', 'is_admin_comment')
        }),
        ('Система', {
            'fields': ('created', 'updated'),
            'classes': ('collapse',)
        }),
    )
    
    def short_content(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    short_content.short_description = 'Комментарий'


@admin.register(LegalInfo)
class LegalInfoAdmin(admin.ModelAdmin):
    list_display = ('company_name', 'inn', 'is_active', 'updated')
    list_filter = ('is_active', 'created', 'updated')
    search_fields = ('company_name', 'inn', 'ogrn')
    readonly_fields = ('created', 'updated')
    
    fieldsets = (
        ('Основная информация о компании', {
            'fields': ('company_name', 'company_full_name', 'inn', 'kpp', 'ogrn')
        }),
        ('Адреса', {
            'fields': ('legal_address', 'actual_address')
        }),
        ('Контакты', {
            'fields': ('phone', 'email', 'website')
        }),
        ('Банковские реквизиты', {
            'fields': ('bank_name', 'bank_account', 'correspondent_account', 'bik'),
            'classes': ('collapse',)
        }),
        ('Документы', {
            'fields': ('contract_file', 'extract_file', 'certificate_file'),
            'classes': ('collapse',)
        }),
        ('Текстовая информация', {
            'fields': ('about_site', 'about_company', 'terms_of_use', 'privacy_policy'),
            'classes': ('collapse',)
        }),
        ('Система', {
            'fields': ('is_active', 'created', 'updated'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        # Убеждаемся, что только одна запись активна
        if obj.is_active:
            LegalInfo.objects.filter(is_active=True).exclude(pk=obj.pk).update(is_active=False)
        super().save_model(request, obj, form, change)


@admin.register(SiteMarketingSettings)
class SiteMarketingSettingsAdmin(admin.ModelAdmin):
    """Дублирование /manage/marketing/ для суперпользователей в Jazzmin."""

    list_display = ('__str__', 'active', 'replace_builtin_counters')

    def has_add_permission(self, request):
        return not SiteMarketingSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
