from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import TelegramUser
from .auth import TelegramBackend

# Создавайте свои просмотры здесь.

def telegram_login(request):
    if request.method == 'POST':
        telegram_id = request.POST.get('telegram_id')
        if telegram_id:
            user = authenticate(request, telegram_id=telegram_id)
            if user is not None:
                login(request, user)
                return redirect('home')
            else:
                messages.error(request, 'Неверный Telegram ID или пользователь не зарегистрирован.')
        else:
            messages.error(request, 'Пожалуйста, введите ваш Telegram ID.')
    return render(request, 'Users/telegram_login.html')

@login_required
def profile(request):
    try:
        telegram_user = TelegramUser.objects.get(user=request.user)
        return render(request, 'Users/profile.html', {'telegram_user': telegram_user})
    except TelegramUser.DoesNotExist:
        return render(request, 'Users/profile.html')
