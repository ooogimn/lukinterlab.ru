from django.contrib import admin

from identity_auth.models import LinkedSocialAccount, SiteCustomerAuthSettings


@admin.register(LinkedSocialAccount)
class LinkedSocialAccountAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'provider', 'provider_user_id', 'created_at')
    list_filter = ('provider',)
    search_fields = ('provider_user_id', 'user__username', 'user__email')
    raw_id_fields = ('user',)
    readonly_fields = ('created_at',)


@admin.register(SiteCustomerAuthSettings)
class SiteCustomerAuthSettingsAdmin(admin.ModelAdmin):
    """Дублирование /manage/auth/oauth/ в Jazzmin; секреты — только суперпользователь."""

    def has_module_permission(self, request):
        return bool(request.user.is_superuser)

    def has_add_permission(self, request):
        return request.user.is_superuser and not SiteCustomerAuthSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
