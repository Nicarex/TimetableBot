from constants import MESSAGE_SPLIT_SENTINEL, MESSAGE_PREFIX


def split_response(text: str) -> list:
    """Разбивает ответ по разделителю и возвращает непустые части с префиксом."""
    parts = str(text).split(MESSAGE_SPLIT_SENTINEL)
    return [MESSAGE_PREFIX + part for part in parts if part]
