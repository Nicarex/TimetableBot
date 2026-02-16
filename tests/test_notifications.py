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
)


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
