class StateManager:
    """Manages chat session state transitions."""
    
    # Define valid states
    STATE_MAIN_MENU = "MAIN_MENU"
    STATE_MODE_BANTUAN = "MODE_BANTUAN"
    STATE_AWAITING_REPORT = "AWAITING_REPORT"
    STATE_AWAITING_WAKTU = "AWAITING_WAKTU"
    STATE_AWAITING_LOKASI = "AWAITING_LOKASI"
    STATE_AWAITING_KORBAN = "AWAITING_KORBAN"
    STATE_CONFIRMING = "CONFIRMING"
    STATE_COMPLETED = "COMPLETED"

    @classmethod
    def get_next_state(cls, current_state: str, missing_fields: list) -> str:
        """Determines the next state based on missing fields."""
        if "waktu" in missing_fields:
            return cls.STATE_AWAITING_WAKTU
        elif "lokasi_teks" in missing_fields:
            return cls.STATE_AWAITING_LOKASI
        elif "data_korban" in missing_fields or "korban" in missing_fields:
            return cls.STATE_AWAITING_KORBAN
        
        return cls.STATE_CONFIRMING
