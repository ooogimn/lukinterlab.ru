"""
Сервисы для модерации статей и комментариев
"""
import logging
import re
from typing import Dict, Any, List, Union
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from Blog.models import Post, Comment
from .models import (
    ArticleModeration, CommentModeration, SEOAnalysis,
    ModerationCriteria, CommentModerationCriteria,
    ModerationNotification, ModerationStatistics
)
from django.contrib.auth import get_user_model
from django.db.models import Avg, Count, Q, Sum
from datetime import date, timedelta

User = get_user_model()

logger = logging.getLogger(__name__)


class ArticleModerationService:
    """Сервис модерации статей"""
    
    def moderate_article(self, post: Post, criteria: ModerationCriteria = None) -> Dict[str, Any]:
        """Модерация статьи"""
        if not criteria:
            criteria = ModerationCriteria.objects.filter(is_active=True).first()
        
        if not criteria:
            logger.warning(f"Нет активных критериев модерации для статьи {post.id}")
            return {'error': 'Нет активных критериев модерации'}
        
        # Проверка по критериям
        check_results = self.check_criteria(post, criteria)
        
        # Определение статуса
        status = self._determine_status(check_results)
        
        # Создание или обновление записи модерации
        moderation, created = ArticleModeration.objects.get_or_create(
            post=post,
            defaults={
                'status': status,
                'criteria_used': criteria,
                'check_results': check_results,
            }
        )
        
        if not created:
            moderation.status = status
            moderation.criteria_used = criteria
            moderation.check_results = check_results
            moderation.save()
        
        return {
            'moderation': moderation,
            'status': status,
            'check_results': check_results,
        }
    
    def check_criteria(self, post: Post, criteria: ModerationCriteria) -> Dict[str, Any]:
        """Проверка статьи по критериям"""
        results = {
            'passed': True,
            'checks': {},
            'errors': [],
            'warnings': [],
        }
        
        criteria_data = criteria.criteria if isinstance(criteria.criteria, dict) else {}
        
        # Проверка длины
        content_length = len(post.content) if post.content else 0
        title_length = len(post.title) if post.title else 0
        
        if 'min_length' in criteria_data:
            min_len = criteria_data.get('min_length', 0)
            if content_length < min_len:
                results['passed'] = False
                results['errors'].append(f"Текст слишком короткий: {content_length} символов (минимум {min_len})")
                results['checks']['length'] = False
            else:
                results['checks']['length'] = True
        
        if 'max_length' in criteria_data:
            max_len = criteria_data.get('max_length', 10000)
            if content_length > max_len:
                results['warnings'].append(f"Текст слишком длинный: {content_length} символов (максимум {max_len})")
                results['checks']['length'] = 'warning'
        
        # Проверка обязательных ключевых слов
        if 'required_keywords' in criteria_data:
            required = criteria_data.get('required_keywords', [])
            if required:
                content_lower = (post.content or '').lower()
                title_lower = (post.title or '').lower()
                found_keywords = []
                missing_keywords = []
                
                for keyword in required:
                    if keyword.lower() in content_lower or keyword.lower() in title_lower:
                        found_keywords.append(keyword)
                    else:
                        missing_keywords.append(keyword)
                
                if missing_keywords:
                    results['passed'] = False
                    results['errors'].append(f"Отсутствуют обязательные ключевые слова: {', '.join(missing_keywords)}")
                    results['checks']['keywords'] = False
                else:
                    results['checks']['keywords'] = True
        
        # Проверка запрещенных слов
        if 'forbidden_words' in criteria_data:
            forbidden = criteria_data.get('forbidden_words', [])
            if forbidden:
                content_lower = (post.content or '').lower()
                title_lower = (post.title or '').lower()
                found_forbidden = []
                
                for word in forbidden:
                    if word.lower() in content_lower or word.lower() in title_lower:
                        found_forbidden.append(word)
                
                if found_forbidden:
                    results['passed'] = False
                    results['errors'].append(f"Найдены запрещенные слова: {', '.join(found_forbidden)}")
                    results['checks']['forbidden_words'] = False
                else:
                    results['checks']['forbidden_words'] = True
        
        # Проверка наличия изображения
        if not post.kartinka:
            results['warnings'].append("Отсутствует изображение превью")
            results['checks']['image'] = False
        else:
            results['checks']['image'] = True
        
        # Проверка категории
        if not post.category:
            results['warnings'].append("Не указана категория")
            results['checks']['category'] = False
        else:
            results['checks']['category'] = True
        
        # Проверка структуры контента (расширенная)
        if post.content:
            import re
            # Проверка наличия заголовков
            has_h2 = bool(re.search(r'<h2[^>]*>', post.content, re.IGNORECASE))
            has_h3 = bool(re.search(r'<h3[^>]*>', post.content, re.IGNORECASE))
            has_paragraphs = bool(re.search(r'<p[^>]*>', post.content, re.IGNORECASE))
            has_lists = bool(re.search(r'<[uo]l[^>]*>', post.content, re.IGNORECASE))
            
            structure_score = 0
            if has_h2:
                structure_score += 1
            if has_h3:
                structure_score += 1
            if has_paragraphs:
                structure_score += 1
            if has_lists:
                structure_score += 1
            
            if structure_score < 2:
                results['warnings'].append("Слабая структура контента (рекомендуется использовать заголовки, параграфы, списки)")
                results['checks']['structure'] = False
            else:
                results['checks']['structure'] = True
        
        # Проверка уникальности заголовка (базовая)
        if post.title:
            # Проверка на дубликаты заголовков
            duplicate_titles = Post.objects.filter(title=post.title).exclude(id=post.id).count()
            if duplicate_titles > 0:
                results['warnings'].append(f"Найдено {duplicate_titles} статей с таким же заголовком")
                results['checks']['unique_title'] = False
            else:
                results['checks']['unique_title'] = True
        
        # Проверка наличия тегов
        tags_count = post.tags.count()
        if tags_count == 0:
            results['warnings'].append("Отсутствуют теги")
            results['checks']['tags'] = False
        elif tags_count < 3:
            results['warnings'].append(f"Мало тегов ({tags_count}, рекомендуется минимум 3)")
            results['checks']['tags'] = 'warning'
        else:
            results['checks']['tags'] = True
        
        return results
    
    def _determine_status(self, check_results: Dict[str, Any]) -> str:
        """Определение статуса на основе результатов проверки"""
        if not check_results.get('passed', True):
            return 'needs_revision'
        elif check_results.get('warnings'):
            return 'pending'
        else:
            return 'approved'


