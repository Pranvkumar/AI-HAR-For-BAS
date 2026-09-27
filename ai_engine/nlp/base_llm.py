"""
Base interface for LLM/NLP guidance modules.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class BaseLLM(ABC):
    """
    Abstract base class for LLM guidance systems.
    All LLM calls MUST receive only deterministic context packets from FSM.
    """

    @abstractmethod
    async def generate_guidance(self, context: Dict[str, Any]) -> str:
        """
        Generate natural language guidance grounded in FSM context.

        Args:
            context: Deterministic context packet from FSM/Validator with keys:
                - current_step (int)
                - total_steps (int)
                - expected_activity (str)
                - detected_activity (str)
                - fsm_status (str)
                - progress (float)
                - is_complete (bool)

        Returns:
            Natural language guidance string.
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if the LLM service is available and configured.
        """
        pass