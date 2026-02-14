"""
Абстракция платформы для устранения дублирования в sql_db.py.
Каждая платформа (email, vk_user, vk_chat, telegram, discord) описывается
через PlatformContext с именем таблицы, столбцом ID и значением ID.
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class PlatformContext:
    name: str        # 'email', 'vk_user', 'vk_chat', 'telegram', 'discord'
    table: str       # имя таблицы в user_settings.db
    id_column: str   # столбец ID (email, vk_id, telegram_id, discord_id)
    user_id: str     # значение ID пользователя


def resolve_platform(
    email: str = None,
    vk_id_chat: str = None,
    vk_id_user: str = None,
    telegram: str = None,
    discord: str = None,
) -> Optional[PlatformContext]:
    """Возвращает PlatformContext для первого не-None аргумента."""
    if email is not None:
        return PlatformContext('email', 'email', 'email', email)
    if vk_id_chat is not None:
        return PlatformContext('vk_chat', 'vk_chat', 'vk_id', vk_id_chat)
    if vk_id_user is not None:
        return PlatformContext('vk_user', 'vk_user', 'vk_id', vk_id_user)
    if telegram is not None:
        return PlatformContext('telegram', 'telegram', 'telegram_id', telegram)
    if discord is not None:
        return PlatformContext('discord', 'discord', 'discord_id', discord)
    return None
