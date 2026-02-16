"""
Абстракция платформы для устранения дублирования в sql_db.py.
Единая таблица users с колонкой platform, поэтому контекст хранит
только имя платформы и ID пользователя.
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class PlatformContext:
    platform: str    # 'email', 'vk_user', 'vk_chat', 'telegram', 'discord'
    user_id: str     # значение platform_id пользователя


def resolve_platform(
    email: str = None,
    vk_id_chat: str = None,
    vk_id_user: str = None,
    telegram: str = None,
    discord: str = None,
) -> Optional[PlatformContext]:
    """Возвращает PlatformContext для первого не-None аргумента."""
    if email is not None:
        return PlatformContext('email', email)
    if vk_id_chat is not None:
        return PlatformContext('vk_chat', vk_id_chat)
    if vk_id_user is not None:
        return PlatformContext('vk_user', vk_id_user)
    if telegram is not None:
        return PlatformContext('telegram', telegram)
    if discord is not None:
        return PlatformContext('discord', discord)
    return None
