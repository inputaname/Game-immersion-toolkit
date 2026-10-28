from __future__ import annotations

from datetime import datetime
import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class CaptureRegion(BaseModel):
    left: float = Field(default=0.08, ge=0, le=1)
    top: float = Field(default=0.67, ge=0, le=1)
    width: float = Field(default=0.84, gt=0, le=1)
    height: float = Field(default=0.25, gt=0, le=1)

    @model_validator(mode="after")
    def validate_bounds(self) -> "CaptureRegion":
        if self.left + self.width > 1.0001:
            raise ValueError("Capture region extends beyond the right edge")
        if self.top + self.height > 1.0001:
            raise ValueError("Capture region extends beyond the bottom edge")
        return self


GameId = Literal["zzz", "pragmata", "hito", "cyberpunk", "wuwa", "witcher3", "nte", "beyond", "heavyrain", "honkai3", "starrail", "genshin", "endfield", "riseofthetombraider", "shadowofthetombraider", "spyro", "mgsvtpp", "mgsvgz", "deathstranding", "plaguetaleinnocence", "detroit", "portal", "portal2", "halflife", "halflife2", "persona5royal", "deusexhrdc"]


def is_comic_text_id(text_id: str) -> bool:
    return re.fullmatch(r"Comic_[0-9a-fA-F]{32}(?::[MF])?", text_id) is not None