class CommentModerationService:
    """Универсальный сервис модерации комментариев (для всех типов)"""
    
    def _get_comment_type_string(self, comment) -> str:
        """Определить тип комментария как строку для comment_type поля"""
        from django.contrib.contenttypes.models import ContentType
        ct = ContentType.objects.get_for_model(comment)
        return f"{ct.app_label}.{ct.model}"
    
    def _get_comment_content(self, comment) -> str:
        """Универсальный метод получения содержимого комментария"""
        if hasattr(comment, 'content'):
            return comment.content or ''
        return ''
    
    def _is_admin_reply(self, comment) -> bool:
        """Универсальный метод проверки является ли комментарий ответом администратора"""
        # Comment (Blog) и OtzivComment
        if hasattr(comment, 'is_admin_reply'):
            return comment.is_admin_reply
        
        # OrderComment
        if hasattr(comment, 'is_admin_comment'):
            return comment.is_admin_comment
        
        return False
    
    def _set_active(self, comment, active: bool):
        """Универсальный метод установки поля active"""
        if hasattr(comment, 'active'):
            comment.active = active
    
    def moderate_comment(self, comment: Union[Comment, Any], criteria: CommentModerationCriteria = None) -> Dict[str, Any]:
        """Универсальная модерация комментария (для всех типов)"""
        try:
            content = self._get_comment_content(comment)
            comment_type_str = self._get_comment_type_string(comment)
            logger.info(f"[MODERATE_COMMENT] Начало модерации комментария {comment.id} (Type: {comment_type_str}). Content length: {len(content)}")
            
            if not criteria:
                criteria = CommentModerationCriteria.objects.filter(is_active=True).first()
                logger.info(f"[MODERATE_COMMENT] Критерии получены из БД: {criteria.name if criteria else 'НЕТ'}")
            
            if not criteria:
                logger.warning(f"[MODERATE_COMMENT] Нет активных критериев модерации для комментария {comment.id}")
                return {'error': 'Нет активных критериев модерации'}
            
            # Проверка по критериям
            try:
                check_results = self.check_criteria(comment, criteria)
                logger.info(f"[MODERATE_COMMENT] Проверка завершена. Passed: {check_results.get('passed')}, Violations: {check_results.get('violations', [])}")
            except Exception as e:
                logger.error(f"[MODERATE_COMMENT] Ошибка при проверке критериев для комментария {comment.id}: {str(e)}", exc_info=True)
                return {'error': f'Ошибка проверки критериев: {str(e)}'}
            
            # Определение действия
            try:
                action = self._determine_action(check_results, criteria)
                logger.info(f"[MODERATE_COMMENT] Определено действие: {action} для комментария {comment.id}")
            except Exception as e:
                logger.error(f"[MODERATE_COMMENT] Ошибка при определении действия для комментария {comment.id}: {str(e)}", exc_info=True)
                return {'error': f'Ошибка определения действия: {str(e)}'}
            
            # Выполнение действия ПЕРЕД созданием записи модерации (если удаление)
            if action == 'deleted':
                try:
                    # Действие 1: Удалить при нарушении
                    # Полностью удаляет комментарий из базы данных
                    comment_id = comment.id
                    comment_content = content[:50] if content else ""
                    logger.warning(f"[MODERATE_COMMENT] УДАЛЕНИЕ комментария {comment_id} (Type: {comment_type_str}). Content preview: {comment_content}...")
                    comment.delete()  # Полное удаление из БД (также удалит запись модерации через CASCADE)
                    logger.info(f"[MODERATE_COMMENT] Комментарий {comment_id} полностью удален из базы данных (deleted)")
                    # Возвращаем результат без комментария и модерации, так как они удалены
                    return {
                        'action': action,
                        'check_results': check_results,
                        'deleted': True,
                    }
                except Exception as e:
                    logger.error(f"[MODERATE_COMMENT] КРИТИЧЕСКАЯ ОШИБКА при удалении комментария {comment.id}: {str(e)}", exc_info=True)
                    return {'error': f'Ошибка удаления комментария: {str(e)}'}

            # Не показывать на сайте до решения модератора (есть только у части моделей, напр. Blog.Comment)
            if action == 'hidden' and hasattr(comment, 'active'):
                self._set_active(comment, False)
                comment.save(update_fields=['active'])
                logger.info(f"[MODERATE_COMMENT] Комментарий {comment.id} скрыт (active=False)")
            
            # Создание или обновление записи модерации (только если комментарий не удален)
            try:
                # Определяем тип комментария для GenericForeignKey
                content_type = ContentType.objects.get_for_model(comment)
                comment_type_str = self._get_comment_type_string(comment)
                
                moderation, created = CommentModeration.objects.get_or_create(
                    content_type=content_type,
                    object_id=comment.id,
                    defaults={
                        'comment_type': comment_type_str,
                        'action': action,
                        'criteria_used': criteria,
                        'check_results': check_results,
                    }
                )
                logger.info(f"[MODERATE_COMMENT] Запись модерации {'создана' if created else 'обновлена'}. Moderation ID: {moderation.id}, Type: {comment_type_str}")
                
                if not created:
                    moderation.action = action
                    moderation.criteria_used = criteria
                    moderation.check_results = check_results
                    if moderation.comment_type != comment_type_str:
                        moderation.comment_type = comment_type_str
                    moderation.save()
                    logger.info(f"[MODERATE_COMMENT] Запись модерации {moderation.id} обновлена")
            except Exception as e:
                logger.error(f"[MODERATE_COMMENT] Ошибка при создании/обновлении записи модерации для комментария {comment.id}: {str(e)}", exc_info=True)
                return {'error': f'Ошибка создания записи модерации: {str(e)}'}
            
            # Выполнение действия исправления текста
            if action == 'corrected':
                # Действие 2: Исправлять текст
                # Автоматически исправляет текст комментария
                try:
                    logger.info(f"[MODERATE_COMMENT] Начало исправления текста комментария {comment.id}")
                    current_content = self._get_comment_content(comment)
                    
                    if moderation.corrected_text:
                        # Если есть готовый исправленный текст - используем его
                        comment.content = moderation.corrected_text
                        logger.info(f"[MODERATE_COMMENT] Использован готовый исправленный текст для комментария {comment.id}")
                    else:
                        # Иначе пытаемся исправить автоматически
                        corrected_content = self._auto_correct_text(current_content, check_results)
                        if corrected_content != current_content:
                            comment.content = corrected_content
                            moderation.corrected_text = corrected_content
                            moderation.save(update_fields=['corrected_text'])
                            logger.info(f"[MODERATE_COMMENT] Текст комментария {comment.id} автоматически исправлен. Old length: {len(current_content)}, New length: {len(corrected_content)}")
                    
                    # Сохраняем комментарий с обновленным текстом
                    # Используем update_fields чтобы избежать повторного срабатывания сигналов
                    comment.save(update_fields=['content'])
                    logger.info(f"[MODERATE_COMMENT] Комментарий {comment.id} исправлен (corrected) и сохранен")
                    
                    # Если также включено действие "reply", добавляем ответ после исправления
                    actions_data = criteria.actions if isinstance(criteria.actions, dict) else {}
                    if actions_data.get('reply', False):
                        logger.info(f"[MODERATE_COMMENT] Также включено действие 'reply', добавляем ответ после исправления")
                        try:
                            if not moderation.auto_reply:
                                auto_reply_text = self._generate_auto_reply(comment, check_results, criteria)
                                moderation.auto_reply = auto_reply_text
                                moderation.save(update_fields=['auto_reply'])
                                logger.info(f"[MODERATE_COMMENT] Сгенерирован автоматический ответ для комментария {comment.id}: {auto_reply_text[:50]}...")
                            
                            self._create_admin_reply(comment, moderation.auto_reply)
                            logger.info(f"[MODERATE_COMMENT] Добавлен автоматический ответ после исправления комментария {comment.id}")
                        except Exception as e:
                            logger.error(f"[MODERATE_COMMENT] Ошибка при добавлении ответа после исправления комментария {comment.id}: {str(e)}", exc_info=True)
                    
                except Exception as e:
                    logger.error(f"[MODERATE_COMMENT] Ошибка при исправлении комментария {comment.id}: {str(e)}", exc_info=True)
                    # В случае ошибки просто логируем, но не прерываем процесс
                
            elif action == 'replied':
                # Действие 3: Добавлять ответ
                # Создает автоматический ответ модератора на комментарий
                try:
                    logger.info(f"[MODERATE_COMMENT] Начало создания автоматического ответа для комментария {comment.id}")
                    if not moderation.auto_reply:
                        # Генерируем автоматический ответ
                        auto_reply_text = self._generate_auto_reply(comment, check_results, criteria)
                        moderation.auto_reply = auto_reply_text
                        moderation.save()
                        logger.info(f"[MODERATE_COMMENT] Сгенерирован автоматический ответ для комментария {comment.id}: {auto_reply_text[:50]}...")
                    
                    # Создаем ответ-комментарий
                    self._create_admin_reply(comment, moderation.auto_reply)
                    logger.info(f"[MODERATE_COMMENT] Добавлен автоматический ответ на комментарий {comment.id} (replied)")
                except Exception as e:
                    logger.error(f"[MODERATE_COMMENT] Ошибка при создании автоматического ответа для комментария {comment.id}: {str(e)}", exc_info=True)
            
            logger.info(f"[MODERATE_COMMENT] Модерация комментария {comment.id} завершена успешно. Action: {action}")
            return {
                'moderation': moderation,
                'action': action,
                'check_results': check_results,
            }
        except Exception as e:
            logger.error(f"[MODERATE_COMMENT] КРИТИЧЕСКАЯ ОШИБКА в методе moderate_comment для комментария {comment.id}: {str(e)}", exc_info=True)
            return {'error': f'Критическая ошибка модерации: {str(e)}'}
    
    def _auto_correct_text(self, content: str, check_results: Dict[str, Any]) -> str:
        """Автоматическое исправление текста комментария"""
        corrected = content
        original_content = content
        
        violations = check_results.get('violations', [])
        logger.info(f"[AUTO_CORRECT] Начало исправления текста. Violations: {violations}, Content length: {len(content)}")
        
        # Исправление слишком короткого комментария
        if 'too_short' in violations:
            # Добавляем примечание
            corrected = f"{corrected} [Текст дополнен модератором]"
            logger.info(f"[AUTO_CORRECT] Добавлено примечание для too_short")
        
        # Исправление слишком длинного комментария
        if 'too_long' in violations:
            # Обрезаем до разумной длины
            max_len = 2000
            if len(corrected) > max_len:
                corrected = corrected[:max_len] + "... [Текст сокращен модератором]"
                logger.info(f"[AUTO_CORRECT] Текст обрезан с {len(corrected)} до {max_len} символов")
        
        # Замена запрещенных слов на фразу LukInterLab
        if 'forbidden_words' in violations:
            found_words = check_results.get('found_words', [])
            replacement_text = "LukInterLab - решает любые проблемы"
            import re
            
            logger.info(f"[AUTO_CORRECT] Найдены запрещенные слова: {found_words}. Начальный текст: {content[:100]}...")
            
            for word in found_words:
                # Заменяем запрещенные слова на фразу LukInterLab
                # Используем более универсальный подход для кириллицы
                # Ищем слово как отдельное слово (не часть другого слова)
                # Для кириллицы используем [^\w] или начало/конец строки
                word_escaped = re.escape(word)
                # Паттерн: начало строки или не буква/цифра, затем слово, затем конец строки или не буква/цифра
                pattern = re.compile(r'(^|[^\w])' + word_escaped + r'([^\w]|$)', re.IGNORECASE | re.UNICODE)
                before_replace = corrected
                
                def replace_func(match):
                    # Сохраняем символы до и после слова
                    prefix = match.group(1) if match.group(1) else ''
                    suffix = match.group(2) if match.group(2) else ''
                    return prefix + replacement_text + suffix
                
                corrected = pattern.sub(replace_func, corrected)
                
                if before_replace != corrected:
                    logger.info(f"[AUTO_CORRECT] Заменено слово '{word}' на '{replacement_text}'. Было: {before_replace[:100]}..., Стало: {corrected[:100]}...")
                else:
                    # Попробуем простую замену без границ слов (на случай если слово в начале/конце или с пунктуацией)
                    simple_pattern = re.compile(re.escape(word), re.IGNORECASE | re.UNICODE)
                    corrected_simple = simple_pattern.sub(replacement_text, corrected)
                    if corrected_simple != corrected:
                        corrected = corrected_simple
                        logger.info(f"[AUTO_CORRECT] Заменено слово '{word}' (простая замена без границ). Было: {before_replace[:100]}..., Стало: {corrected[:100]}...")
                    else:
                        logger.warning(f"[AUTO_CORRECT] Слово '{word}' не найдено в тексте для замены. Текст: {corrected[:100]}...")
        
        if corrected != original_content:
            logger.info(f"[AUTO_CORRECT] Текст исправлен. Было: {original_content[:100]}..., Стало: {corrected[:100]}...")
        else:
            logger.warning(f"[AUTO_CORRECT] Текст НЕ был изменен! Возможно, слова не найдены или уже заменены.")
        
        return corrected
    
    def _generate_auto_reply(self, comment: Comment, check_results: Dict[str, Any], criteria: CommentModerationCriteria) -> str:
        """Генерация текста автоматического ответа"""
        violations = check_results.get('violations', [])
        
        # Базовые шаблоны ответов
        if 'forbidden_words' in violations:
            return "Спасибо за ваш комментарий. Пожалуйста, соблюдайте правила вежливости в общении."
        
        if 'spam' in violations:
            return "Ваш комментарий был помечен как спам. Если это ошибка, пожалуйста, свяжитесь с администрацией."
        
        if 'too_short' in violations:
            return "Ваш комментарий слишком короткий. Пожалуйста, уточните вашу мысль."
        
        if 'too_long' in violations:
            return "Ваш комментарий слишком длинный. Пожалуйста, сократите его до разумного размера."
        
        # Общий ответ
        return "Спасибо за ваш комментарий! Мы ценим ваше мнение."
    
    def _create_admin_reply(self, comment: Union[Comment, Any], reply_text: str):
        """Универсальное создание автоматического ответа администратора на комментарий"""
        try:
            logger.info(f"[CREATE_ADMIN_REPLY] Начало создания ответа администратора. Comment ID: {comment.id}, Type: {type(comment).__name__}, Reply length: {len(reply_text)}")
            
            # Определяем тип комментария и создаем соответствующий ответ
            comment_type = type(comment).__name__
            
            # Comment (Blog) - комментарии к статьям
            if comment_type == 'Comment' and hasattr(comment, 'post'):
                from Blog.models import Comment as CommentModel
                
                existing_reply = CommentModel.objects.filter(
                    post=comment.post,
                    parent=comment,
                    is_admin_reply=True
                ).first()
                
                if existing_reply:
                    existing_reply.content = reply_text
                    existing_reply.save(update_fields=['content'])
                    logger.info(f"[CREATE_ADMIN_REPLY] Обновлен существующий ответ {existing_reply.id} на Comment {comment.id}")
                else:
                    admin_reply = CommentModel.objects.create(
                        post=comment.post,
                        parent=comment,
                        author_comment='Администратор',
                        email='admin@example.com',
                        content=reply_text,
                        is_admin_reply=True,
                        active=True
                    )
                    logger.info(f"[CREATE_ADMIN_REPLY] Создан новый ответ {admin_reply.id} на Comment {comment.id}")
            
            # OtzivComment - комментарии к отзывам
            elif comment_type == 'OtzivComment' and hasattr(comment, 'otziv'):
                from home.models import OtzivComment
                
                existing_reply = OtzivComment.objects.filter(
                    otziv=comment.otziv,
                    parent=comment,
                    is_admin_reply=True
                ).first()
                
                if existing_reply:
                    existing_reply.content = reply_text
                    existing_reply.save(update_fields=['content'])
                    logger.info(f"[CREATE_ADMIN_REPLY] Обновлен существующий ответ {existing_reply.id} на OtzivComment {comment.id}")
                else:
                    admin_reply = OtzivComment.objects.create(
                        otziv=comment.otziv,
                        parent=comment,
                        author_name='Администратор',
                        author_email='admin@example.com',
                        content=reply_text,
                        is_admin_reply=True,
                        active=True
                    )
                    logger.info(f"[CREATE_ADMIN_REPLY] Создан новый ответ {admin_reply.id} на OtzivComment {comment.id}")
            
            # OrderComment - комментарии к заказам
            elif comment_type == 'OrderComment' and hasattr(comment, 'order'):
                from home.models import OrderComment
                from django.contrib.auth import get_user_model
                User = get_user_model()
                
                # Получаем администратора (первого суперпользователя или создаем системного)
                admin_user = User.objects.filter(is_superuser=True).first()
                if not admin_user:
                    logger.warning(f"[CREATE_ADMIN_REPLY] Не найден суперпользователь для создания ответа к OrderComment")
                    return
                
                existing_reply = OrderComment.objects.filter(
                    order=comment.order,
                    is_admin_comment=True
                ).first()
                
                if existing_reply:
                    existing_reply.content = reply_text
                    existing_reply.save(update_fields=['content'])
                    logger.info(f"[CREATE_ADMIN_REPLY] Обновлен существующий ответ {existing_reply.id} на OrderComment {comment.id}")
                else:
                    admin_reply = OrderComment.objects.create(
                        order=comment.order,
                        author=admin_user,
                        content=reply_text,
                        is_admin_comment=True
                    )
                    logger.info(f"[CREATE_ADMIN_REPLY] Создан новый ответ {admin_reply.id} на OrderComment {comment.id}")
            
            else:
                logger.warning(f"[CREATE_ADMIN_REPLY] Неизвестный тип комментария: {comment_type}")
                
        except Exception as e:
            logger.error(f"[CREATE_ADMIN_REPLY] КРИТИЧЕСКАЯ ОШИБКА при создании ответа администратора на комментарий {comment.id}: {str(e)}", exc_info=True)
            raise  # Пробрасываем ошибку дальше
    
    def check_criteria(self, comment: Union[Comment, Any], criteria: CommentModerationCriteria) -> Dict[str, Any]:
        """Универсальная проверка комментария по критериям"""
        results = {
            'passed': True,
            'checks': {},
            'violations': [],
        }
        
        criteria_data = criteria.criteria if isinstance(criteria.criteria, dict) else {}
        content = self._get_comment_content(comment)
        content_length = len(content)
        
        # Проверка длины
        if 'min_length' in criteria_data:
            min_len = criteria_data.get('min_length', 5)
            if content_length < min_len:
                results['passed'] = False
                results['violations'].append('too_short')
                results['checks']['length'] = False
        
        if 'max_length' in criteria_data:
            max_len = criteria_data.get('max_length', 2000)
            if content_length > max_len:
                results['passed'] = False
                results['violations'].append('too_long')
                results['checks']['length'] = False

        # Слишком много URL — типичный спам (если max_urls задан в критериях)
        if 'max_urls' in criteria_data:
            max_urls = criteria_data.get('max_urls', 2)
            try:
                max_urls = int(max_urls)
            except (TypeError, ValueError):
                max_urls = 2
            url_hits = content.lower().count('http://') + content.lower().count('https://')
            if url_hits > max_urls:
                results['passed'] = False
                results['violations'].append('spam')
                results['checks']['too_many_links'] = False
        
        # Проверка запрещенных слов
        if 'forbidden_words' in criteria_data:
            forbidden = criteria_data.get('forbidden_words', [])
            if forbidden:
                content_lower = content.lower()
                found_forbidden = []
                
                for word in forbidden:
                    if word.lower() in content_lower:
                        found_forbidden.append(word)
                
                if found_forbidden:
                    results['passed'] = False
                    results['violations'].append('forbidden_words')
                    results['checks']['forbidden_words'] = False
                    results['found_words'] = found_forbidden
        
        # Проверка спам-паттернов
        if 'spam_patterns' in criteria_data:
            spam_patterns = criteria_data.get('spam_patterns', [])
            if spam_patterns:
                content_lower = content.lower()
                found_patterns = []
                
                for pattern in spam_patterns:
                    if pattern.lower() in content_lower:
                        found_patterns.append(pattern)
                
                if found_patterns:
                    results['passed'] = False
                    results['violations'].append('spam')
                    results['checks']['spam'] = False
                    results['found_patterns'] = found_patterns
        
        return results
    
    def _determine_action(self, check_results: Dict[str, Any], criteria: CommentModerationCriteria) -> str:
        """Определение действия на основе результатов проверки и JSON «Действия» в критерии (delete/correct/reply)."""
        if check_results.get('passed', True):
            return 'approved'

        actions_data = criteria.actions if isinstance(criteria.actions, dict) else {}
        violations = check_results.get('violations', [])

        logger.info(
            f"[DETERMINE_ACTION] Violations: {violations}, "
            f"actions: delete={actions_data.get('delete')}, correct={actions_data.get('correct')}, reply={actions_data.get('reply')}"
        )

        if 'forbidden_words' in violations or 'spam' in violations:
            if actions_data.get('delete', True):
                logger.info("[DETERMINE_ACTION] Выбрано действие: deleted (forbidden_words/spam)")
                return 'deleted'

        if 'forbidden_words' in violations:
            if actions_data.get('correct', False):
                logger.info("[DETERMINE_ACTION] Выбрано действие: corrected (forbidden_words + correct=True)")
                return 'corrected'

        if 'too_short' in violations or 'too_long' in violations:
            if actions_data.get('correct', False):
                logger.info("[DETERMINE_ACTION] Выбрано действие: corrected (too_short/too_long + correct=True)")
                return 'corrected'

        if actions_data.get('reply', False):
            logger.info("[DETERMINE_ACTION] Выбрано действие: replied (reply=True)")
            return 'replied'

        if violations:
            logger.info("[DETERMINE_ACTION] Нарушения без подходящего действия в критерии — hidden (active=False)")
            return 'hidden'

        logger.info("[DETERMINE_ACTION] Выбрано действие: approved")
        return 'approved'


