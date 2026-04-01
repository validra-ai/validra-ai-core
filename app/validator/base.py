from abc import ABC, abstractmethod
from typing import Optional


class BaseValidator(ABC):

    @abstractmethod
    def validate(
        self,
        test: dict,
        response: dict,
        meta: Optional[dict] = None,
        provider=None,
        provider_config=None,
    ) -> dict:
        raise NotImplementedError
