from langchain_core.messages import SystemMessage, RemoveMessage

MEMORY_PREFIX = "[Long-term memory]"


def find_old_memory_messages(messages: list) -> list[RemoveMessage]:
    """Finds all previously-injected long-term-memory SystemMessages so they
    can be replaced with a fresh one, instead of accumulating forever."""
    old_ids = [
        m.id for m in messages
        if isinstance(m, SystemMessage) and str(m.content).startswith(MEMORY_PREFIX)
    ]
    return [RemoveMessage(id=mid) for mid in old_ids if mid is not None]