class SEOService:
    """Сервис SEO анализа"""
    
    def analyze_post(self, post: Post) -> Dict[str, Any]:
        """SEO анализ статьи"""
        analysis_data = {
            'score': 0,
            'checks': {},
            'recommendations': [],
        }
        
        score = 0
        max_score = 100
        
        # Проверка заголовка (20 баллов)
        title_score = self._check_title(post.title)
        analysis_data['checks']['title'] = title_score
        score += title_score.get('score', 0)
        
        # Проверка мета-описания (15 баллов)
        meta_desc_score = self._check_meta_description(post.description)
        analysis_data['checks']['meta_description'] = meta_desc_score
        score += meta_desc_score.get('score', 0)
        
        # Проверка контента (30 баллов)
        content_score = self._check_content(post.content)
        analysis_data['checks']['content'] = content_score
        score += content_score.get('score', 0)
        
        # Проверка изображения (10 баллов)
        image_score = self._check_image(post.kartinka)
        analysis_data['checks']['image'] = image_score
        score += image_score.get('score', 0)
        
        # Проверка структуры (15 баллов)
        structure_score = self._check_structure(post.content)
        analysis_data['checks']['structure'] = structure_score
        score += structure_score.get('score', 0)
        
        # Проверка ключевых слов (10 баллов)
        keywords_score = self._check_keywords(post)
        analysis_data['checks']['keywords'] = keywords_score
        score += keywords_score.get('score', 0)
        
        analysis_data['score'] = min(score, max_score)
        
        # Подготовка мета-тегов для сохранения
        meta_title = post.meta_title or post.title[:60] if post.title else ''
        meta_description = post.meta_description or post.description[:160] if post.description else ''
        focus_keyword = post.focus_keyword or ''
        
        # Создание или обновление SEO анализа
        seo_analysis, created = SEOAnalysis.objects.get_or_create(
            post=post,
            defaults={
                'seo_score': analysis_data['score'],
                'analysis_data': analysis_data,
                'meta_title': meta_title,
                'meta_description': meta_description,
                'focus_keyword': focus_keyword,
            }
        )
        
        if not created:
            seo_analysis.seo_score = analysis_data['score']
            seo_analysis.analysis_data = analysis_data
            seo_analysis.meta_title = meta_title
            seo_analysis.meta_description = meta_description
            seo_analysis.focus_keyword = focus_keyword
            seo_analysis.updated_at = timezone.now()
            seo_analysis.save()
        
        return {
            'analysis': seo_analysis,
            'score': analysis_data['score'],
            'data': analysis_data,
        }
    
    def _check_title(self, title: str) -> Dict[str, Any]:
        """Проверка заголовка"""
        if not title:
            return {'score': 0, 'message': 'Отсутствует заголовок'}
        
        length = len(title)
        score = 20
        
        if length < 30:
            score -= 10
            message = 'Заголовок слишком короткий (рекомендуется 30-60 символов)'
        elif length > 60:
            score -= 10
            message = 'Заголовок слишком длинный (рекомендуется 30-60 символов)'
        else:
            message = 'Заголовок оптимальной длины'
        
        return {'score': max(0, score), 'length': length, 'message': message}
    
    def _check_meta_description(self, description: str) -> Dict[str, Any]:
        """Проверка мета-описания"""
        if not description:
            return {'score': 0, 'message': 'Отсутствует мета-описание'}
        
        length = len(description)
        score = 15
        
        if length < 120:
            score -= 7
            message = 'Мета-описание слишком короткое (рекомендуется 120-160 символов)'
        elif length > 160:
            score -= 7
            message = 'Мета-описание слишком длинное (рекомендуется 120-160 символов)'
        else:
            message = 'Мета-описание оптимальной длины'
        
        return {'score': max(0, score), 'length': length, 'message': message}
    
    def _check_content(self, content: str) -> Dict[str, Any]:
        """Проверка контента"""
        if not content:
            return {'score': 0, 'message': 'Отсутствует контент'}
        
        # Удаляем HTML теги для подсчета
        import re
        text_content = re.sub(r'<[^>]+>', '', content)
        word_count = len(text_content.split())
        
        score = 30
        
        if word_count < 300:
            score -= 15
            message = f'Контент слишком короткий ({word_count} слов, рекомендуется минимум 300)'
        elif word_count < 500:
            score -= 5
            message = f'Контент можно расширить ({word_count} слов, рекомендуется 500+)'
        else:
            message = f'Контент достаточной длины ({word_count} слов)'
        
        return {'score': max(0, score), 'word_count': word_count, 'message': message}
    
    def _check_image(self, image) -> Dict[str, Any]:
        """Проверка изображения"""
        if not image:
            return {'score': 0, 'message': 'Отсутствует изображение'}
        
        return {'score': 10, 'message': 'Изображение присутствует'}
    
    def _check_structure(self, content: str) -> Dict[str, Any]:
        """Проверка структуры контента"""
        if not content:
            return {'score': 0, 'message': 'Отсутствует контент'}
        
        score = 15
        has_h2 = '<h2' in content.lower()
        has_h3 = '<h3' in content.lower()
        has_lists = '<ul' in content.lower() or '<ol' in content.lower()
        has_paragraphs = '<p' in content.lower()
        
        if not has_h2:
            score -= 5
        if not has_paragraphs:
            score -= 5
        if not has_lists:
            score -= 3
        
        message = f'Структура: H2={has_h2}, H3={has_h3}, списки={has_lists}, параграфы={has_paragraphs}'
        
        return {'score': max(0, score), 'message': message}
    
    def _check_keywords(self, post: Post) -> Dict[str, Any]:
        """Проверка ключевых слов"""
        score = 10
        
        # Проверка тегов
        tags_count = post.tags.count()
        if tags_count == 0:
            score -= 5
            message = 'Отсутствуют теги'
        elif tags_count < 3:
            score -= 2
            message = f'Мало тегов ({tags_count}, рекомендуется 3-5)'
        else:
            message = f'Теги присутствуют ({tags_count})'
        
        return {'score': max(0, score), 'tags_count': tags_count, 'message': message}
    
    def generate_meta_tags(self, post: Post) -> Dict[str, str]:
        """Генерация мета-тегов"""
        # Базовые мета-теги на основе заголовка и описания
        meta_title = post.title[:60] if post.title else ''
        meta_description = post.description[:160] if post.description else ''
        
        # Если описания нет, берем первые слова из контента
        if not meta_description and post.content:
            import re
            text_content = re.sub(r'<[^>]+>', '', post.content)
            words = text_content.split()[:25]
            meta_description = ' '.join(words)[:160]
        
        return {
            'meta_title': meta_title,
            'meta_description': meta_description,
        }


