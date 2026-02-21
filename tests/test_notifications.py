"""Тесты для рассылки уведомлений с новой нормализованной схемой."""
import sqlite3
import asyncio
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from sql_db import (
    _collect_notification_messages_normalized,
    send_notifications_email,
    send_notifications_vk_chat,
    send_notifications_vk_user,
    send_notifications_telegram,
    send_notifications_vk_both_async,
)
from constants import MESSAGE_SPLIT_SENTINEL, MESSAGE_PREFIX


# ─── Хелперы для создания in-memory БД ───

def _create_db_and_populate(users_data):
    """Создаёт in-memory БД с новой схемой и наполняет данными.

    users_data: список dict с ключами:
        platform, platform_id, notification, lesson_time, teachers, groups
    Возвращает (conn, cursor).
    """
    conn = sqlite3.connect(':memory:')
    conn.execute('PRAGMA foreign_keys=ON')
    conn.row_factory = sqlite3.Row
    conn.execute("""CREATE TABLE users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        platform TEXT NOT NULL,
        platform_id TEXT NOT NULL,
        notification INTEGER NOT NULL DEFAULT 1,
        lesson_time INTEGER NOT NULL DEFAULT 1,
        UNIQUE(platform, platform_id))""")
    conn.execute("""CREATE TABLE user_groups (
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        group_id TEXT NOT NULL,
        PRIMARY KEY (user_id, group_id))""")
    conn.execute("""CREATE TABLE user_teachers (
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        teacher TEXT NOT NULL,
        PRIMARY KEY (user_id, teacher))""")
    for u in users_data:
        conn.execute(
            'INSERT INTO users (platform, platform_id, notification, lesson_time) VALUES (?, ?, ?, ?)',
            (u['platform'], u['platform_id'], u.get('notification', 1), u.get('lesson_time', 1)))
        uid = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
        for t in u.get('teachers', []):
            conn.execute('INSERT INTO user_teachers (user_id, teacher) VALUES (?, ?)', (uid, t))
        for g in u.get('groups', []):
            conn.execute('INSERT INTO user_groups (user_id, group_id) VALUES (?, ?)', (uid, g))
    conn.commit()
    return conn


def _make_user_row(notification=1, lesson_time=1):
    """Создаёт sqlite3.Row-подобный dict для _collect_notification_messages_normalized."""
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    conn.execute('CREATE TABLE tmp (id INTEGER, platform TEXT, platform_id TEXT, notification INTEGER, lesson_time INTEGER)')
    conn.execute('INSERT INTO tmp VALUES (1, "email", "a@b.com", ?, ?)', (notification, lesson_time))
    row = conn.execute('SELECT * FROM tmp').fetchone()
    conn.close()
    return row


# ─── _collect_notification_messages_normalized ───

