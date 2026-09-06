__all__ = [
    "mask_secret",
]


def mask_secret(
    *,
    value: str,
) -> str:
    """掩码敏感值, 只保留前 4 位.

    Args:
        value: 原始值.

    Returns:
        掩码后的展示值, 空值原样返回.

    """
    if not value:
        return ""
    return f"{value[:4]}***"
