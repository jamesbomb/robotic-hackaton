from __future__ import annotations

from pathlib import Path


def transcribe_audio_file(audio_path: Path, model_name: str = "tiny") -> str:
    """Transcribe an audio file with optional OpenAI Whisper.

    Whisper is intentionally optional because the P0 mock/chat path must work
    without heavyweight audio dependencies.
    """

    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    try:
        import whisper  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError(
            "Whisper voice input requires the optional package `openai-whisper`. "
            "Install it in the project venv only when voice input is needed: "
            "`.venv/bin/pip install openai-whisper`"
        ) from exc

    model = whisper.load_model(model_name)
    result = model.transcribe(str(audio_path))
    text = str(result.get("text", "")).strip()
    if not text:
        raise RuntimeError(f"Whisper returned an empty transcript for {audio_path}")
    return text