class TestCollectNotificationMessages:
    def test_empty_lists_returns_empty(self):
        row = _make_user_row()
        result = _collect_notification_messages_normalized(
            row, ['Иванов'], ['307'], [], [], [], [])
        assert result == []

    def test_matching_teacher_current_week(self):
        row = _make_user_row()
        with patch('sql_db.timetable', return_value='расписание') as mock_tt:
            result = _collect_notification_messages_normalized(
                row, ['Иванов'], [], [], [], ['Иванов'], [])
        assert len(result) == 1
        assert 'текущую' in result[0][0]
        assert 'преподавателя' in result[0][0]
        assert 'Иванов' in result[0][0]
        mock_tt.assert_called_once_with(teacher='Иванов')

    def test_matching_teacher_next_week(self):
        row = _make_user_row()
        with patch('sql_db.timetable', return_value='расписание'):
            result = _collect_notification_messages_normalized(
                row, ['Иванов'], [], [], [], [], ['Иванов'])
        assert len(result) == 1
        assert 'следующую' in result[0][0]

    def test_matching_group_current_week(self):
        row = _make_user_row()
        with patch('sql_db.timetable', return_value='расписание') as mock_tt:
            result = _collect_notification_messages_normalized(
                row, [], ['307'], ['307'], [], [], [])
        assert len(result) == 1
        assert 'текущую' in result[0][0]
        assert 'группы' in result[0][0]
        assert '307' in result[0][0]
        mock_tt.assert_called_once_with(group_id='307')

    def test_matching_group_next_week(self):
        row = _make_user_row()
        with patch('sql_db.timetable', return_value='расписание') as mock_tt:
            result = _collect_notification_messages_normalized(
                row, [], ['307'], [], ['307'], [], [])
        assert len(result) == 1
        assert 'следующую' in result[0][0]
        mock_tt.assert_called_once_with(group_id='307', next='YES')

    def test_no_match_returns_empty(self):
        row = _make_user_row()
        with patch('sql_db.timetable', return_value='расписание'):
            result = _collect_notification_messages_normalized(
                row, ['Иванов'], ['307'], ['999'], ['999'], ['Петров'], ['Петров'])
        assert result == []

    def test_exact_match_no_substring(self):
        """Проверяем, что 'Иванов' НЕ совпадает с 'Иванова' (баг старой схемы)."""
        row = _make_user_row()
        with patch('sql_db.timetable', return_value='расписание'):
            result = _collect_notification_messages_normalized(
                row, ['Иванова'], [], [], [], ['Иванов'], [])
        assert result == []

    def test_lesson_time_disabled(self):
        row = _make_user_row(lesson_time=0)
        with patch('sql_db.timetable', return_value='расписание') as mock_tt:
            result = _collect_notification_messages_normalized(
                row, ['Иванов'], [], [], [], ['Иванов'], [])
        assert len(result) == 1
        mock_tt.assert_called_once_with(teacher='Иванов', lesson_time='YES')

    def test_multiple_matches(self):
        row = _make_user_row()
        with patch('sql_db.timetable', return_value='расписание'):
            result = _collect_notification_messages_normalized(
                row, ['Иванов', 'Петров'], ['307', '308'],
                ['307', '308'], ['307'], ['Иванов', 'Петров'], ['Иванов'])
        # teacher current: Иванов, Петров (2)
        # teacher next: Иванов (1)
        # group current: 307, 308 (2)
        # group next: 307 (1)
        assert len(result) == 6

    def test_next_week_kwarg(self):
        row = _make_user_row()
        with patch('sql_db.timetable', return_value='расписание') as mock_tt:
            _collect_notification_messages_normalized(
                row, ['Иванов'], [], [], [], [], ['Иванов'])
        mock_tt.assert_called_once_with(teacher='Иванов', next='YES')


# ─── send_notifications_email ───

class TestSendNotificationsEmail:
    @patch('sql_db.connection_to_sql')
    @patch('sql_db.sendMail')
    @patch('sql_db.timetable', return_value='расписание')
    @patch('sql_db.format_timetable_html', return_value='<html>расписание</html>')
    def test_sends_email_to_matching_users(self, mock_html, mock_tt, mock_mail, mock_conn):
        conn = _create_db_and_populate([
            {'platform': 'email', 'platform_id': 'user@test.com', 'teachers': ['Иванов'], 'groups': []},
        ])
        mock_conn.return_value = conn
        result = send_notifications_email(
            group_list_current_week=[], group_list_next_week=[],
            teacher_list_current_week=['Иванов'], teacher_list_next_week=[])
        assert result is True
        mock_mail.assert_called_once()
        call_kwargs = mock_mail.call_args
        assert call_kwargs[1]['to_email'] == 'user@test.com'
        assert call_kwargs[1]['subject'] == 'Изменения в расписании'

    @patch('sql_db.connection_to_sql')
    @patch('sql_db.sendMail')
    @patch('sql_db.timetable', return_value='расписание')
    def test_no_email_when_no_match(self, mock_tt, mock_mail, mock_conn):
        conn = _create_db_and_populate([
            {'platform': 'email', 'platform_id': 'user@test.com', 'teachers': ['Петров'], 'groups': []},
        ])
        mock_conn.return_value = conn
        result = send_notifications_email(
            group_list_current_week=[], group_list_next_week=[],
            teacher_list_current_week=['Иванов'], teacher_list_next_week=[])
        assert result is True
        mock_mail.assert_not_called()

    @patch('sql_db.connection_to_sql')
    @patch('sql_db.sendMail')
    @patch('sql_db.timetable', return_value='расписание')
    def test_skips_users_with_notifications_off(self, mock_tt, mock_mail, mock_conn):
        conn = _create_db_and_populate([
            {'platform': 'email', 'platform_id': 'off@test.com', 'notification': 0, 'teachers': ['Иванов'], 'groups': []},
            {'platform': 'email', 'platform_id': 'on@test.com', 'notification': 1, 'teachers': ['Иванов'], 'groups': []},
        ])
        mock_conn.return_value = conn
        result = send_notifications_email(
            group_list_current_week=[], group_list_next_week=[],
            teacher_list_current_week=['Иванов'], teacher_list_next_week=[])
        assert result is True
        assert mock_mail.call_count == 1
        assert mock_mail.call_args[1]['to_email'] == 'on@test.com'

    @patch('sql_db.connection_to_sql')
    @patch('sql_db.sendMail')
    @patch('sql_db.timetable', return_value='расписание')
    def test_ignores_non_email_platforms(self, mock_tt, mock_mail, mock_conn):
        conn = _create_db_and_populate([
            {'platform': 'telegram', 'platform_id': '123', 'teachers': ['Иванов'], 'groups': []},
        ])
        mock_conn.return_value = conn
        send_notifications_email(
            group_list_current_week=[], group_list_next_week=[],
            teacher_list_current_week=['Иванов'], teacher_list_next_week=[])
        mock_mail.assert_not_called()

    @patch('sql_db.connection_to_sql')
    @patch('sql_db.sendMail')
    @patch('sql_db.timetable', return_value='расписание')
    @patch('sql_db.format_timetable_html', return_value='<html></html>')
    def test_multiple_users_multiple_emails(self, mock_html, mock_tt, mock_mail, mock_conn):
        conn = _create_db_and_populate([
            {'platform': 'email', 'platform_id': 'a@test.com', 'teachers': ['Иванов'], 'groups': []},
            {'platform': 'email', 'platform_id': 'b@test.com', 'teachers': ['Иванов'], 'groups': ['307']},
        ])
        mock_conn.return_value = conn
        send_notifications_email(
            group_list_current_week=['307'], group_list_next_week=[],
            teacher_list_current_week=['Иванов'], teacher_list_next_week=[])
        assert mock_mail.call_count == 2


