from sqlalchemy.ext.asyncio import AsyncSession
from app.models.chat_session import ChatSession

class BaseFieldProcessor:
    """Abstract base class for processing, validating, and questioning specific incident fields."""
    
    async def validate_and_extract(
        self, message: str, session: ChatSession, extracted_data: dict, db: AsyncSession
    ) -> tuple[bool, dict | str]:
        """
        Validates user input and extracts the relevant field.
        
        Returns:
            (True, updated_extracted_data_dict) if input is valid.
            (False, error_message_text) if input is invalid.
        """
        raise NotImplementedError()

    def get_question(self, session: ChatSession, extracted_data: dict) -> tuple[str, list]:
        """
        Returns the question text and buttons for this field.
        
        Returns:
            (question_text, buttons_list)
        """
        raise NotImplementedError()