class NotificationService:
    """Сервис уведомлений модераторов"""
    
    def notify_article_pending(self, moderation: ArticleModeration):
        """Уведомление о статье на модерации"""
        moderators = User.objects.filter(is_staff=True)
        
        for moderator in moderators:
            ModerationNotification.objects.create(
                recipient=moderator,
                notification_type='article_pending',
                title=f'Статья "{moderation.post.title}" ожидает модерации',
                message=f'Статья от {moderation.post.author.get_full_name() or moderation.post.author.username} требует проверки.',
                article_moderation=moderation
            )
    
    def notify_comment_pending(self, moderation: CommentModeration):
        """Уведомление о комментарии на модерации"""
        moderators = User.objects.filter(is_staff=True)
        
        for moderator in moderators:
            ModerationNotification.objects.create(
                recipient=moderator,
                notification_type='comment_pending',
                title=f'Новый комментарий требует проверки',
                message=f'Комментарий от {moderation.comment.author_comment} на статью "{moderation.comment.post.title}"',
                comment_moderation=moderation
            )
    
    def notify_seo_low_score(self, analysis: SEOAnalysis):
        """Уведомление о низком SEO score"""
        if analysis.seo_score < 50:
            moderators = User.objects.filter(is_staff=True)
            
            for moderator in moderators:
                ModerationNotification.objects.create(
                    recipient=moderator,
                    notification_type='seo_low_score',
                    title=f'Низкий SEO score для статьи "{analysis.post.title}"',
                    message=f'SEO score статьи составляет {analysis.seo_score} баллов. Требуется оптимизация.',
                    seo_analysis=analysis
                )