# ─── send_notifications_vk_chat / send_notifications_vk_user ───

class TestSendNotificationsVk:
    @patch('sql_db.connection_to_sql')
    @patch('sql_db.write_msg_vk_chat', new_callable=AsyncMock)
    @patch('sql_db.timetable', return_value='расписание')
    def test_vk_chat_sends_messages(self, mock_tt, mock_send, mock_conn):
        conn = _create_db_and_populate([
            {'platform': 'vk_chat', 'platform_id': '100', 'teachers': [], 'groups': ['307']},
        ])
        mock_conn.return_value = conn
        result = send_notifications_vk_chat(
            group_list_current_week=['307'], group_list_next_week=[],
            teacher_list_current_week=[], teacher_list_next_week=[])
        assert result is True
        assert mock_send.call_count == 2  # msg_text + timetable

    @patch('sql_db.connection_to_sql')
    @patch('sql_db.write_msg_vk_user', new_callable=AsyncMock)
    @patch('sql_db.timetable', return_value='расписание')
    def test_vk_user_sends_messages(self, mock_tt, mock_send, mock_conn):
        conn = _create_db_and_populate([
            {'platform': 'vk_user', 'platform_id': '200', 'teachers': ['Иванов'], 'groups': []},
        ])
        mock_conn.return_value = conn
        result = send_notifications_vk_user(
            group_list_current_week=[], group_list_next_week=[],
            teacher_list_current_week=['Иванов'], teacher_list_next_week=[])
        assert result is True
        assert mock_send.call_count == 2

    @patch('sql_db.connection_to_sql')
    @patch('sql_db.write_msg_vk_chat', new_callable=AsyncMock)
    @patch('sql_db.timetable', return_value='расписание')
    def test_vk_chat_no_match_no_send(self, mock_tt, mock_send, mock_conn):
        conn = _create_db_and_populate([
            {'platform': 'vk_chat', 'platform_id': '100', 'teachers': [], 'groups': ['308']},
        ])
        mock_conn.return_value = conn
        send_notifications_vk_chat(
            group_list_current_week=['307'], group_list_next_week=[],
            teacher_list_current_week=[], teacher_list_next_week=[])
        mock_send.assert_not_called()

    @patch('sql_db.connection_to_sql')
    @patch('sql_db.write_msg_vk_user', new_callable=AsyncMock)
    @patch('sql_db.timetable', return_value='расписание')
    def test_vk_user_skips_notification_off(self, mock_tt, mock_send, mock_conn):
        conn = _create_db_and_populate([
            {'platform': 'vk_user', 'platform_id': '200', 'notification': 0, 'teachers': ['Иванов'], 'groups': []},
        ])
        mock_conn.return_value = conn
        send_notifications_vk_user(
            group_list_current_week=[], group_list_next_week=[],
            teacher_list_current_week=['Иванов'], teacher_list_next_week=[])
        mock_send.assert_not_called()

    @patch('sql_db.connection_to_sql')
    @patch('sql_db.write_msg_vk_chat', new_callable=AsyncMock)
    @patch('sql_db.timetable', return_value='расписание')
    def test_vk_chat_multiple_groups(self, mock_tt, mock_send, mock_conn):
        conn = _create_db_and_populate([
            {'platform': 'vk_chat', 'platform_id': '100', 'teachers': [], 'groups': ['307', '308']},
        ])
        mock_conn.return_value = conn
        send_notifications_vk_chat(
            group_list_current_week=['307', '308'], group_list_next_week=[],
            teacher_list_current_week=[], teacher_list_next_week=[])
        # 2 groups × 2 messages each (text + timetable)
        assert mock_send.call_count == 4


