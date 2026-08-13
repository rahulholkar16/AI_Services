from langchain_core.messages.utils import count_tokens_approximately
from langchain_core.messages import BaseMessage

def count_tokens(messages: list[BaseMessage], tools: list = None) -> int:
    
    return count_tokens_approximately(
        messages,
        chars_per_token=4.0,           
        extra_tokens_per_message=3.0,  
        count_name=True,               
        use_usage_metadata_scaling=True,  
        tools=tools,                   
    )