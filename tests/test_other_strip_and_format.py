"""Тесты для strip_email_quotes, strip_html_quotes, format_timetable_html из other.py."""
import pytest
from other import strip_email_quotes, strip_html_quotes, format_timetable_html


# ─── strip_email_quotes ───

class TestStripEmailQuotes:
    def test_empty_string(self):
        assert strip_email_quotes('') == ''

    def test_none_returns_none(self):
        assert strip_email_quotes(None) is None

    def test_no_quotes(self):
        text = 'Привет!\nКак дела?'
        assert strip_email_quotes(text) == text

    def test_strips_quoted_lines(self):
        text = 'Мой ответ\n> Цитата\n> Еще цитата'
        assert strip_email_quotes(text) == 'Мой ответ'

    def test_strips_on_wrote_marker(self):
        text = 'Мой ответ\nOn Mon, 1 Jan 2024 someone wrote:\nЦитата'
        assert strip_email_quotes(text) == 'Мой ответ'

    def test_strips_russian_napisal_marker(self):
        text = 'Ответ\nИванов И.И. 01.01.2024 написал:'
        assert strip_email_quotes(text) == 'Ответ'

    def test_strips_original_message_marker(self):
        text = 'Ответ\n---- Original Message ----\nСтарое сообщение'
        assert strip_email_quotes(text) == 'Ответ'

    def test_strips_forwarded_message_marker(self):
        text = 'Ответ\n-- Forwarded message --\nПересланное'
        assert strip_email_quotes(text) == 'Ответ'

    def test_strips_underscore_separator(self):
        text = 'Ответ\n__\nСтарое'
        assert strip_email_quotes(text) == 'Ответ'

    def test_preserves_multiline_reply(self):
        text = 'Строка 1\nСтрока 2\nСтрока 3'
        assert strip_email_quotes(text) == text

    def test_strips_trailing_whitespace(self):
        text = 'Ответ  \n> Цитата'
        result = strip_email_quotes(text)
        assert result == 'Ответ'

    def test_original_message_case_insensitive(self):
        text = 'Ответ\n-- original message --\nСтарое'
        assert strip_email_quotes(text) == 'Ответ'


# ─── strip_html_quotes ───

class TestStripHtmlQuotes:
    def test_empty_string(self):
        assert strip_html_quotes('') == ''

    def test_none_returns_none(self):
        assert strip_html_quotes(None) is None

    def test_no_quotes(self):
        html = '<p>Привет</p>'
        assert strip_html_quotes(html) == html

    def test_strips_gmail_quote(self):
        html = '<p>Ответ</p><div class="gmail_quote">Цитата</div>'
        assert strip_html_quotes(html) == '<p>Ответ</p>'

    def test_strips_outlook_appendonsend(self):
        html = '<p>Ответ</p><div id="appendonsend">Старое</div>'
        assert strip_html_quotes(html) == '<p>Ответ</p>'

    def test_strips_outlook_divRplyFwdMsg(self):
        html = '<p>Ответ</p><div id="divRplyFwdMsg">Старое</div>'
        assert strip_html_quotes(html) == '<p>Ответ</p>'

    def test_strips_blockquote(self):
        html = '<p>Ответ</p><blockquote>Цитата</blockquote>'
        assert strip_html_quotes(html) == '<p>Ответ</p>'

    def test_strips_hr_separator(self):
        html = '<p>Ответ</p><hr /><p>Старое</p>'
        assert strip_html_quotes(html) == '<p>Ответ</p>'

    def test_strips_hr_without_slash(self):
        html = '<p>Ответ</p><hr><p>Старое</p>'
        assert strip_html_quotes(html) == '<p>Ответ</p>'

    def test_only_first_quote_stripped(self):
        html = '<p>Ответ</p><div class="gmail_quote">Цитата1</div><blockquote>Цитата2</blockquote>'
        result = strip_html_quotes(html)
        assert 'Ответ' in result
        assert 'gmail_quote' not in result


# ─── format_timetable_html ───

class TestFormatTimetableHtml:
    def test_empty_string(self):
        result = format_timetable_html('')
        assert result == '<br>'

    def test_teacher_header(self):
        result = format_timetable_html('Преподаватель Иванов И.И.')
        assert '<h2' in result
        assert 'Иванов И.И.' in result

    def test_group_header(self):
        result = format_timetable_html('Группа 307')
        assert '<h2' in result
        assert '307' in result

    def test_day_of_week_line(self):
        result = format_timetable_html('ПОНЕДЕЛЬНИК - 01.01.2024')
        assert '<h3' in result
        assert 'ПОНЕДЕЛЬНИК' in result

    def test_empty_lesson_line(self):
        result = format_timetable_html('1. -')
        assert '<div' in result
        assert '1. -' in result

    def test_lesson_with_data(self):
        result = format_timetable_html('1. 09:00-10:30 (л) Математика 2/311 307 гр.')
        assert '<div' in result
        assert 'border-left' in result
        assert 'Математика' in result

    def test_no_lessons_message(self):
        result = format_timetable_html('Не найдено занятий на текущую неделю')
        assert '<p' in result
        assert 'italic' in result

    def test_no_saved_message(self):
        result = format_timetable_html('Нет сохраненных групп')
        assert '<p' in result
        assert 'italic' in result

    def test_change_notification_line(self):
        result = format_timetable_html('Расписание было изменено')
        assert 'font-weight: bold' in result
        assert 'было изменено' in result

    def test_regular_text(self):
        result = format_timetable_html('Просто текст')
        assert '<p>' in result
        assert 'Просто текст' in result

    def test_multiline(self):
        text = 'Преподаватель Иванов И.И.\nПОНЕДЕЛЬНИК - 01.01.2024\n1. -\n2. 09:00 (л) Математика'
        result = format_timetable_html(text)
        assert '<h2' in result
        assert '<h3' in result
        assert result.count('<div') >= 2

    def test_empty_line_produces_br(self):
        result = format_timetable_html('Строка 1\n\nСтрока 2')
        assert '<br>' in result