# ─── send_notifications_telegram ───

class TestSendNotificationsTelegram:
    @patch('sql_db.connection_to_sql')
    @patch('sql_db.write_msg_telegram', new_callable=AsyncMock)
    @patch('sql_db.timetable', return_value='расписание')
    def test_telegram_sends_messages(self, mock_tt, mock_send, mock_conn):
        conn = _create_db_and_populate([
            {'platform': 'telegram', 'platform_id': '111', 'teachers': ['Иванов'], 'groups': []},
        ])
        mock_conn.return_value = conn
        result = send_notifications_telegram(
            group_list_current_week=[], group_list_next_week=[],
            teacher_list_current_week=['Иванов'], teacher_list_next_week=[])
        assert result is True
        assert mock_send.call_count == 2
        # Проверяем что отправлено нужному пользователю
        calls = mock_send.call_args_list
        for call in calls:
            assert call[1]['tg_id'] == '111'

    @patch('sql_db.connection_to_sql')
    @patch('sql_db.write_msg_telegram', new_callable=AsyncMock)
    @patch('sql_db.timetable', return_value='расписание')
    def test_telegram_no_match(self, mock_tt, mock_send, mock_conn):
        conn = _create_db_and_populate([
            {'platform': 'telegram', 'platform_id': '111', 'teachers': [], 'groups': ['999']},
        ])
        mock_conn.return_value = conn
        send_notifications_telegram(
            group_list_current_week=['307'], group_list_next_week=[],
            teacher_list_current_week=[], teacher_list_next_week=[])
        mock_send.assert_not_called()

    @patch('sql_db.connection_to_sql')
    @patch('sql_db.write_msg_telegram', new_callable=AsyncMock)
    @patch('sql_db.timetable', return_value='расписание')
    def test_telegram_skips_disabled_notifications(self, mock_tt, mock_send, mock_conn):
        conn = _create_db_and_populate([
            {'platform': 'telegram', 'platform_id': '111', 'notification': 0, 'teachers': ['Иванов'], 'groups': []},
        ])
        mock_conn.return_value = conn
        send_notifications_telegram(
            group_list_current_week=[], group_list_next_week=[],
            teacher_list_current_week=['Иванов'], teacher_list_next_week=[])
        mock_send.assert_not_called()

    @patch('sql_db.connection_to_sql')
    @patch('sql_db.write_msg_telegram', new_callable=AsyncMock)
    @patch('sql_db.timetable')
    def test_telegram_splits_long_timetable(self, mock_tt, mock_send, mock_conn):
        """Расписание с сентинелем отправляется несколькими сообщениями."""
        conn = _create_db_and_populate([
            {'platform': 'telegram', 'platform_id': '111', 'teachers': ['Иванов'], 'groups': []},
        ])
        mock_conn.return_value = conn
        mock_tt.return_value = f'часть1{MESSAGE_SPLIT_SENTINEL}часть2'
        result = send_notifications_telegram(
            group_list_current_week=[], group_list_next_week=[],
            teacher_list_current_week=['Иванов'], teacher_list_next_week=[])
        assert result is True
        # 1 msg_text + 2 части расписания = 3 вызова
        assert mock_send.call_count == 3
        calls = mock_send.call_args_list
        assert calls[1][1]['message'] == 'часть1'
        assert calls[2][1]['message'] == 'часть2'

    @patch('sql_db.connection_to_sql')
    @patch('sql_db.write_msg_telegram', new_callable=AsyncMock)
    @patch('sql_db.timetable')
    def test_telegram_splits_three_parts(self, mock_tt, mock_send, mock_conn):
        """Сентинель может встречаться несколько раз — каждая часть отправляется отдельно."""
        conn = _create_db_and_populate([
            {'platform': 'telegram', 'platform_id': '111', 'teachers': ['Иванов'], 'groups': []},
        ])
        mock_conn.return_value = conn
        mock_tt.return_value = f'А{MESSAGE_SPLIT_SENTINEL}Б{MESSAGE_SPLIT_SENTINEL}В'
        send_notifications_telegram(
            group_list_current_week=[], group_list_next_week=[],
            teacher_list_current_week=['Иванов'], teacher_list_next_week=[])
        # 1 msg_text + 3 части = 4 вызова
        assert mock_send.call_count == 4
        calls = mock_send.call_args_list
        assert calls[1][1]['message'] == 'А'
        assert calls[2][1]['message'] == 'Б'
        assert calls[3][1]['message'] == 'В'

    @patch('sql_db.connection_to_sql')
    @patch('sql_db.write_msg_telegram', new_callable=AsyncMock)
    @patch('sql_db.timetable')
    def test_telegram_ignores_empty_parts_from_split(self, mock_tt, mock_send, mock_conn):
        """Пустые части после split не отправляются."""
        conn = _create_db_and_populate([
            {'platform': 'telegram', 'platform_id': '111', 'teachers': ['Иванов'], 'groups': []},
        ])
        mock_conn.return_value = conn
        # Сентинель в конце порождает пустую часть — она должна игнорироваться
        mock_tt.return_value = f'расписание{MESSAGE_SPLIT_SENTINEL}'
        send_notifications_telegram(
            group_list_current_week=[], group_list_next_week=[],
            teacher_list_current_week=['Иванов'], teacher_list_next_week=[])
        # 1 msg_text + 1 непустая часть = 2 вызова (пустая часть отброшена)
        assert mock_send.call_count == 2

    @patch('sql_db.connection_to_sql')
    @patch('sql_db.write_msg_telegram', new_callable=AsyncMock)
    @patch('sql_db.timetable', return_value='расписание')
    def test_telegram_multiple_users(self, mock_tt, mock_send, mock_conn):
        conn = _create_db_and_populate([
            {'platform': 'telegram', 'platform_id': '111', 'teachers': ['Иванов'], 'groups': []},
            {'platform': 'telegram', 'platform_id': '222', 'teachers': ['Иванов'], 'groups': ['307']},
        ])
        mock_conn.return_value = conn
        send_notifications_telegram(
            group_list_current_week=['307'], group_list_next_week=[],
            teacher_list_current_week=['Иванов'], teacher_list_next_week=[])
        # user1: 1 teacher match → 2 calls
        # user2: 1 teacher + 1 group → 4 calls
        assert mock_send.call_count == 6


