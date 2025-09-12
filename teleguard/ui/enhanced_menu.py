"""Enhanced menu system with breadcrumbs and navigation"""

from typing import Any, Dict, List

from telethon import Button


class MenuBuilder:
    def __init__(self):
        self.breadcrumbs = []

    def build_menu(
        self, title: str, options: List[Dict[str, Any]], show_back: bool = True
    ) -> tuple[str, List[List[Button]]]:
        """Build menu with breadcrumbs"""
        # Build breadcrumb navigation
        breadcrumb = " > ".join(self.breadcrumbs + [title])
        message = f"📍 {breadcrumb}\n\n{title}"

        # Build button rows
        buttons = []
        for i in range(0, len(options), 2):
            row = []
            for j in range(2):
                if i + j < len(options):
                    opt = options[i + j]
                    row.append(Button.inline(opt["text"], opt["callback"]))
            buttons.append(row)

        # Add navigation buttons
        nav_row = []
        if show_back and self.breadcrumbs:
            nav_row.append(Button.inline("⬅️ Back", "menu_back"))
        nav_row.append(Button.inline("🏠 Main Menu", "main_menu"))

        if nav_row:
            buttons.append(nav_row)

        return message, buttons

    def push_breadcrumb(self, name: str):
        """Add breadcrumb level"""
        self.breadcrumbs.append(name)

    def pop_breadcrumb(self):
        """Remove last breadcrumb level"""
        if self.breadcrumbs:
            self.breadcrumbs.pop()

    def clear_breadcrumbs(self):
        """Clear all breadcrumbs"""
        self.breadcrumbs.clear()
