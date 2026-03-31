from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User
from .models import TelegramUser

class TelegramBackend(ModelBackend):
    def authenticate(self, request, telegram_id=None, **kwargs):
        try:
            telegram_user = TelegramUser.objects.get(telegram_id=telegram_id)
            if telegram_user.user:
                return telegram_user.user
            return None
        except TelegramUser.DoesNotExist:
            return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None 