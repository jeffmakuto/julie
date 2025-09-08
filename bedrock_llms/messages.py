from typing import List, Dict
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage

def to_lc_messages(messages: List[Dict[str, str]]) -> List[BaseMessage]:
    lc_messages: List[BaseMessage] = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role == "system":
            lc_messages.append(SystemMessage(content=content))
        elif role == "assistant":
            lc_messages.append(AIMessage(content=content))
        else:
            lc_messages.append(HumanMessage(content=content))
    return lc_messages