# ─── Кросс-платформенные тесты ───

class TestCrossPlatformIsolation:
    """Проверяем, что уведомления для одной платформы не затрагивают другие."""

    @patch('sql_db.connection_to_sql')
    @patch('sql_db.sendMail')
    @patch('sql_db.timetable', return_value='расписание')
    def test_email_ignores_other_platforms(self, mock_tt, mock_mail, mock_conn):
        conn = _create_db_and_populate([
            {'platform': 'email', 'platform_id': 'a@test.com', 'teachers': ['Иванов'], 'groups': []},
            {'platform': 'telegram', 'platform_id': '111', 'teachers': ['Иванов'], 'groups': []},
            {'platform': 'vk_user', 'platform_id': '222', 'teachers': ['Иванов'], 'groups': []},
            {'platform': 'vk_chat', 'platform_id': '333', 'teachers': ['Иванов'], 'groups': []},
            {'platform': 'discord', 'platform_id': '444', 'teachers': ['Иванов'], 'groups': []},
        ])
        mock_conn.return_value = conn
        send_notifications_email(
            group_list_current_week=[], group_list_next_week=[],
            teacher_list_current_week=['Иванов'], teacher_list_next_week=[])
        assert mock_mail.call_count == 1
        assert mock_mail.call_args[1]['to_email'] == 'a@test.com'

    @patch('sql_db.connection_to_sql')
    @patch('sql_db.write_msg_telegram', new_callable=AsyncMock)
    @patch('sql_db.timetable', return_value='расписание')
    def test_telegram_ignores_other_platforms(self, mock_tt, mock_send, mock_conn):
        conn = _create_db_and_populate([
            {'platform': 'email', 'platform_id': 'a@test.com', 'teachers': ['Иванов'], 'groups': []},
            {'platform': 'telegram', 'platform_id': '111', 'teachers': ['Иванов'], 'groups': []},
            {'platform': 'vk_user', 'platform_id': '222', 'teachers': ['Иванов'], 'groups': []},
        ])
        mock_conn.return_value = conn
        send_notifications_telegram(
            group_list_current_week=[], group_list_next_week=[],
            teacher_list_current_week=['Иванов'], teacher_list_next_week=[])
        assert mock_send.call_count == 2  # только для telegram-пользователя


