import re
from pathlib import Path
from typing import Optional

from faster_whisper import WhisperModel


def _cleanup_transcript(text: str) -> str:
    t = (text or "").strip()

    # Убираем повторяющиеся пробелы
    t = re.sub(r"\s+", " ", t)

    # Убираем часть мусорных слов-паразитов, если они отдельными токенами
    trash_patterns = [
        r"\b(ээ+|эм+|мм+|ну+)\b",
    ]
    for pattern in trash_patterns:
        t = re.sub(pattern, "", t, flags=re.IGNORECASE)

    t = re.sub(r"\s+", " ", t).strip(" ,.-")
    return t


class VoiceTranscriber:
    """
    Lazy-loaded transcriber:
    - модель не инициализируется на старте бота
    - первая инициализация произойдёт только при первом голосовом
    """

    def __init__(
        self,
        model_size: str = "small",
        device: str = "cpu",
        compute_type: str = "int8",
    ):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.model: Optional[WhisperModel] = None

    def _get_model(self) -> WhisperModel:
        if self.model is None:
            self.model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
            )
        return self.model

    async def transcribe_file(self, path: str) -> str:
        model = self._get_model()

        # Первая попытка — русская транскрибация
        segments, _ = model.transcribe(
            path,
            language="ru",
            beam_size=5,
            best_of=5,
            vad_filter=True,
        )
        parts = [seg.text.strip() for seg in segments if seg.text and seg.text.strip()]
        text = _cleanup_transcript(" ".join(parts))

        # Если текст подозрительно короткий, делаем вторую попытку без фиксированного языка
        if len(text) < 12:
            segments2, _ = model.transcribe(
                path,
                beam_size=7,
                best_of=7,
                vad_filter=True,
            )
            parts2 = [seg.text.strip() for seg in segments2 if seg.text and seg.text.strip()]
            text2 = _cleanup_transcript(" ".join(parts2))
            if len(text2) > len(text):
                text = text2

        return text

    async def download_and_transcribe(self, bot, voice) -> str:
        tg_file = await bot.get_file(voice.file_id)
        tmp_dir = Path("tmp")
        tmp_dir.mkdir(exist_ok=True)

        local_path = tmp_dir / f"{voice.file_unique_id}.ogg"

        await bot.download_file(
            tg_file.file_path,
            destination=local_path,
        )

        text = await self.transcribe_file(str(local_path))

        try:
            local_path.unlink(missing_ok=True)
        except Exception:
            pass

        return text