class AppSettings(BaseModel):
    zzz_proxy_voice: Literal['unconfigured', 'female', 'male'] = 'unconfigured'
    preferred_game: Literal["auto", "zzz", "pragmata", "cyberpunk", "wuwa", "witcher3", "nte", "beyond", "heavyrain", "starrail", "genshin", "endfield", "riseofthetombraider", "shadowofthetombraider", "spyro", "mgsvtpp", "mgsvgz", "deathstranding", "plaguetaleinnocence", "detroit", "portal", "portal2", "halflife", "halflife2", "persona5royal", "deusexhrdc"] = "auto"

    @field_validator("preferred_game", mode="before")
    @classmethod
    def retire_archived_game(cls, value):
        return "auto" if value in {"honkai3", "hito"} else value
    process_names: list[str] = Field(default_factory=lambda: ["ZenlessZoneZero.exe"])
    window_title_contains: list[str] = Field(
        default_factory=lambda: ["Zenless Zone Zero", "ZenlessZoneZero"]
    )
    region: CaptureRegion = Field(default_factory=CaptureRegion)
    tip_region: CaptureRegion = Field(
        default_factory=lambda: CaptureRegion(left=0.62, top=0.015, width=0.37, height=0.19)
    )
    cinematic_region: CaptureRegion = Field(
        default_factory=lambda: CaptureRegion(left=0.04, top=0.06, width=0.92, height=0.88)
    )
    hito_region: CaptureRegion = Field(
        default_factory=lambda: CaptureRegion(left=0.35, top=0.765, width=0.365, height=0.18)
    )
    hito_tip_region: CaptureRegion = Field(
        default_factory=lambda: CaptureRegion(left=0.31, top=0.075, width=0.38, height=0.16)
    )
    hito_auto_regions: bool = True
    cyberpunk_region: CaptureRegion = Field(default_factory=lambda: CaptureRegion(left=.12, top=.59, width=.76, height=.37))
    cyberpunk_tip_region: CaptureRegion = Field(default_factory=lambda: CaptureRegion(left=.10, top=.12, width=.70, height=.62))
    cyberpunk_capture_chatter: bool = True
    cyberpunk_v_voice: Literal["unconfigured", "female", "male"] = "unconfigured"
    wuwa_region: CaptureRegion = Field(default_factory=lambda: CaptureRegion(left=.10, top=.64, width=.80, height=.32))
    wuwa_tip_region: CaptureRegion = Field(default_factory=lambda: CaptureRegion(left=.58, top=.05, width=.40, height=.32))
    wuwa_capture_chatter: bool = False
    wuwa_cinematic_region: CaptureRegion = Field(default_factory=lambda: CaptureRegion(left=.12, top=.20, width=.76, height=.43))
    wuwa_capture_cinematic: bool = True
    wuwa_rover_voice: Literal["unconfigured", "female", "male"] = "unconfigured"
    witcher3_region: CaptureRegion = Field(default_factory=lambda: CaptureRegion(left=.08, top=.63, width=.84, height=.34))
    witcher3_tip_region: CaptureRegion = Field(default_factory=lambda: CaptureRegion(left=.08, top=0, width=.76, height=.74))
    witcher3_capture_chatter: bool = True
    beyond_region: CaptureRegion = Field(default_factory=lambda: CaptureRegion(left=.05, top=.70, width=.90, height=.28))
    heavyrain_region: CaptureRegion = Field(default_factory=lambda: CaptureRegion(left=.05, top=.70, width=.90, height=.28))
    riseofthetombraider_region: CaptureRegion = Field(default_factory=lambda: CaptureRegion(left=.08, top=.65, width=.84, height=.33))
    shadowofthetombraider_region: CaptureRegion = Field(default_factory=lambda: CaptureRegion(left=.08, top=.65, width=.84, height=.33))
    spyro_region: CaptureRegion = Field(default_factory=lambda: CaptureRegion(left=.04, top=.60, width=.92, height=.38))
    mgsvtpp_region: CaptureRegion = Field(default_factory=lambda: CaptureRegion(left=.04, top=.60, width=.92, height=.38))
    mgsvgz_region: CaptureRegion = Field(default_factory=lambda: CaptureRegion(left=.04, top=.60, width=.92, height=.38))
    deathstranding_region: CaptureRegion = Field(default_factory=lambda: CaptureRegion(left=.04, top=.60, width=.92, height=.38))
    plaguetaleinnocence_region: CaptureRegion = Field(default_factory=lambda: CaptureRegion(left=.04, top=.60, width=.92, height=.38))
    detroit_region: CaptureRegion = Field(default_factory=lambda: CaptureRegion(left=.04, top=.60, width=.92, height=.38))
    portal_region: CaptureRegion = Field(default_factory=lambda: CaptureRegion(left=.04, top=.60, width=.92, height=.38))
    portal2_region: CaptureRegion = Field(default_factory=lambda: CaptureRegion(left=.04, top=.60, width=.92, height=.38))
    halflife_region: CaptureRegion = Field(default_factory=lambda: CaptureRegion(left=.04, top=.60, width=.92, height=.38))
    halflife2_region: CaptureRegion = Field(default_factory=lambda: CaptureRegion(left=.04, top=.60, width=.92, height=.38))
    persona5royal_region: CaptureRegion = Field(default_factory=lambda: CaptureRegion(left=.04, top=.60, width=.92, height=.38))
    deusexhrdc_region: CaptureRegion = Field(default_factory=lambda: CaptureRegion(left=.04, top=.60, width=.92, height=.38))
    starrail_region: CaptureRegion = Field(default_factory=lambda: CaptureRegion(left=.10, top=.70, width=.80, height=.28))
    starrail_player_voice: Literal["unconfigured", "female", "male"] = "unconfigured"
    genshin_region: CaptureRegion = Field(default_factory=lambda: CaptureRegion(left=.10, top=.70, width=.80, height=.28))
    genshin_player_voice: Literal["unconfigured", "female", "male"] = "unconfigured"
    endfield_region: CaptureRegion = Field(default_factory=lambda: CaptureRegion(left=.10, top=.70, width=.80, height=.28))
    endfield_player_voice: Literal["unconfigured", "female", "male"] = "unconfigured"
    nte_region: CaptureRegion = Field(default_factory=lambda: CaptureRegion(left=.10, top=.70, width=.80, height=.28))
    nte_picture_area: Literal["window", "16:9"] = "window"
    nte_player_voice: Literal["unconfigured", "female", "male"] = "unconfigured"
    # Legacy visual-novel dialogue extends to the right client edge; cropping
    # at 92% cuts its final words. Start below the highlighted speaker strip.
    honkai3_region: CaptureRegion = Field(default_factory=lambda: CaptureRegion(left=.04, top=.72, width=.96, height=.24))
    honkai3_picture_area: Literal["window", "16:9"] = "window"
    # "ndi" reads frames from an NDI source on the local network instead of a
    # game window on this PC; ndi_game names the game being streamed.
    capture_source: Literal["window", "ndi"] = "window"
    ndi_source: str = Field(default="", max_length=256)
    ndi_game: GameId | None = None
    scan_interval_ms: int = Field(default=250, ge=100, le=5000)
    stable_frames: int = Field(default=2, ge=1, le=8)
    fuzzy_threshold: float = Field(default=82.0, ge=50, le=100)
    auto_start: bool = True
    save_unmatched: bool = False
    capture_unvoiced: bool = False

    @field_validator("process_names", "window_title_contains")
    @classmethod
    def strip_string_lists(cls, value: list[str]) -> list[str]:
        return [item.strip() for item in value if item.strip()]


