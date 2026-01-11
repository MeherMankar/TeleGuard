"""Internationalization support"""

import logging

logger = logging.getLogger(__name__)


TRANSLATIONS = {
    "en": {
        "welcome": "Welcome to TeleGuard!",
        "account_added": "Account added successfully",
        "account_removed": "Account removed",
        "error": "An error occurred",
        "back": "Back",
        "cancel": "Cancel",
        "confirm": "Confirm",
        "menu_accounts": "Account Settings",
        "menu_otp": "OTP Manager",
        "menu_messaging": "Messaging",
        "menu_channels": "Channels",
        "menu_cleanup": "Cleanup",
    },
    "es": {
        "welcome": "¡Bienvenido a TeleGuard!",
        "account_added": "Cuenta agregada exitosamente",
        "account_removed": "Cuenta eliminada",
        "error": "Ocurrió un error",
        "back": "Atrás",
        "cancel": "Cancelar",
        "confirm": "Confirmar",
        "menu_accounts": "Configuración de Cuenta",
        "menu_otp": "Gestor OTP",
        "menu_messaging": "Mensajería",
        "menu_channels": "Canales",
        "menu_cleanup": "Limpieza",
    },
    "ru": {
        "welcome": "Добро пожаловать в TeleGuard!",
        "account_added": "Аккаунт успешно добавлен",
        "account_removed": "Аккаунт удален",
        "error": "Произошла ошибка",
        "back": "Назад",
        "cancel": "Отмена",
        "confirm": "Подтвердить",
        "menu_accounts": "Настройки аккаунта",
        "menu_otp": "Менеджер OTP",
        "menu_messaging": "Сообщения",
        "menu_channels": "Каналы",
        "menu_cleanup": "Очистка",
    },
}


class I18n:
    def __init__(self):
        self.user_languages = {}
        self.default_language = "en"

    def set_user_language(self, user_id: int, language: str):
        """Set user's preferred language"""
        if language in TRANSLATIONS:
            self.user_languages[user_id] = language
            logger.info(f"Set language {language} for user {user_id}")
        else:
            logger.warning(f"Language {language} not supported")

    def get_user_language(self, user_id: int) -> str:
        """Get user's language"""
        return self.user_languages.get(user_id, self.default_language)

    def translate(self, user_id: int, key: str, **kwargs) -> str:
        """Translate a key for user"""
        lang = self.get_user_language(user_id)
        translations = TRANSLATIONS.get(lang, TRANSLATIONS[self.default_language])
        text = translations.get(key, key)

        if kwargs:
            try:
                text = text.format(**kwargs)
            except Exception as e:
                logger.error(f"Translation format error: {e}")

        return text

    def get_available_languages(self) -> list:
        """Get list of available languages"""
        return list(TRANSLATIONS.keys())


i18n = I18n()