# ─── Тесты junction-таблиц в контексте уведомлений ───

class TestJunctionTableNotifications:
    """Проверяем корректную работу junction-таблиц при рассылке."""

    @patch('sql_db.connection_to_sql')
    @patch('sql_db.sendMail')
    @patch('sql_db.timetable', return_value='расписание')
    @patch('sql_db.format_timetable_html', return_value='<html></html>')
    def test_user_with_multiple_teachers_and_groups(self, mock_html, mock_tt, mock_mail, mock_conn):
        conn = _create_db_and_populate([
            {'platform': 'email', 'platform_id': 'multi@test.com',
             'teachers': ['Иванов', 'Петров', 'Сидоров'],
             'groups': ['307', '308']},
        ])
        mock_conn.return_value = conn
        send_notifications_email(
            group_list_current_week=['307'], group_list_next_week=['308'],
            teacher_list_current_week=['Иванов', 'Петров'], teacher_list_next_week=['Сидоров'])
        assert mock_mail.call_count == 1  # один email со всеми изменениями

    @patch('sql_db.connection_to_sql')
    @patch('sql_db.sendMail')
    @patch('sql_db.timetable', return_value='расписание')
    def test_user_with_no_teachers_or_groups(self, mock_tt, mock_mail, mock_conn):
        conn = _create_db_and_populate([
            {'platform': 'email', 'platform_id': 'empty@test.com', 'teachers': [], 'groups': []},
        ])
        mock_conn.return_value = conn
        send_notifications_email(
            group_list_current_week=['307'], group_list_next_week=[],
            teacher_list_current_week=['Иванов'], teacher_list_next_week=[])
        mock_mail.assert_not_called()

    def test_collect_with_empty_teachers_and_groups(self):
        row = _make_user_row()
        with patch('sql_db.timetable', return_value='расписание'):
            result = _collect_notification_messages_normalized(
                row, [], [], ['307'], [], ['Иванов'], [])
        assert result == []


# ─── Интеграционные тесты ───

