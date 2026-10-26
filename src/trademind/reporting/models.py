"""The interface to a text model. Providers only send a prompt and return the reply."""

from typing import Protocol


class ChatModel(Protocol):
    name: str

    def complete(self, system: str, user: str) -> str:
        """Send a system prompt and a user message. Return the model's reply.

        Raises ExplainerError if the service fails or is not set up.
        """
        ...
