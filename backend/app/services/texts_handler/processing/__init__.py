from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..context import TextContext


class TextProcessingStep:
    def __init__(self) -> None:
        self.next: TextProcessingStep | None = None

    def set_next(self, handler: TextProcessingStep) -> TextProcessingStep:
        self.next = handler
        return handler

    def handle(self, context: TextContext) -> None:
        self.forward(context)

    def forward(self, context: TextContext) -> None:
        if self.next is not None:
            self.next.handle(context)
