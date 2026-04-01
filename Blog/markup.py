"""
Нормализация разметки статей: Markdown → HTML, удаление дубликатов FAQ в теле.
"""
import logging
import re

logger = logging.getLogger(__name__)

# Заголовки FAQ в основном тексте (доп. секция с FAQ генерируется отдельно)
_FAQ_IN_HEADING = re.compile(
    r'(?:частые вопросы|часто задаваемые|❓\s*часты|\bfaq\b)',
    re.IGNORECASE,
)


def strip_leading_inline_faq_markdown(text: str) -> str:
    """
    Убирает блок «частые вопросы» в начале, если модель всё же вставила FAQ в основной текст.
    Начало основного текста — первый заголовок не-вопрос (не «Как …?» на короткой строке) или явный H1 (# ).
    """
    if not text or len(text) < 30:
        return text
    window = text[:12000]
    if not _FAQ_IN_HEADING.search(window):
        return text
    m = re.search(
        r'(?m)^#{1,6}\s*[^\n]*(?:частые вопросы|часто задаваемые|❓)[^\n]*\s*$',
        window,
    )
    if not m:
        return text
    sub = text[m.start() :]
    _q_heading = re.compile(
        r'^(Как|Почему|Что|Какие|Когда|Можно ли|Стоит ли|Сколько)\b.+[?？]\s*$',
        re.IGNORECASE,
    )

    def _main_start(body: str) -> int | None:
        for m2 in re.finditer(r'(?m)^(#{1,6})\s+(.+?)\s*$', body):
            hashes, title = m2.group(1), m2.group(2).strip()
            if len(hashes) == 1 and hashes == '#':
                return m2.start()
            if len(title) >= 40 and not _q_heading.match(title):
                return m2.start()
        return None

    cut = _main_start(sub)
    if cut is None or cut < 10:
        return text
    prefix = text[: m.start()].rstrip()
    rest = sub[cut:].lstrip()
    if not rest:
        return text
    return (prefix + '\n\n' + rest).strip() if prefix else rest


def strip_leading_inline_faq_html_fragment(text: str) -> str:
    """Удаляет ведущий <h2>…частые вопросы…</h2> и следующие пары h3/p до следующего h1/h2."""
    if not text or 'частые' not in text.lower()[:6000]:
        return text
    m = re.search(
        r'(?is)^\s*<h2[^>]*>[^<]*(?:частые вопросы|часто задаваем|❓)[^<]*</h2>\s*',
        text[:8000],
    )
    if not m:
        return text
    tail = text[m.end() :]
    # пропускаем типичные пары вопрос–ответ
    end_qa = 0
    qa_pat = re.compile(
        r'(?is)^(?:<h3[^>]*>.*?</h3>\s*<p[^>]*>.*?</p>\s*)+',
    )
    qm = qa_pat.match(tail)
    if qm:
        end_qa = qm.end()
    trimmed = tail[end_qa:].lstrip()
    return (text[: m.start()] + trimmed).strip()


def strip_trailing_faq_rubric_markdown(text: str) -> str:
    """Убирает хвост вида «## HTML-блок FAQ», если модель вывела служебный заголовок вместо чистого HTML."""
    if not text:
        return text
    return re.sub(
        r'(?is)\n{1,3}#{1,6}\s*.*?(?:HTML[-\s]*блок\s*)?FAQ.*$',
        '',
        text,
        count=1,
    )


def looks_like_html_fragment(s: str) -> bool:
    if not s:
        return False
    head = s[:3500].lstrip()
    return bool(
        re.search(r'<\s*(h[1-6]|p|div|section|ul|ol|blockquote|table)\b', head, re.I)
    )


def article_markup_to_html(raw: str) -> str:
    """
    Если текст похож на Markdown — конвертирует в HTML.
    Уже HTML не трогает (эвристика по тегам).
    """
    if not raw or not raw.strip():
        return raw or ''
    s = raw.strip()
    if looks_like_html_fragment(s):
        return raw
    try:
        import markdown

        return markdown.markdown(
            s,
            extensions=['extra', 'nl2br'],
            output_format='html',
        )
    except ImportError:
        logger.warning('Пакет markdown не установлен — тело статьи не конвертировано из MD')
        return raw


def normalize_additional_section_to_html(fragment: str) -> str:
    """Доп. секция должна быть HTML; если пришёл Markdown — превращаем в HTML."""
    if not fragment or not fragment.strip():
        return fragment or ''
    s = fragment.strip()
    s = re.sub(r'```html\s*', '', s, flags=re.I)
    s = re.sub(r'```\s*', '', s)
    s = s.strip()
    if looks_like_html_fragment(s):
        return s
    return article_markup_to_html(s)


__all__ = [
    'article_markup_to_html',
    'normalize_additional_section_to_html',
    'strip_leading_inline_faq_markdown',
    'strip_leading_inline_faq_html_fragment',
    'strip_trailing_faq_rubric_markdown',
    'looks_like_html_fragment',
]
