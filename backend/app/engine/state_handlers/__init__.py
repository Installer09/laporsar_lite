from app.engine.state_handlers.base import BaseStateHandler
from app.engine.state_handlers.awaiting_report import AwaitingReportStateHandler
from app.engine.state_handlers.awaiting_field import AwaitingFieldStateHandler
from app.engine.state_handlers.confirming import ConfirmingStateHandler
from app.engine.state_handlers.completed import CompletedStateHandler

def get_state_handler(state_name: str) -> BaseStateHandler:
    """Registry function to resolve a dialogue state to its corresponding StateHandler."""
    from app.engine.chatbot_engine import STATE_FIELD_MAP
    
    if state_name == "AWAITING_REPORT":
        return AwaitingReportStateHandler()
    elif state_name in STATE_FIELD_MAP:
        return AwaitingFieldStateHandler()
    elif state_name == "CONFIRMING":
        return ConfirmingStateHandler()
    elif state_name == "COMPLETED":
        return CompletedStateHandler()
    else:
        raise ValueError(f"Unknown state '{state_name}'")