class LanguageContext(BaseModel):
    source_language: str = 'zh'
    source_locale: str = 'zh-Hans'
    source_text: str | None = None
    translation_locale: str = 'en'
    translation_text: str | None = None
    audio_locale: str = 'zh-Hans'
    texts: dict[str, str] = Field(default_factory=dict)
    voice_status: Literal['voiced', 'unvoiced', 'unavailable', 'unknown'] = 'unknown'
    dialogue_kind: str | None = None

    @model_validator(mode='after')
    def legacy_language_defaults(self):
        if self.source_text is None:
            self.source_text = getattr(self, 'chinese', '')
        if self.translation_text is None:
            self.translation_text = getattr(self, 'english', '')
        return self


class TextMatch(LanguageContext):
    game: GameId = "zzz"
    text_id: str
    english: str
    chinese: str
    source_ocr: str
    score: float
    kind: Literal["exact", "fuzzy"]
    ambiguous: bool = False
    speaker_english: str | None = None
    speaker_chinese: str | None = None


class TranscriptLine(LanguageContext):
    id: int
    created_at: datetime
    session_id: str
    game: GameId = "zzz"
    source_ocr: str
    english: str
    chinese: str
    text_id: str
    score: float
    match_kind: str
    ambiguous: bool = False
    channel: Literal["dialogue", "gameplay", "tip", "cinematic"] = "dialogue"
    voiced: bool = False
    has_audio: bool = False
    # Runtime-only hint used while an already-mapped original voice is being
    # decoded. It is intentionally not persisted in SQLite.
    audio_pending: bool = False
    audio_source: Literal["original", "recording"] = "recording"
    speaker_english: str | None = None
    speaker_chinese: str | None = None
    favorite: bool = False

    @property
    def is_comic(self) -> bool:
        """Official comic subtitles can be captured without a voice mapping."""
        return self.game == "zzz" and self.channel == "cinematic" and is_comic_text_id(self.text_id)


class CaptureSnapshot(BaseModel):
    match_reason: str | None = None
    visible_text_ids: list[str] = Field(default_factory=list)
    running: bool = False
    phase: str = "stopped"
    message: str = "Capture is stopped"
    active_game: GameId | None = None
    window_title: str | None = None
    window_bounds: tuple[int, int, int, int] | None = None
    crop_bounds: tuple[int, int, int, int] | None = None
    tip_crop_bounds: tuple[int, int, int, int] | None = None
    cinematic_crop_bounds: tuple[int, int, int, int] | None = None
    last_ocr: str = ""
    last_ocr_confidence: float | None = None
    last_tip_ocr: str = ""
    last_tip_ocr_confidence: float | None = None
    last_tip_match_score: float | None = None
    last_cinematic_ocr: str = ""
    last_cinematic_ocr_confidence: float | None = None
    last_cinematic_match_score: float | None = None
    last_match_score: float | None = None
    last_scan_at: datetime | None = None
    last_error: str | None = None
