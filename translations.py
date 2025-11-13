# translations.py

from dataclasses import dataclass
from typing import Any, Dict
from languages import MessagesType


@dataclass
class TranslationService:
    translations: MessagesType
    default_lang: str = "en"

    def __post_init__(self) -> None:
        if self.default_lang not in self.translations:
            raise ValueError(f"Default language '{self.default_lang}' not in translations")

    def _get_lang(self, lang: str | None) -> str:
        if lang and lang in self.translations:
            return lang
        return self.default_lang

    def t(self, key: str, lang: str | None = None, **kwargs: Any) -> str:
        """
        Restituisce la stringa tradotta per `key` nella lingua `lang`.
        - key può essere del tipo 'greeting.hello'
        - kwargs sono i placeholder da formattare nella stringa
        """
        lang_code = self._get_lang(lang)
        lang_dict = self.translations.get(lang_code, {})
        default_dict = self.translations[self.default_lang]

        # supporto chiavi annidate: "section.subkey"
        sections = key.split(".")
        value = self._get_nested(lang_dict, sections)
        if value is None:
            value = self._get_nested(default_dict, sections)
        if value is None:
            # ultima difesa: torna la key stessa
            value = key

        if kwargs:
            try:
                value = value.format(**kwargs)
            except Exception:
                # se il format fallisce, restituisci comunque la stringa grezza
                pass

        return value

    @staticmethod
    def _get_nested(d: Dict[str, Any], path: list[str]) -> Any | None:
        current: Any = d
        for part in path:
            if not isinstance(current, dict) or part not in current:
                return None
            current = current[part]
        return current
