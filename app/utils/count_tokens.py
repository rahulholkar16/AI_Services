from langchain_core.messages.utils import count_tokens_approximately
from langchain_core.messages import BaseMessage

def count_tokens(messages: list[BaseMessage], tools: list = None) -> int:
    
    return count_tokens_approximately(
        messages,
        chars_per_token=4.0,           # default is fine for English/code mix
        extra_tokens_per_message=3.0,  # role + formatting overhead per message
        count_name=True,               # counts sender name if present
        use_usage_metadata_scaling=True,  # <-- turn this ON
        tools=tools,                   # pass your bound tool schemas here
    )