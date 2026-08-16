from faster_whisper import WhisperModel


class WhisperService:

    def __init__(self):
        self._model = None

    @property
    def model(self) -> WhisperModel:
        if self._model is None:
            self._model = WhisperModel(
                "small",
                device="cpu",
                compute_type="int8",
            )
        return self._model

    def transcribe(self, audio_path: str) -> dict:
        segments_iter, info = self.model.transcribe(
            audio_path,
            beam_size=5,
        )

        segments = []
        transcript_parts = []

        for segment in segments_iter:
            text = segment.text.strip()
            segments.append(
                {
                    "start": round(segment.start, 2),
                    "end": round(segment.end, 2),
                    "text": text,
                }
            )
            if text:
                transcript_parts.append(text)

        return {
            "language": info.language,
            "language_probability": round(info.language_probability, 4),
            "transcript": " ".join(transcript_parts),
            "segments": segments,
        }


whisper_service = WhisperService()
