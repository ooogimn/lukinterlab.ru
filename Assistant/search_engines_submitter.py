"""
Сервис для отправки статей в поисковые системы
"""
import logging
import requests
from typing import Dict, Any, Optional
from django.conf import settings
from django.urls import reverse

logger = logging.getLogger(__name__)


class SearchEnginesSubmitter:
    """Сервис для отправки статей в поисковые системы (Google, Yandex, Bing)"""
    
    def __init__(self):
        """Инициализация сервиса"""
        self.site_url = getattr(settings, 'SITE_URL', 'https://lukinterlab.ru')
        self.sitemap_url = f"{self.site_url}/sitemap.xml"
        
        # API ключи (опционально)
        self.google_api_key = getattr(settings, 'GOOGLE_SEARCH_CONSOLE_API_KEY', None)
        self.yandex_token = getattr(settings, 'YANDEX_WEBMASTER_TOKEN', None)
        self.bing_api_key = getattr(settings, 'BING_WEBMASTER_API_KEY', None)
    
    def submit_to_google(self, url: str) -> Dict[str, Any]:
        """
        Отправка URL в Google (API + ping)
        
        Args:
            url: URL статьи
            
        Returns:
            Результат отправки
        """
        result = {
            'success': False,
            'method': None,
            'error': None
        }
        
        # Метод 1: Ping sitemap
        try:
            ping_url = f"https://www.google.com/ping?sitemap={self.sitemap_url}"
            response = requests.get(ping_url, timeout=10)
            if response.status_code == 200:
                result['success'] = True
                result['method'] = 'ping'
                logger.info(f"[OK] Google ping успешен: {url}")
        except Exception as e:
            logger.warning(f"[WARNING] Google ping ошибка: {str(e)}")
            result['error'] = str(e)
        
        # Метод 2: Google Search Console API (если настроен)
        if self.google_api_key:
            try:
                # Здесь можно добавить вызов Google Search Console API
                # Пока не реализовано, т.к. требует OAuth2 аутентификации
                logger.debug("Google Search Console API требует OAuth2 настройки")
            except Exception as e:
                logger.warning(f"[WARNING] Google API ошибка: {str(e)}")
        
        return result
    
    def submit_to_yandex(self, url: str) -> Dict[str, Any]:
        """
        Отправка URL в Yandex (API + ping)
        
        Args:
            url: URL статьи
            
        Returns:
            Результат отправки
        """
        result = {
            'success': False,
            'method': None,
            'error': None
        }
        
        # Метод 1: Ping sitemap
        try:
            ping_url = f"https://webmaster.yandex.ru/ping?sitemap={self.sitemap_url}"
            response = requests.get(ping_url, timeout=10)
            if response.status_code == 200:
                result['success'] = True
                result['method'] = 'ping'
                logger.info(f"[OK] Yandex ping успешен: {url}")
        except Exception as e:
            logger.warning(f"[WARNING] Yandex ping ошибка: {str(e)}")
            result['error'] = str(e)
        
        # Метод 2: Yandex Webmaster API (если настроен)
        if self.yandex_token:
            try:
                api_url = "https://api.webmaster.yandex.net/v4/user/{user_id}/hosts/{host_id}/recrawl/queue"
                # Требует user_id и host_id, которые нужно получить через API
                logger.debug("Yandex Webmaster API требует настройки user_id и host_id")
            except Exception as e:
                logger.warning(f"[WARNING] Yandex API ошибка: {str(e)}")
        
        return result
    
    def submit_to_bing(self, url: str) -> Dict[str, Any]:
        """
        Отправка URL в Bing (API + ping)
        
        Args:
            url: URL статьи
            
        Returns:
            Результат отправки
        """
        result = {
            'success': False,
            'method': None,
            'error': None
        }
        
        # Метод 1: Ping sitemap
        try:
            ping_url = f"https://www.bing.com/ping?sitemap={self.sitemap_url}"
            response = requests.get(ping_url, timeout=10)
            if response.status_code == 200:
                result['success'] = True
                result['method'] = 'ping'
                logger.info(f"[OK] Bing ping успешен: {url}")
        except Exception as e:
            logger.warning(f"[WARNING] Bing ping ошибка: {str(e)}")
            result['error'] = str(e)
        
        # Метод 2: Bing Webmaster Tools API (если настроен)
        if self.bing_api_key:
            try:
                api_url = "https://ssl.bing.com/webmaster/api.svc/json/SubmitUrl"
                # Требует настройки API ключа
                logger.debug("Bing Webmaster API требует настройки API ключа")
            except Exception as e:
                logger.warning(f"[WARNING] Bing API ошибка: {str(e)}")
        
        return result
    
    def submit_all(self, post) -> Dict[str, Any]:
        """
        Отправка статьи во все поисковые системы
        
        Args:
            post: Статья Post
            
        Returns:
            Результаты отправки
        """
        url = f"{self.site_url}{post.get_absolute_url()}"
        
        results = {
            'google': self.submit_to_google(url),
            'yandex': self.submit_to_yandex(url),
            'bing': self.submit_to_bing(url),
        }
        
        success_count = sum(1 for r in results.values() if r.get('success', False))
        logger.info(f"[SUBMIT] Отправка в поисковые системы: {success_count}/3 успешно")
        
        return results
