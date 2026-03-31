from django.core.management.base import BaseCommand
from home.models import SEOModel
from django.conf import settings


class Command(BaseCommand):
    help = 'Создает/обновляет SEO записи для всех страниц с AI/ИИ ключевыми словами'

    def handle(self, *args, **options):
        self.stdout.write('Оптимизация SEO для AI/ИИ запросов...')
        
        # Ключевые слова для AI/ИИ
        ai_keywords = (
            'искусственный интеллект, ИИ, AI, LLM, большие языковые модели, '
            'GigaChat, GPT, Gemini, DeepSeek, Grok, OpenAI, Google AI, '
            'саморекламирующие сайты, самопродающие магазины, '
            'ИИ-интеграция, ИИ-боты, ИИ-маркетинг, ИИ-автоматизация, '
            'внедрение ИИ в бизнес, ИИ для бизнеса, AI решения, '
            'интеграция искусственного интеллекта, LLM интеграция, '
            'GigaChat API, GPT интеграция, Gemini API, DeepSeek API, '
            'ИИ-консалтинг, AI консалтинг, искусственный интеллект для бизнеса'
        )
        
        # Страницы для оптимизации
        pages_data = [
            {
                'page_url': '/',
                'title': 'LukInterLab - AI и IT решения под ключ | ИИ интеграция',
                'description': 'Создаем сайты, боты, приложения и интернет-магазины с искусственным интеллектом. Специализируемся на LLM, интеграции GigaChat, GPT, Gemini, DeepSeek, Grok. Саморекламирующие сайты, самопродающие магазины.',
                'keywords': ai_keywords,
                'h1': 'LukInterLab - ваша AI-лаборатория',
            },
            {
                'page_url': '/services/',
                'title': 'AI и IT услуги | Интеграция ИИ и LLM | LukInterLab',
                'description': 'Услуги по интеграции искусственного интеллекта: GigaChat, GPT, Gemini, DeepSeek, Grok. Саморекламирующие сайты, самопродающие интернет-магазины, ИИ-маркетинг, ИИ-боты.',
                'keywords': ai_keywords + ', услуги ИИ, услуги AI, интеграция LLM, ИИ услуги',
                'h1': 'AI и IT услуги',
            },
            {
                'page_url': '/extra-services/',
                'title': 'Дополнительные AI услуги | ИИ поддержка и консалтинг',
                'description': 'Дополнительные услуги с искусственным интеллектом: обучение ИИ-моделей, ИИ-контент, ИИ-модерация, ИИ-поддержка 24/7, ИИ-аналитика, ИИ-безопасность.',
                'keywords': ai_keywords + ', ИИ поддержка, AI консалтинг, обучение ИИ, ИИ аналитика',
                'h1': 'Дополнительные AI услуги',
            },
            {
                'page_url': '/otziv/',
                'title': 'Отзывы о AI и IT услугах LukInterLab | ИИ интеграция',
                'description': 'Отзывы клиентов о работе с LukInterLab: интеграция ИИ, создание AI-решений, внедрение LLM, разработка ИИ-ботов и автоматизация с искусственным интеллектом.',
                'keywords': ai_keywords + ', отзывы ИИ, отзывы AI, отзывы интеграция',
                'h1': 'Отзывы наших клиентов',
            },
        ]
        
        created_count = 0
        updated_count = 0
        
        for page_data in pages_data:
            seo_obj, created = SEOModel.objects.update_or_create(
                page_url=page_data['page_url'],
                defaults={
                    'title': page_data['title'],
                    'description': page_data['description'],
                    'keywords': page_data['keywords'],
                    'h1': page_data.get('h1', ''),
                    'og_title': page_data['title'],
                    'og_description': page_data['description'],
                }
            )
            
            if created:
                created_count += 1
                self.stdout.write(f'Создана SEO запись: {page_data["page_url"]}')
            else:
                updated_count += 1
                self.stdout.write(f'Обновлена SEO запись: {page_data["page_url"]}')
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Успешно обработано: {created_count} создано, {updated_count} обновлено'
            )
        )

