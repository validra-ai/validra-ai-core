from abc import ABC, abstractmethod
from typing import Optional


class BasePlugin(ABC):
    name: str = "base"

    @abstractmethod
    def generate(
        self,
        example: dict,
        previous_cases: list,
        max_cases: int,
        meta: Optional[dict],
        provider,
        provider_config,
    ) -> list:
        raise NotImplementedError