class StatisticsService:
    """Сервис статистики модерации"""
    
    def update_daily_statistics(self, target_date: date = None):
        """Обновление дневной статистики"""
        if not target_date:
            target_date = date.today()
        
        # Статистика по статьям
        articles_pending = ArticleModeration.objects.filter(
            status='pending',
            submitted_at__date=target_date
        ).count()
        
        articles_approved = ArticleModeration.objects.filter(
            status='approved',
            moderated_at__date=target_date
        ).count()
        
        articles_rejected = ArticleModeration.objects.filter(
            status='rejected',
            moderated_at__date=target_date
        ).count()
        
        articles_needs_revision = ArticleModeration.objects.filter(
            status='needs_revision',
            moderated_at__date=target_date
        ).count()
        
        # Статистика по комментариям
        comments_pending = CommentModeration.objects.filter(
            action__isnull=True,
            checked_at__date=target_date
        ).count()
        
        comments_approved = CommentModeration.objects.filter(
            action='approved',
            moderated_at__date=target_date
        ).count()
        
        comments_deleted = CommentModeration.objects.filter(
            action='deleted',
            moderated_at__date=target_date
        ).count()
        
        comments_corrected = CommentModeration.objects.filter(
            action='corrected',
            moderated_at__date=target_date
        ).count()
        
        # SEO статистика
        seo_analyses = SEOAnalysis.objects.filter(analyzed_at__date=target_date)
        seo_analyzed = seo_analyses.count()
        seo_avg_score = seo_analyses.aggregate(Avg('seo_score'))['seo_score__avg'] or 0
        seo_high_score = seo_analyses.filter(seo_score__gte=80).count()
        seo_low_score = seo_analyses.filter(seo_score__lt=50).count()
        
        # Среднее время модерации
        moderated_articles = ArticleModeration.objects.filter(
            moderated_at__date=target_date,
            submitted_at__isnull=False
        )
        
        avg_time = 0
        if moderated_articles.exists():
            total_hours = 0
            count = 0
            for mod in moderated_articles:
                if mod.moderated_at and mod.submitted_at:
                    delta = mod.moderated_at - mod.submitted_at
                    total_hours += delta.total_seconds() / 3600
                    count += 1
            if count > 0:
                avg_time = total_hours / count
        
        # Создание или обновление статистики
        stats, created = ModerationStatistics.objects.update_or_create(
            date=target_date,
            defaults={
                'articles_pending': articles_pending,
                'articles_approved': articles_approved,
                'articles_rejected': articles_rejected,
                'articles_needs_revision': articles_needs_revision,
                'comments_pending': comments_pending,
                'comments_approved': comments_approved,
                'comments_deleted': comments_deleted,
                'comments_corrected': comments_corrected,
                'seo_analyzed': seo_analyzed,
                'seo_avg_score': round(seo_avg_score, 2),
                'seo_high_score': seo_high_score,
                'seo_low_score': seo_low_score,
                'avg_moderation_time': round(avg_time, 2),
            }
        )
        
        return stats
    
    def get_statistics_period(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """Получение статистики за период"""
        stats = ModerationStatistics.objects.filter(
            date__gte=start_date,
            date__lte=end_date
        )
        
        return {
            'total_articles_pending': stats.aggregate(Sum('articles_pending'))['articles_pending__sum'] or 0,
            'total_articles_approved': stats.aggregate(Sum('articles_approved'))['articles_approved__sum'] or 0,
            'total_articles_rejected': stats.aggregate(Sum('articles_rejected'))['articles_rejected__sum'] or 0,
            'total_comments_approved': stats.aggregate(Sum('comments_approved'))['comments_approved__sum'] or 0,
            'total_comments_deleted': stats.aggregate(Sum('comments_deleted'))['comments_deleted__sum'] or 0,
            'avg_seo_score': stats.aggregate(Avg('seo_avg_score'))['seo_avg_score__avg'] or 0,
            'avg_moderation_time': stats.aggregate(Avg('avg_moderation_time'))['avg_moderation_time__avg'] or 0,
        }