class TestNotificationIntegration:
    """Сквозные тесты: мокируется только реальный API-запрос к платформе.

    Вся промежуточная логика (выборка подписчиков из БД, формирование заголовка
    «Изменения в расписании на … неделю для …», добавление MESSAGE_PREFIX,
    разбивка расписания по MESSAGE_SPLIT_SENTINEL) работает по-настоящему —
    без моков. Это гарантирует, что нужное содержимое действительно доходит
    до платформенного API.
    """

    # ── Telegram ──────────────────────────────────────────────────────────────
    # aiogram.Bot не экспортируется на уровне пакета до реального импорта (3.x
    # lazy load), поэтому патчим sql_db.write_msg_telegram. Интеграционная
    # ценность сохраняется: _send_notifications_telegram_async,
    # _collect_notification_messages_normalized и логика split работают вживую —
    # мы проверяем конкретный текст, который они передают в write_msg_telegram.

    @patch('sql_db.write_msg_telegram', new_callable=AsyncMock)
    @patch('sql_db.connection_to_sql')
    @patch('sql_db.timetable', return_value='Пн: Матан 8:00\nВт: Физика 10:00')
    def test_telegram_header_and_timetable_reach_send_function(self, mock_tt, mock_conn, mock_send):
        """Заголовок содержит имя преподавателя + тип недели; расписание —
        текст от timetable(). Оба вызова идут правильному tg_id."""
        conn = _create_db_and_populate([
            {'platform': 'telegram', 'platform_id': '42', 'teachers': ['Иванов'], 'groups': []},
        ])
        mock_conn.return_value = conn

        send_notifications_telegram(
            group_list_current_week=[], group_list_next_week=[],
            teacher_list_current_week=['Иванов'], teacher_list_next_week=[])

        calls = mock_send.call_args_list
        assert len(calls) == 2
        msgs = [c[1]['message'] for c in calls]
        tg_ids = [c[1]['tg_id'] for c in calls]
        # Все сообщения идут правильному пользователю
        assert all(tid == '42' for tid in tg_ids)
        # Заголовок содержит имя и тип недели
        assert any('Иванов' in m and 'текущую' in m and 'преподавателя' in m for m in msgs)
        # Расписание содержит содержимое от timetable()
        assert any('Пн: Матан 8:00' in m for m in msgs)

    @patch('sql_db.write_msg_telegram', new_callable=AsyncMock)
    @patch('sql_db.connection_to_sql')
    @patch('sql_db.timetable')
    def test_telegram_split_sentinel_produces_separate_write_calls(self, mock_tt, mock_conn, mock_send):
        """Сентинель в расписании → каждая часть передаётся в write_msg_telegram
        отдельным вызовом. Сам сентинель ни в одно сообщение не попадает."""
        conn = _create_db_and_populate([
            {'platform': 'telegram', 'platform_id': '42', 'teachers': ['Иванов'], 'groups': []},
        ])
        mock_conn.return_value = conn
        mock_tt.return_value = f'Пн: Матан{MESSAGE_SPLIT_SENTINEL}Вт: Физика'

        send_notifications_telegram(
            group_list_current_week=[], group_list_next_week=[],
            teacher_list_current_week=['Иванов'], teacher_list_next_week=[])

        # 1 заголовок + 2 части расписания
        assert mock_send.call_count == 3
        msgs = [c[1]['message'] for c in mock_send.call_args_list]
        assert not any(MESSAGE_SPLIT_SENTINEL in m for m in msgs)
        assert any('Пн: Матан' in m for m in msgs)
        assert any('Вт: Физика' in m for m in msgs)

    @patch('sql_db.write_msg_telegram', new_callable=AsyncMock)
    @patch('sql_db.connection_to_sql')
    @patch('sql_db.timetable', return_value='расписание')
    def test_telegram_unsubscribed_user_gets_no_messages(self, mock_tt, mock_conn, mock_send):
        """Пользователь с подпиской на другого преподавателя не получает ничего."""
        conn = _create_db_and_populate([
            {'platform': 'telegram', 'platform_id': '42', 'teachers': ['Петров'], 'groups': []},
        ])
        mock_conn.return_value = conn

        send_notifications_telegram(
            group_list_current_week=[], group_list_next_week=[],
            teacher_list_current_week=['Иванов'], teacher_list_next_week=[])

        mock_send.assert_not_called()

    # ── VK ────────────────────────────────────────────────────────────────────

    @patch('sql_db.API')
    @patch('sql_db.connection_to_sql')
    @patch('sql_db.timetable', return_value='Пн: Матан 8:00')
    def test_vk_user_correct_peer_id_and_prefixed_content(self, mock_tt, mock_conn, MockAPI):
        """VK user: api.messages.send получает правильный peer_id и текст с MESSAGE_PREFIX."""
        conn = _create_db_and_populate([
            {'platform': 'vk_user', 'platform_id': '999', 'teachers': ['Петров'], 'groups': []},
        ])
        mock_conn.return_value = conn
        mock_api = MagicMock()
        mock_api.messages.send = AsyncMock(return_value=1)
        MockAPI.return_value = mock_api

        result = send_notifications_vk_user(
            group_list_current_week=[], group_list_next_week=[],
            teacher_list_current_week=['Петров'], teacher_list_next_week=[])

        assert result is True
        calls = mock_api.messages.send.call_args_list
        assert len(calls) == 2
        # Правильный получатель
        assert all(c.kwargs['peer_id'] == 999 for c in calls)
        sent = [c.kwargs['message'] for c in calls]
        # Префикс добавлен
        assert all(m.startswith(MESSAGE_PREFIX) for m in sent)
        # Заголовок и расписание присутствуют
        assert any('Петров' in m for m in sent)
        assert any('Пн: Матан' in m for m in sent)

    @patch('sql_db.API')
    @patch('sql_db.connection_to_sql')
    @patch('sql_db.timetable', return_value='расписание')
    def test_vk_chat_peer_id_gets_2e9_offset(self, mock_tt, mock_conn, MockAPI):
        """VK chat с обычным ID: peer_id должен быть смещён на 2 000 000 000."""
        conn = _create_db_and_populate([
            {'platform': 'vk_chat', 'platform_id': '100', 'groups': ['307'], 'teachers': []},
        ])
        mock_conn.return_value = conn
        mock_api = MagicMock()
        mock_api.messages.send = AsyncMock(return_value=1)
        MockAPI.return_value = mock_api

        send_notifications_vk_chat(
            group_list_current_week=['307'], group_list_next_week=[],
            teacher_list_current_week=[], teacher_list_next_week=[])

        calls = mock_api.messages.send.call_args_list
        assert len(calls) == 2
        assert all(c.kwargs['peer_id'] == 2_000_000_100 for c in calls)

    @patch('sql_db.API')
    @patch('sql_db.connection_to_sql')
    @patch('sql_db.timetable', return_value='расписание')
    def test_vk_both_async_sends_to_chat_and_user_in_one_loop(self, mock_tt, mock_conn, MockAPI):
        """send_notifications_vk_both_async: уведомления уходят и в чат, и пользователю
        за один asyncio.run() — без промежуточного закрытия event loop.

        _send_notifications_vk_async вызывается дважды (chat, user), каждый раз
        открывая и закрывая соединение через _db_connection. Поэтому mock_conn
        получает side_effect с двумя отдельными in-memory DB — иначе второй вызов
        получит уже закрытое соединение."""
        users_data = [
            {'platform': 'vk_chat', 'platform_id': '1', 'groups': ['307'], 'teachers': []},
            {'platform': 'vk_user', 'platform_id': '2', 'groups': ['307'], 'teachers': []},
        ]
        mock_conn.side_effect = [
            _create_db_and_populate(users_data),
            _create_db_and_populate(users_data),
        ]
        mock_api = MagicMock()
        mock_api.messages.send = AsyncMock(return_value=1)
        MockAPI.return_value = mock_api

        asyncio.run(send_notifications_vk_both_async(
            group_list_current_week=['307'], group_list_next_week=[],
            teacher_list_current_week=[], teacher_list_next_week=[]))

        # Чат: 2 сообщения (заголовок + расписание), пользователь: 2
        assert mock_api.messages.send.call_count == 4
        peer_ids = {c.kwargs['peer_id'] for c in mock_api.messages.send.call_args_list}
        # Чат: peer_id = 2_000_000_001 (смещение), пользователь: 2
        assert 2_000_000_001 in peer_ids
        assert 2 in peer_ids

    # ── Email ─────────────────────────────────────────────────────────────────

    @patch('sql_db.sendMail')
    @patch('sql_db.format_timetable_html', return_value='<b>Пн: Матан</b>')
    @patch('sql_db.connection_to_sql')
    @patch('sql_db.timetable', return_value='Пн: Матан')
    def test_email_html_timetable_reaches_sendmail(self, mock_tt, mock_conn, mock_html, mock_mail):
        """Email: HTML-расписание от format_timetable_html попадает в sendMail(html=…),
        тема — «Изменения в расписании», адресат — подписанный пользователь."""
        conn = _create_db_and_populate([
            {'platform': 'email', 'platform_id': 'user@example.com',
             'teachers': ['Иванов'], 'groups': []},
        ])
        mock_conn.return_value = conn

        send_notifications_email(
            group_list_current_week=[], group_list_next_week=[],
            teacher_list_current_week=['Иванов'], teacher_list_next_week=[])

        mock_mail.assert_called_once()
        kw = mock_mail.call_args[1]
        assert kw['to_email'] == 'user@example.com'
        assert kw['subject'] == 'Изменения в расписании'
        assert '<b>Пн: Матан</b>' in kw['html']
