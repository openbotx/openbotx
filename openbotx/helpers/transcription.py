import io
import logging

logger = logging.getLogger(__name__)

_model = None


def _get_model():
    global _model
    if _model is None:
        from faster_whisper import WhisperModel

        _model = WhisperModel("base", device="cpu", compute_type="int8")
        logger.info("whisper model loaded (base, cpu, int8)")
    return _model


def transcribe(audio_data: bytes) -> str:
    model = _get_model()
    buf = io.BytesIO(audio_data)
    segments, info = model.transcribe(buf, beam_size=5)
    text = " ".join(seg.text for seg in segments).strip()
    if text:
        logger.info(
            "transcribed audio (%s, prob=%.2f): %s",
            info.language,
            info.language_probability,
            text[:100],
        )
    return text
