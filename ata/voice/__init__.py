"""Voice channel: STT/TTS abstraction, registry, and built-in providers.

Importing this package registers the built-in reference provider (OpenAI). Third
parties register their own via ``register_stt`` / ``register_tts``; the long tail
is also reachable through the optional Pipecat bridge.
"""

# Register the built-in reference providers (OpenAI STT + TTS).
from ata.voice import providers as _providers  # noqa: F401
from ata.voice.client import (
    STTClient,
    TranscriptionResult,
    TTSClient,
    VoiceIO,
    VoiceIODefaults,
)
from ata.voice.registry import (
    create_voice_io,
    register_stt,
    register_tts,
    stt_registry,
    tts_registry,
)

__all__ = [
    "STTClient",
    "TTSClient",
    "TranscriptionResult",
    "VoiceIO",
    "VoiceIODefaults",
    "create_voice_io",
    "register_stt",
    "register_tts",
    "stt_registry",
    "tts_registry",
]
