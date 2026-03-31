"""
Утилиты для работы с токенами GigaChat
"""
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


def count_tokens_approx(text: str) -> int:
    """
    Приблизительный подсчет токенов в тексте
    
    Для русского текста: ~4 символа = 1 токен
    Для английского: ~3 символа = 1 токен
    
    Args:
        text: Текст для подсчета
        
    Returns:
        Приблизительное количество токенов
    """
    if not text:
        return 0
    
    # Простая эвристика: считаем, что среднее соотношение 3.5 символа на токен
    # Это приблизительная оценка, точный подсчет требует API
    return len(text) // 3.5


def estimate_prompt_tokens(messages: list) -> int:
    """
    Оценить количество токенов в промпте
    
    Args:
        messages: Список сообщений для API
        
    Returns:
        Приблизительное количество токенов
    """
    total_text = ""
    for msg in messages:
        content = msg.get('content', '')
        role = msg.get('role', '')
        # Добавляем вес для системных сообщений
        if role == 'system':
            total_text += content * 1.2  # Системные промпты весят больше
        else:
            total_text += content
    
    return count_tokens_approx(total_text)


def check_token_limit(model: str, estimated_tokens: int) -> Dict[str, Any]:
    """
    Проверить, не превысит ли запрос лимит токенов
    
    Args:
        model: Название модели
        estimated_tokens: Оценочное количество токенов
        
    Returns:
        Dict с информацией о проверке
    """
    from .models import TokenUsage
    
    limit_info = TokenUsage.check_limits(model)
    remaining = limit_info['remaining']
    
    return {
        'can_proceed': estimated_tokens <= remaining,
        'estimated_tokens': estimated_tokens,
        'remaining': remaining,
        'will_exceed': estimated_tokens > remaining,
        'limit_info': limit_info,
    }

