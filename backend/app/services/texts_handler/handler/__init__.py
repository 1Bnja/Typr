from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..context import TextContext


class TextHandler:
    def __init__(self) -> None:
        self.next: TextHandler | None = None

    def set_next(self, handler: TextHandler) -> TextHandler:
        self.next = handler
        return handler

    def handle(self, context: TextContext) -> None:
        self.forward(context)

    def forward(self, context: TextContext) -> None:
        if self.next is not None:
            self.next.handle(context)
