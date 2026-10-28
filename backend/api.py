from __future__ import annotations

import asyncio
import os
import json
import sys
import subprocess
import tempfile
import threading
from contextlib import asynccontextmanager, contextmanager, nullcontext
from pathlib import Path
from subprocess import TimeoutExpired
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Header, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, JSONResponse
from pydantic import BaseModel, Field, ConfigDict

from .voice_assets import VoiceAssetService
from .capture import CaptureService
from .config import SettingsStore
from .models import AppSettings, CaptureRegion, CaptureSnapshot, TranscriptLine
from .storage import TranscriptStore
from .textmaps import TextMapIndex
from .pragmata import PragmataTextIndex
from .hito import HitoTextIndex
from .pragmata_audio import PragmataVoiceAssetService
from .pragmata_updates import PragmataUpdateManager
from .local_game import LocalGameTextIndex
from .local_voice import LocalVoiceAssetService
from .local_game_updates import LocalGameUpdateManager
from .game_assets import LOCAL_GAMES
from .speakers import SpeakerResolver
from .updates import BackgroundUpdateManager
from .toolkit_update import ToolkitUpdater
from .lexirise import LexiriseService, LexiriseError, REQUEST_KEY
from .reading import LexiriseReadingService
from .runtime_handoff import CaptureHandoff
from .state_version import StateVersion
from .lexirise_settings import account_settings, STUDY_LANGUAGES
from .accounts import AccountStore
from .languages import translation_language, study_language, resolve_locale, GAME_LOCALES
from .language_preparation import LanguagePreparation
from .language_inventory import LanguageInventory
from .ndi_source import NDI_LINK, NdiUnavailable, list_sources as list_ndi_sources
from .windows import list_visible_windows, game_data_directory, installed_zzz_game_data_directory
from .installation import InstallationService
from .scoped_mobile_exports import ScopedMobileExports
from .automatic_mobile_export import AutomaticMobileExports
from .game_paths import GAMES, configured_install, clear_install, discover_install, save_install, validate_install
from .local_access import COMPANION_ORIGINS, LocalAccessMiddleware, local_access_allowed


PROJECT_ROOT = Path(os.environ.get("PROXY_TRANSCRIPT_PROJECT_ROOT", Path(__file__).resolve().parents[1]))
DATA_DIR = PROJECT_ROOT / "data"


class ManualIngest(BaseModel):
    text: str = Field(min_length=1, max_length=1000)


class FavoriteUpdate(BaseModel):
    favorite: bool


class WordProficiencyUpdate(BaseModel):
    start: int = Field(ge=0)
    proficiency: int = Field(ge=1, le=4)


class WordContextQuestion(BaseModel):
    start: int = Field(ge=0)
    question: str = Field(min_length=1, max_length=500)


class GrammarKnownUpdate(BaseModel):
    slug: str = Field(min_length=1, max_length=160, pattern=r"^[a-zA-Z0-9_-]+$")
    known: bool = Field(strict=True)


class SetupFolder(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str | None = Field(default=None, max_length=4096)
    use_automatic: bool = Field(default=False, strict=True)


class SetupComplete(BaseModel):
    model_config = ConfigDict(extra="forbid")
    auto_start: bool = Field(strict=True)


class SetupAction(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EventHub:
    def __init__(self, context=None) -> None:
        self.context = context
        self.clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self.clients.add(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self.clients.discard(websocket)

    async def broadcast(self, event: dict[str, object]) -> None:
        # Stamp before the first await: a delayed send retains its publication revision.
        if self.context:
            event = {**event, 'context': self.context()}
        async with self._lock:
            clients = list(self.clients)
        stale: list[WebSocket] = []
        for client in clients:
            try:
                await client.send_json(event)
            except Exception:
                stale.append(client)
        if stale:
            async with self._lock:
                for client in stale:
                    self.clients.discard(client)


class Runtime:
    def __init__(self) -> None:
        self.standby = os.environ.get('PROXY_TRANSCRIPT_STANDBY') == '1'
        self._updates_started = False
        self.toolkit_updater = ToolkitUpdater(PROJECT_ROOT)
        self.warm_task = None
        self.repair_task = None
        self.state_version = StateVersion()
        self.hub = EventHub(lambda: self.state_version.publish(self.accounts.generation))
        local_settings = Path(os.environ.get("LOCALAPPDATA", PROJECT_ROOT / "data")) / "Proxy Transcript/settings.json"
        existing_user = local_settings.is_file() or (DATA_DIR / "settings.json").is_file()
        self.settings = SettingsStore(local_settings, legacy_path=DATA_DIR / "settings.json")
        self.transcript = TranscriptStore(DATA_DIR / "transcript-v2.db")
        self.accounts = AccountStore()
        self.lexirise = LexiriseService(DATA_DIR / "lexirise", accounts=self.accounts)
        self.reading = LexiriseReadingService(DATA_DIR / "lexirise", self.lexirise)
        self._readers = {}
        self.textmaps = TextMapIndex(DATA_DIR / "textmaps")
        self.pragmata = PragmataTextIndex(DATA_DIR / "pragmata")
        self.pragmata.load()
        self.hito = HitoTextIndex(DATA_DIR / "hito")
        self.voice_assets = VoiceAssetService(
            DATA_DIR / "voice-assets/manifest.json",
            DATA_DIR / "voice-assets/vgmstream/vgmstream-cli.exe",
            DATA_DIR / "audio",
            DATA_DIR / "voice-assets/learned-manifest.json",
        )
        self._legacy_zzz_voice = self.voice_assets
        self._legacy_zzz_index = self.textmaps
        self.pragmata_voice_assets = PragmataVoiceAssetService(
            DATA_DIR / "pragmata",
            DATA_DIR / "voice-assets/vgmstream/vgmstream-cli.exe",
            DATA_DIR / "audio",
        )
        self._legacy_pragmata_voice = self.pragmata_voice_assets
        self._legacy_pragmata_index = self.pragmata
        self.game_indexes = {game: LocalGameTextIndex(game, DATA_DIR / game) for game in LOCAL_GAMES}
        self.game_voice_assets = {game: LocalVoiceAssetService(game, DATA_DIR / game,
            DATA_DIR / "voice-assets/vgmstream/vgmstream-cli.exe", DATA_DIR / "audio") for game in self.game_indexes}
        self._legacy_game_voices = tuple(self.game_voice_assets.values())
        self._legacy_game_voice_map = dict(self.game_voice_assets)
        self._legacy_game_indexes = dict(self.game_indexes)
        self.speakers = SpeakerResolver(self.textmaps, self.voice_assets, self.transcript)
        self.event_loop = asyncio.get_running_loop()
        removed_rows = [] if self.standby else self.transcript.purge_unvoiced()
        if not self.standby:
            removed_rows.extend(self.transcript.prune(keep_nonfavorite=50))
        audio_dir = (DATA_DIR / "audio").resolve()
        for _, filename in removed_rows:
            if not filename:
                continue
            path = (audio_dir / filename).resolve()
            if path.parent == audio_dir:
                path.unlink(missing_ok=True)
        self.capture = CaptureService(
            settings=self.settings,
            textmaps=self.textmaps,
            pragmata=self.pragmata,
            transcript=self.transcript,
            on_line=self.on_line,
            on_delete=self.on_delete,
            on_status=self.on_capture_status,
            audio_dir=DATA_DIR / "audio",
            voice_assets=self.voice_assets,
            pragmata_voice_assets=self.pragmata_voice_assets,
            hito=self.hito,
            game_indexes=self.game_indexes,
            game_voice_assets=self.game_voice_assets,
        )
        self.map_task: asyncio.Task[None] | None = None
        self.update_manager = BackgroundUpdateManager(
            PROJECT_ROOT, self.textmaps, self.voice_assets, self.on_update_thread
        )
        self.pragmata_updater = PragmataUpdateManager(
            PROJECT_ROOT, self.pragmata, self.pragmata_voice_assets, self.on_update_thread
        )
        self.game_updaters = {game: LocalGameUpdateManager(game, self.game_indexes[game], voices,
            self.on_update_thread, project_root=PROJECT_ROOT) for game, voices in self.game_voice_assets.items()}
        self.languages = LanguagePreparation(self.build_language, self.activate_language, self.language_state,
            supported=self.reader_locales, cancellable=True,
            rebuild=lambda game, locale, targets, **options: self.build_language(game, locale, targets, force=True, **options))
        self._locale_indexes, self._locale_voices, self._active_locales = {}, {}, {}
        self._locale_voice_lock = threading.RLock()
        self.capture.recorded_voice_assets = self.recorded_voice_assets
        self.capture.language_setup = self.capture_language_ready
        self.capture.language_problem = self.capture_language_problem
        self.capture.context_scope = lambda: self.accounts.generation
        self.installation = InstallationService(PROJECT_ROOT, settings=self.settings,
            game_state=self.setup_game_state, refresh=self.refresh_game, existing_user=existing_user,
            account_configured=lambda: self.lexirise.status()["configured"], install_lookup=self.setup_install)
        self.index_task: asyncio.Task[None] | None = None
        self.mobile_exports = ScopedMobileExports(PROJECT_ROOT, self.accounts, self.languages)
        self.automatic_exports = AutomaticMobileExports(PROJECT_ROOT, install_lookup=self.setup_install)
        self.language_inventory = LanguageInventory(DATA_DIR, self.setup_install)

    def account_preferences(self):
        session = self.lexirise.pin()
        if not hasattr(session, '_settings_payload'):
            account_settings(session)
        return session._settings_payload

    def reader_locales(self, game):
        # Each subsequent reader release supplies an explicit locale contract.
        if game in {*LOCAL_GAMES, 'pragmata', 'zzz'}:
            from .game_assets import asset_adapter
            adapter, _ = asset_adapter(game)
            return getattr(adapter, 'SUPPORTED_LOCALES', ('zh-Hans',))
        return ('zh-Hans',)

    def build_language(self, game, locale, targets, *, force=False, job=None):
        from .game_assets import asset_adapter
        from .multilingual_index import MultilingualTextIndex
        if job:
            job.checkpoint()
        if game in {*LOCAL_GAMES, 'pragmata', 'zzz'}:
            adapter, _ = asset_adapter(game)
            if hasattr(adapter, 'index_language'):
                install = self.setup_install(game)
                if install is None:
                    raise ValueError('Choose the installed game folder before preparing its language.')
                directory = DATA_DIR / 'languages' / game / locale
                directory.mkdir(parents=True, exist_ok=True)
                path = directory / 'textmap.json'
                stamp = adapter.fingerprint(install)
                indexes = self.__dict__.setdefault('_locale_indexes', {})
                key = (game, locale)
                cached = indexes.get(key)
                if cached is None:
                    cached = indexes[key] = MultilingualTextIndex(game, directory)
                    current_table = cached.ready
                else:
                    current_table = cached.load()
                # The validated generation already owns the large text table.
                # Periodic checks need its tiny metadata, not another full JSON
                # allocation while capture is matching the same records.
                old = cached.snapshot_metadata
                if not current_table:
                    try:
                        old = json.loads(path.read_text(encoding='utf-8'))
                    except (OSError, ValueError):
                        old = {}
                if (not force and old.get('format') == 2 and old.get('game') == game and old.get('source_locale') == locale
                        and old.get('fingerprint') == stamp and old.get('targets_requested') == sorted(targets)
                        and old.get('reader_revision') == adapter.LANGUAGE_INDEX_VERSION
                        and old.get('install') == str(install)):
                    # Matching metadata alone does not prove the table is usable.
                    # A truncated/invalid snapshot used to be skipped forever.
                    # load() cheaply reuses an unchanged validated file. Its
                    # return value is essential: a failed reload can retain an
                    # older usable in-memory index while disk still needs repair.
                    if current_table and cached.ready and cached.source_locale == locale and cached.entry_count:
                        return
                from .update_workers import INDEX_BUILD_LOCK, subprocess_options
                if job:
                    job.report('queued', 'Waiting for another game to finish preparing; capture stays available')
                with (job.acquire(INDEX_BUILD_LOCK) if job else INDEX_BUILD_LOCK), tempfile.TemporaryDirectory(prefix='language-', dir=directory) as temporary:
                    if job:
                        job.report('extracting', 'Reading official subtitles and original voice mappings; large games can take several minutes (30-minute limit)')
                    output = Path(temporary) / 'textmap.json'
                    command = [sys.executable, '-m', 'backend.language_worker', '--game', game,
                        '--install', str(install), '--directory', str(DATA_DIR / game), '--locale', locale,
                        '--targets', json.dumps(targets), '--output', str(output)]
                    if job:
                        returncode = job.run(command, cwd=Path(__file__).resolve().parents[1], timeout=1800,
                                             progress_path=output.with_name('progress.json'), **subprocess_options())
                    else:
                        returncode = subprocess.run(command, cwd=Path(__file__).resolve().parents[1],
                            capture_output=True, text=True, timeout=1800, **subprocess_options()).returncode
                    if returncode:
                        from .preparation_errors import PreparationFailure, public_failure
                        failure = public_failure(RuntimeError())
                        try:
                            failure = json.loads(output.with_name('failure.json').read_text(encoding='utf-8'))
                            output.with_name('failure.log').replace(directory / 'last-preparation-error.log')
                        except (OSError, ValueError):
                            pass
                        changed = bool(old.get('fingerprint') and old['fingerprint'] != stamp)
                        message = failure['message']
                        if changed:
                            message = 'Installed game files changed since the last preparation. ' + message
                        if old:
                            message += ' The previous table was kept; changed voice files may remain unavailable until repair succeeds.'
                        raise PreparationFailure(failure.get('code', 'reader_failed'), message,
                            game_files_changed=changed, previous_snapshot_retained=bool(old),
                            retry_seconds=failure.get('retry_seconds', 120))
                    if job:
                        job.report('validating', 'Validating the replacement language table before activation')
                    candidate = MultilingualTextIndex(game, Path(temporary))
                    if not candidate.ready or candidate.source_locale != locale or adapter.fingerprint(install) != stamp:
                        raise ValueError('Language snapshot is incomplete or game files changed; previous table retained.')
                    with job.publication() if job else nullcontext():
                        output.replace(path)
                if hasattr(self, 'automatic_exports'):
                    self.automatic_exports.wake.set()
                return
        if job:
            raise ValueError('This reader cannot prepare a cancellable language snapshot; previous table retained.')
        if locale != 'zh-Hans' or any(target.lower() not in {'en', 'zh-hans', 'zh'} for target in targets):
            raise ValueError('This language pair needs the multilingual reader update. No other language was substituted.')
        if game == 'zzz':
            self.update_manager.check_once()
        elif game == 'pragmata':
            self.pragmata_updater._run()
        else:
            self.game_updaters[game]._run()

    def language_state(self, game, locale):
        path = DATA_DIR / 'languages' / game / locale
        missing = {'ready': False, 'state': 'not_ready', 'message': 'The selected language table is unavailable; prepare or rebuild it in Languages.',
                   'source_locale': locale, 'entry_count': 0, 'audio_count': 0}
        if (path / 'textmap.json').is_file():
            from .multilingual_index import MultilingualTextIndex
            key = (game, locale)
            index = self._locale_indexes.get(key)
            if index is None:
                index = self._locale_indexes[key] = MultilingualTextIndex(game, path)
            index.load()
            return index.status() if index.source_locale == locale else missing
        if locale != 'zh-Hans' or path.parent.is_dir():
            return missing
        if game == 'zzz':
            index = getattr(self, '_legacy_zzz_index', self.textmaps).status()
            count = getattr(self, '_legacy_zzz_voice', self.voice_assets).status().get('mapped_lines', 0)
        elif game == 'pragmata':
            index = getattr(self, '_legacy_pragmata_index', self.pragmata).status()
            count = getattr(self, '_legacy_pragmata_voice', self.pragmata_voice_assets).status().get('mapped_lines', 0)
        else:
            index = getattr(self, '_legacy_game_indexes', self.game_indexes)[game].status()
            count = index.get('audio_count', 0)
        return {**index, 'source_locale': locale, 'audio_count': count} if index.get('source_locale') in (None, locale) else missing

    def activate_language(self, game, locale, account):
        if account != self.accounts.status()['active'] or self.languages.selected(game, account) != locale:
            return False
        directory = DATA_DIR / 'languages' / game / locale
        if (directory / 'textmap.json').is_file():
            from .multilingual_index import MultilingualTextIndex
            key = (game, locale)
            index = self._locale_indexes.get(key)
            if index is None:
                index = self._locale_indexes[key] = MultilingualTextIndex(game, directory)
            index.load()
            voices = self.language_voice_assets(game, locale)
            if not index.ready or index.source_locale != locale or voices is None:
                return False
            try:
                settings = self.account_preferences()
                source = study_language(locale)
                index.target_locale = (translation_language(settings, source) if source in settings['languages']
                                       else self.languages.selected_target(game, locale, account))
            except LexiriseError:
                index.target_locale = self.languages.selected_target(game, locale, account)
            if game == 'zzz':
                self.textmaps = self.capture.textmaps = index
                self.voice_assets = self.capture.voice_assets = voices
            elif game == 'pragmata':
                self.pragmata = self.capture.pragmata = index
                self.pragmata_voice_assets = self.capture.pragmata_voice_assets = voices
            else:
                self.game_indexes[game] = index
                self.game_voice_assets[game] = voices
        elif locale == 'zh-Hans':
            if game == 'zzz':
                self.textmaps = self.capture.textmaps = self._legacy_zzz_index
                self.voice_assets = self.capture.voice_assets = self._legacy_zzz_voice
            elif game == 'pragmata':
                self.pragmata = self.capture.pragmata = self._legacy_pragmata_index
                self.pragmata_voice_assets = self.capture.pragmata_voice_assets = self._legacy_pragmata_voice
            elif game in self._legacy_game_indexes:
                self.game_indexes[game] = self._legacy_game_indexes[game]
                self.game_voice_assets[game] = self._legacy_game_voice_map[game]
        else:
            return False
        if self._active_locales.get(game) != locale:
            self._active_locales[game] = locale
            self.capture._scan_epoch += 1
        return True

    def language_voice_assets(self, game, locale):
        if game not in GAME_LOCALES or locale not in GAME_LOCALES[game]:
            return None
        directory = DATA_DIR / 'languages' / game / locale
        if not (directory / 'textmap.json').is_file():
            return None
        with self._locale_voice_lock:
            key = (game, locale)
            voices = self._locale_voices.get(key)
            if voices is None:
                decoder = DATA_DIR / 'voice-assets/vgmstream/vgmstream-cli.exe'
                voices = (PragmataVoiceAssetService(directory, decoder, DATA_DIR / 'audio', tools_dir=DATA_DIR / game / 'tools')
                          if game == 'pragmata' else LocalVoiceAssetService(game, directory, decoder,
                              DATA_DIR / 'audio', tools_dir=DATA_DIR / game / 'tools'))
                self._locale_voices[key] = voices
            voices.reload()
            return voices if voices.locale == locale else None

    def recorded_voice_assets(self, line):
        # Historical playback reads an existing snapshot without selecting or
        # preparing another language or changing account preferences.
        scoped = self.language_voice_assets(line.game, line.source_locale)
        if scoped and scoped.has_variant(line.text_id, line.english):
            return scoped
        if line.game == 'zzz' and line.source_locale == 'zh-Hans':
            return self._legacy_zzz_voice
        if scoped:
            return scoped
        return self.capture._assets_for(line.game)

    def capture_language_problem(self, game):
        account = self.accounts.status()['active']
        locale = self.languages.selected(game, account)
        if not locale:
            with self.languages.lock:
                choice = self.languages.data.get('requested', {}).get(account, {}).get(game)
                pending = dict(self.languages.jobs.get((game, choice['locale']), {})) if choice else {}
            if choice:
                return f"{choice['locale']}: {pending.get('message', 'Your requested language is queued for preparation.')}"
            return 'Choose a game language and press Prepare language below. The toolkit will keep it ready automatically.'
        with self.languages.lock:
            job = dict(self.languages.jobs.get((game, locale), {}))
        if job.get('state') == 'preparing':
            return f"{locale}: {job['message']}. This runs automatically for all configured games."
        if job.get('state') == 'error':
            return f"{locale}: {job['message']} {job.get('retry_after', 'Check Games & Languages to retry.')}"
        return f'{locale}: the prepared table is missing or cannot be activated. Automatic repair checks run every 2 minutes; see Setup → Languages.'

    def capture_language_ready(self, game):
        if game == 'hito':
            return True
        account = self.accounts.status()['active']
        locale = self.languages.selected(game, account)
        if not locale or not self.languages.prepared(game, locale):
            return False
        return self.activate_language(game, locale, account)

    def reading_for(self, line: TranscriptLine):
        session = self.lexirise.pin(line.source_language)
        if not hasattr(session, '_settings_payload'):
            account_settings(session)
        target = translation_language(session._settings_payload, line.source_language)
        key = (session._scope(), line.source_language, target, session._settings_scope)
        if key not in self._readers:
            self._readers[key] = LexiriseReadingService(DATA_DIR / 'lexirise', session,
                source_language=line.source_language, translation_language=target)
        return self._readers[key]

    def present_line(self, line: TranscriptLine) -> TranscriptLine:
        try:
            settings = self.account_preferences()
            target = (translation_language(settings, line.source_language) if line.source_language in settings['languages']
                      else line.translation_locale)
        except LexiriseError:
            if not self.lexirise.status()['configured']:
                return line
            target = ''
        texts = line.texts or {'en': line.english, 'zh-Hans': line.chinese}
        locale = resolve_locale(target, texts)
        prepared = self.languages.prepared(line.game, line.source_locale)
        if prepared and target not in prepared['targets']:
            locale = None
        return line.model_copy(update={'translation_locale': locale or target,
                                      'translation_text': texts.get(locale, '') if locale else ''})

    def setup_install(self, game: str) -> Path | None:
        install = discover_install(game)
        if install:
            return install
        if game == "zzz":
            data = installed_zzz_game_data_directory(self.settings.get())
            return data.parent if data else None
        if game == "pragmata":
            from scripts.index_pragmata_assets import find_install
            return find_install()
        from .games import GAME_PROFILES
        from .windows import executable_path_for_window
        for window in list_visible_windows():
            if window.process_name.casefold() not in {name.casefold() for name in GAME_PROFILES[game].process_names}:
                continue
            executable = executable_path_for_window(window)
            if executable:
                depth = 5 if game == "nte" else 3 if game == "wuwa" else 2 if game in {"cyberpunk", "witcher3"} else 0
                try:
                    return validate_install(game, executable.parents[depth])
                except (OSError, ValueError, IndexError):
                    continue
        return None

    def setup_game_state(self, game: str) -> dict:
        account = self.accounts.status()['active']
        locale = self.languages.selected(game, account) if game in GAME_LOCALES else None
        if locale:
            prepared = self.languages.prepared(game, locale)
            index = self.language_state(game, locale) if prepared else {'ready': False, 'state': 'not_ready', 'source_locale': locale,
                'message': 'Prepare the selected learning language in Languages.'}
            audio = {'ready': bool(index.get('ready') and index.get('audio_count'))}
            with self.languages.lock:
                job = dict(self.languages.jobs.get((game, locale), {}))
            pending = job.get('state') in {'preparing', 'error'}
            update = {'state': job['state'] if pending else index.get('state', 'waiting'), 'progress': job.get('progress', 100),
                      'message': job.get('message', '') if pending else index.get('message', ''), 'last_checked': (prepared or {}).get('prepared_at'),
                      'last_error': job.get('message') if job.get('state') == 'error' else None}
        elif game in GAME_LOCALES and account != 'legacy':
            index = {'ready': False, 'state': 'needs_language_setup', 'message': 'Select and prepare a learning language in Languages.'}
            audio, update = {}, {'state': 'waiting', 'progress': 0}
        elif game == "zzz":
            index = getattr(self, '_legacy_zzz_index', self.textmaps).status()
            audio, update = getattr(self, '_legacy_zzz_voice', self.voice_assets).status(), self.update_manager.status()
        elif game == "pragmata":
            index = getattr(self, '_legacy_pragmata_index', self.pragmata).status()
            audio, update = getattr(self, '_legacy_pragmata_voice', self.pragmata_voice_assets).status(), self.pragmata_updater.status()
        elif game == "hito":
            index, audio, update = self.hito.status(), {}, {"state": "automatic", "progress": 100}
        else:
            index = getattr(self, '_legacy_game_indexes', self.game_indexes)[game].status()
            audio = getattr(self, '_legacy_game_voice_map', self.game_voice_assets)[game].status()
            update = self.game_updaters[game].status()
        return {"index_ready": bool(index.get("ready")), "index_state": index.get("state"),
                'source_locale': index.get('source_locale'),
                "index_message": index.get("message", ""), "indexed_lines": index.get("entry_count", 0),
                "audio_ready": bool(audio.get("ready")), "update_state": update.get("state", "idle"),
                "update_message": update.get("message", "Game data checks run automatically"),
                "progress": update.get("progress", 100), "last_checked": update.get("last_checked"),
                "catalog_message": update.get("catalog_message"), "catalog_warning": update.get("catalog_warning", False),
                "needs_attention": bool(update.get("last_error"))}

    def refresh_game(self, game: str) -> bool:
        if game not in GAMES:
            raise ValueError("Unsupported game")
        if game != 'hito':
            prepared = [(locale, targets) for title, locale, targets in self.languages.entries() if title == game]
            return any([self.languages.request(game, locale, targets[0], refresh=True)
                        for locale, targets in prepared if targets])
        self.hito.ensure_game_files(None)
        return self.hito.refresh()

    def start_updates(self) -> None:
        if self._updates_started:
            return
        self._updates_started = True
        self.languages.start()
        if hasattr(self, 'toolkit_updater'):
            self.toolkit_updater.start()
        if hasattr(self, 'automatic_exports'):
            self.automatic_exports.start()
        self.start_audio_repair()

    def start_audio_repair(self) -> None:
        if self.standby or not self._updates_started or (self.repair_task and not self.repair_task.done()):
            return
        self.repair_task = asyncio.create_task(self.repair_recent_audio(), name='repair-original-voices')

    async def repair_recent_audio(self) -> None:
        # One historical request at a time leaves decoding capacity available
        # for the game. Newly discovered comic mappings repair existing rows.
        loop = asyncio.get_running_loop()
        for line in self.transcript.list(limit=50):
            ready = asyncio.Event()
            if self.capture.repair_recorded_line(line, completed=lambda: loop.call_soon_threadsafe(ready.set)):
                try:
                    await asyncio.wait_for(ready.wait(), 45)
                except asyncio.TimeoutError:
                    return

    async def stop_updates(self) -> None:
        self._updates_started = False
        if hasattr(self, 'toolkit_updater'):
            self.toolkit_updater.close()
        if hasattr(self, 'automatic_exports'):
            await asyncio.to_thread(self.automatic_exports.close)
        await asyncio.to_thread(self.languages.close)
        if self.repair_task:
            self.repair_task.cancel()
            try:
                await self.repair_task
            except asyncio.CancelledError:
                pass
            self.repair_task = None
        if self.index_task:
            self.index_task.cancel()
            try:
                await self.index_task
            except asyncio.CancelledError:
                pass
            self.index_task = None
        await asyncio.gather(*(asyncio.to_thread(updater.close) for updater in
            [self.update_manager, self.pragmata_updater, *self.game_updaters.values()]))
        self._updates_started = False

    async def on_line(self, line: TranscriptLine) -> None:
        # Capture/audio threads can queue this coroutine before a favorite,
        # audio completion or deletion. Publish the current row, not that old
        # object with a new revision; deleted rows must stay deleted.
        audio_pending = line.audio_pending
        line = self.transcript.get(line.id)
        if line is None:
            return
        line = self.present_line(line)
        if line.game == "zzz":
            line = self.speakers.enrich(line)
        if audio_pending and not line.has_audio:
            # Preserve this transient notice only until original audio is ready.
            line = line.model_copy(update={"audio_pending": True})
        await self.hub.broadcast({"type": "line", "line": line.model_dump(mode="json")})

    def on_update_thread(self, update: dict[str, object]) -> None:
        asyncio.run_coroutine_threadsafe(
            self.hub.broadcast({"type": "update_status", "updates": self.update_status()}),
            self.event_loop,
        )
        if update.get('state') in {'ready', 'idle'}:
            self.event_loop.call_soon_threadsafe(self.start_audio_repair)

    async def on_delete(self, line_id: int) -> None:
        await self.hub.broadcast({"type": "line_deleted", "line_id": line_id})

    async def on_capture_status(self, status: CaptureSnapshot) -> None:
        await self.hub.broadcast({"type": "capture_status", "capture": status.model_dump(mode="json")})

    def update_status(self) -> dict[str, object]:
        return self.languages.update_status()

    def context(self):
        return self.state_version.snapshot(self.accounts.generation)

    def status(self) -> dict[str, object]:
        context = self.context()
        return {
            "context": context,
            "capture": self.capture.snapshot().model_dump(mode="json"),
            "textmaps": self.textmaps.status(),
            "game_textmaps": {
                "zzz": self.textmaps.status(),
                "pragmata": self.pragmata.status(),
                "hito": self.hito.status(),
                **{game: index.status() for game, index in self.game_indexes.items()},
            },
            "audio": {"ready": self.voice_assets.ready or self.pragmata_voice_assets.ready or any(v.ready for v in self.game_voice_assets.values()),
                      "message": "Original voices from game files; matched by visible subtitles",
                      "clip_mode": "subtitle-game-files", "listening": False},
            "voice_assets": self.voice_assets.status(),
            "pragmata_voice_assets": self.pragmata_voice_assets.status(),
            "game_voice_assets": {game: v.status() for game, v in self.game_voice_assets.items()},
            "updates": self.update_status(),
            "selected_languages": {game: {'source_locale': locale, 'source_language': study_language(locale)}
                for game in GAME_LOCALES if (locale := self.languages.selected(game, self.accounts.status()['active']))},
            "settings": self.settings.get().model_dump(mode="json"),
            "session": {
                "id": self.capture.session_id,
                "line_count": self.transcript.count(self.capture.session_id),
                "total_line_count": self.transcript.count(),
            },
        }

    def start_map_prepare(self, force: bool = False) -> bool:
        if self.map_task and not self.map_task.done():
            return False
        self.map_task = asyncio.create_task(self.prepare_maps(force), name="textmap-prepare")
        return True

    async def prepare_maps(self, force: bool = False) -> None:
        # A language switch may replace the active index while this task waits.
        # Legacy preparation must never call its APIs on a multilingual index.
        index = self._legacy_zzz_index
        try:
            await asyncio.to_thread(
                index.prepare,
                force_download=force,
                progress=index.set_message,
            )
            if not self.standby:
                await asyncio.to_thread(self.speakers.backfill)
        except Exception as error:
            index.state = "ready" if index.ready else "error"
            index.message = "Refresh failed; keeping the previous complete TextMaps" if index.ready else str(error)
        await self.hub.broadcast({"type": "textmaps_status", "textmaps": self.textmaps.status()})


runtime: Runtime


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global runtime
    runtime = Runtime()
    if (runtime.capture_language_ready('zzz') and runtime.textmaps is runtime._legacy_zzz_index
            and runtime._legacy_zzz_index.file_path("zh_base").is_file()):
        runtime.start_map_prepare()
    if runtime.standby:
        runtime.warm_task = asyncio.create_task(runtime.capture.warmup(), name='prepare-replacement-ocr')
    else:
        runtime.start_updates()
    if not runtime.standby and runtime.settings.get().auto_start and runtime.installation.completed:
        runtime.capture.start()
    try:
        yield
    finally:
        if runtime.warm_task:
            try:
                await runtime.warm_task
            except (Exception, asyncio.CancelledError):
                pass
        runtime.mobile_exports.cancel_all()
        runtime.standby = True
        await runtime.stop_updates()
        await runtime.capture.close()
        await asyncio.to_thread(runtime.hito.close)
        runtime._legacy_zzz_voice.close()
        runtime._legacy_pragmata_voice.close()
        for reader in runtime._readers.values():
            reader.pool.shutdown(wait=False, cancel_futures=True)
        for voices in set([*runtime._legacy_game_voices, *runtime.game_voice_assets.values(), *runtime._locale_voices.values()]):
            voices.close()
        if runtime.map_task and not runtime.map_task.done():
            runtime.map_task.cancel()
            try:
                await runtime.map_task
            except asyncio.CancelledError:
                pass


app = FastAPI(title="Proxy Transcript API", version="0.1.0", lifespan=lifespan)


@app.middleware('http')
async def pin_account_request(request: Request, call_next):
    current = globals().get('runtime')
    guarded = request.url.path.startswith('/api/lexirise/settings') or request.url.path.startswith('/api/lexirise/decks') or (
        request.url.path.startswith('/api/lines/') and ('/reading' in request.url.path or request.url.path.endswith('/lexirise')))
    if not guarded or not hasattr(current, 'accounts'):
        return await call_next(request)
    with current.accounts.lock:
        account = current.accounts.status()['active']
        expected = request.headers.get('x-proxy-transcript-account')
        if expected is not None and expected != account:
            return JSONResponse({'detail': 'Account changed. Reload before retrying this operation.'}, status_code=409)
        try:
            key = current.lexirise._key()
        except LexiriseError:
            return JSONResponse({'detail': 'Configure a Lexirise account on this PC.'}, status_code=503)
    token = REQUEST_KEY.set(key)
    try:
        return await call_next(request)
    finally:
        REQUEST_KEY.reset(token)


app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted(COMPANION_ORIGINS),
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["*"],
)
# Outermost: reject HTTP/preflight and WebSocket requests before account pinning,
# endpoint side effects, acceptance, or capture/status snapshots.
app.add_middleware(LocalAccessMiddleware)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def runtime_access(request: Request, action: str) -> None:
    if request.url.hostname not in {'127.0.0.1', 'localhost'} or action != 'update':
        raise HTTPException(403, 'Use the local companion updater')


@app.get('/api/runtime/ready')
def runtime_ready(game: str | None = None) -> dict:
    indexes = {'zzz': runtime.textmaps, 'pragmata': runtime.pragmata, 'hito': runtime.hito, **runtime.game_indexes}
    if game in GAME_LOCALES:
        # A standby replacement has not captured a frame yet, so its legacy
        # index may still be empty. Check the explicitly prepared snapshot
        # without activating capture, building tables or reading an account API.
        account = runtime.accounts.status()['active']
        locale = runtime.languages.selected(game, account)
        if locale:
            index_ready = bool(runtime.languages.prepared(game, locale)
                               and runtime.language_state(game, locale).get('ready'))
        else:
            # Older installations have no explicit language selection yet.
            # Let their complete legacy index warm the upgrade; capture still
            # requires explicit preparation in the replacement. Never reuse a
            # locale index activated for a different account.
            index = indexes.get(game)
            index_ready = bool(index and index.ready and not getattr(index, 'source_locale', None))
    else:
        index_ready = game is None or (game in indexes and indexes[game].ready)
    warm = runtime.warm_task is None or (runtime.warm_task.done() and not runtime.warm_task.cancelled()
                                         and runtime.warm_task.exception() is None)
    return {'ready': bool(index_ready and warm), 'standby': runtime.standby}


@app.post('/api/runtime/quiesce')
async def runtime_quiesce(request: Request, x_proxy_transcript: str = Header(default='')) -> dict:
    runtime_access(request, x_proxy_transcript)
    running = runtime.capture.snapshot().running
    # Stop resource-heavy refreshes while capture is still serving the old app.
    await runtime.stop_updates()
    await runtime.capture.stop()
    runtime.standby = True
    return runtime.capture.export_handoff(running).model_dump()


@app.post('/api/runtime/activate')
async def runtime_activate(payload: CaptureHandoff, request: Request,
                           x_proxy_transcript: str = Header(default='')) -> dict:
    runtime_access(request, x_proxy_transcript)
    if not runtime_ready()['ready']:
        raise HTTPException(409, 'Replacement OCR is still warming up')
    if runtime.capture.snapshot().running:
        # A failed quiesce may stop updates while leaving capture serving.
        # Rollback resumes that work without replacing its live session.
        runtime.standby = False
        runtime.start_updates()
        return {'active': True}
    runtime.capture.import_handoff(payload)
    runtime.standby = False
    if payload.running:
        runtime.capture.start()
    runtime.start_updates()
    return {'active': True}


@app.get("/api/status")
def get_status() -> dict[str, object]:
    return runtime.status()


def read_context():
    # Lightweight fixture runtimes may omit the transport clock.
    return runtime.context() if hasattr(runtime, 'context') else None


def check_read_context(context):
    if context is not None and context['account_generation'] != runtime.accounts.generation:
        raise HTTPException(409, 'Account changed while reading. Reload the current context.')


@app.get('/api/snapshot')
def companion_snapshot() -> dict:
    context = read_context()  # Before status, SQLite, enrichment or account reads.
    status = runtime.status()
    lines = {}
    # Retired capture adapters still have read-only transcript/favorite history.
    for game in (*GAMES, 'hito'):
        for line in [*get_lines(limit=50, before_id=None, game=game), *get_favorites(game=game)]:
            lines[line.id] = line.model_dump(mode='json')
    # This ledger read does not request remote account preferences.
    integration = integration_status(refresh_settings=False)
    check_read_context(context)
    return {'context': context, 'status': status, 'lines': list(lines.values()), 'lexirise': integration}


def setup_access(request: Request, header: str | None = None, *, write: bool = False) -> None:
    if not local_access_allowed(request.scope.get('headers', [])):
        raise HTTPException(403, "Setup is available only on this PC")
    if write and header != "setup":
        raise HTTPException(403, "Setup action header required")


@app.get("/api/setup")
def setup_status(request: Request, game: str | None = None) -> dict:
    setup_access(request)
    if game is not None and game not in GAMES:
        raise HTTPException(404, 'Unsupported game')
    accounts = getattr(runtime, 'accounts', None)
    with accounts.lock if accounts else nullcontext():
        exports = runtime.mobile_exports if hasattr(runtime, 'mobile_exports') else None
        status = (exports.status(game) if game and hasattr(exports, 'require_scope') else exports.status()) if exports else None
        return {**runtime.installation.status(), 'mobile_export': status}


class LanguageAction(BaseModel):
    model_config = ConfigDict(extra='forbid')
    locale: str = Field(min_length=2, max_length=24)
    action: Literal['prepare', 'rebuild', 'select', 'remove', 'cleanup'] = 'prepare'
    target: str | None = Field(default=None, max_length=24)


@app.get('/api/setup/games/{game}/languages')
def game_languages(game: str, request: Request) -> dict:
    setup_access(request)
    if game not in GAMES or game not in GAME_LOCALES:
        raise HTTPException(404, 'Unsupported game language setup')
    context = read_context()
    try:
        result = runtime.languages.status(game, runtime.accounts.status()['active'])
        inventory = runtime.language_inventory.status(game, result)
        for row in result['locales']:
            row.update(inventory['locales'].get(row['locale'], {}))
        result.update({key: value for key, value in inventory.items() if key != 'locales'})
        try:
            settings = runtime.account_preferences()
            result['enabled_languages'] = settings['languages']
            result['targets'] = {source: translation_language(settings, source) for source in settings['languages']}
        except LexiriseError:
            result['enabled_languages'] = None
            result['targets'] = {}
        check_read_context(context)
        return {**result, 'context': context}
    except (ValueError, LexiriseError) as error:
        raise HTTPException(400, str(error)) from None


@app.post('/api/setup/games/{game}/languages')
def prepare_game_language(game: str, payload: LanguageAction, request: Request,
                          x_proxy_transcript: str = Header(default='')) -> dict:
    setup_access(request, x_proxy_transcript, write=True)
    if game not in GAMES or game not in GAME_LOCALES:
        raise HTTPException(404, 'Unsupported game language setup')
    try:
        account = runtime.accounts.status()['active']
        if payload.action == 'cleanup':
            busy = runtime.mobile_exports.status(game).get('state') in {'preparing', 'exporting', 'cancelling'}
            result = runtime.language_inventory.cleanup(game, payload.locale, runtime.languages, busy)
            runtime.capture._scan_epoch += 1
            runtime._locale_indexes.pop((game, payload.locale), None)
            runtime._locale_voices.pop((game, payload.locale), None)
            return result
        if payload.action == 'remove':
            runtime.languages.remove(game, payload.locale)
            return {'removed': True}
        source = study_language(payload.locale)
        if payload.action == 'select':
            runtime.languages.select(game, payload.locale, account, target=payload.target)
            return {'selected': payload.locale}
        settings = runtime.account_preferences() if runtime.lexirise.status()['configured'] else None
        # Account membership controls the picker and account features, not local play.
        target = translation_language(settings, source) if settings and source in settings['languages'] else payload.target
        if not target:
            raise ValueError('Choose a translation language or reload Lexirise settings.')
        return {'started': runtime.languages.request(game, payload.locale, target, account,
                                                    rebuild=payload.action == 'rebuild')}
    except (ValueError, LexiriseError) as error:
        raise HTTPException(400, str(error)) from None


class AutomaticExportOptions(BaseModel):
    model_config = ConfigDict(extra='forbid')
    action: Literal['save', 'update', 'pause', 'resume', 'retry', 'browse', 'close-picker'] = 'save'
    enabled: bool = False
    destination: str = Field(default='', max_length=2000)
    languages: dict[str, str] = Field(default_factory=dict, max_length=20)


@app.get('/api/setup/games/{game}/automatic-mobile-export')
def automatic_export_status(game: str, request: Request) -> dict:
    setup_access(request)
    if game not in GAME_LOCALES:
        raise HTTPException(404, 'Unsupported game')
    return runtime.automatic_exports.status(game)


@app.post('/api/setup/games/{game}/automatic-mobile-export')
def automatic_export_action(game: str, payload: AutomaticExportOptions, request: Request,
                            x_proxy_transcript: str = Header(default='')) -> dict:
    setup_access(request, x_proxy_transcript, write=True)
    if game not in GAME_LOCALES:
        raise HTTPException(404, 'Unsupported game')
    manager = runtime.automatic_exports
    try:
        if payload.action == 'save':
            return manager.configure(game, payload.enabled, payload.destination, payload.languages)
        if payload.action == 'browse':
            manager.picker.browse(payload.destination or None)
            return manager.status(game)
        if payload.action == 'close-picker':
            manager.picker.close_picker()
            return manager.status(game)
        return manager.action(game, payload.action)
    except (ValueError, OSError):
        raise HTTPException(400, 'Check the export folder and select supported voice and translation languages.') from None


class MobileExportOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    include_audio: bool = True
    destination_folder: str | None = None
    game: str | None = Field(default=None, min_length=1, max_length=24)


@contextmanager
def export_scope(request, game=None):
    accounts = getattr(runtime, 'accounts', None)
    with accounts.lock if accounts else nullcontext():
        if hasattr(runtime.mobile_exports, 'require_scope'):
            try:
                runtime.mobile_exports.require_scope(game, request.headers.get('x-proxy-transcript-export-scope'))
            except ValueError as error:
                raise HTTPException(409, str(error)) from None
        yield


@app.post("/api/setup/games/{game}/mobile-export")
def mobile_export(game: str, payload: MobileExportOptions, request: Request,
                  x_proxy_transcript: str | None = Header(default=None)) -> dict:
    setup_access(request, x_proxy_transcript, write=True)
    if game not in GAMES:
        raise HTTPException(404, "Unsupported game")
    try:
        with export_scope(request, game):
            return {"started": runtime.mobile_exports.start(game, payload.include_audio, payload.destination_folder)}
    except (ValueError, OSError):
        raise HTTPException(400, "Choose a writable private export folder outside game files and source repositories.") from None


@app.post("/api/setup/games/{game}/mobile-export/preview")
def mobile_export_preview(game: str, payload: MobileExportOptions, request: Request,
                          x_proxy_transcript: str | None = Header(default=None)) -> dict:
    setup_access(request, x_proxy_transcript, write=True)
    if game not in GAMES:
        raise HTTPException(404, "Unsupported game")
    try:
        with export_scope(request, game):
            return runtime.mobile_exports.preview(game, payload.include_audio, payload.destination_folder)
    except (ValueError, OSError):
        raise HTTPException(400, "Choose an absolute folder outside game files and source repositories. Refresh game data if its estimate is unavailable.") from None


@app.post("/api/setup/mobile-export/browse")
def mobile_export_browse(payload: MobileExportOptions, request: Request,
                         x_proxy_transcript: str | None = Header(default=None)) -> dict:
    setup_access(request, x_proxy_transcript, write=True)
    try:
        with export_scope(request, payload.game):
            return {'started': runtime.mobile_exports.browse(payload.destination_folder, game=payload.game)
                    if payload.game else runtime.mobile_exports.browse(payload.destination_folder)}
    except (ValueError, OSError):
        raise HTTPException(400, "Could not open the Windows folder picker. Paste a private destination folder instead.") from None


@app.get("/api/setup/mobile-export")
def mobile_export_status(request: Request, game: str | None = None) -> dict:
    setup_access(request)
    if game is not None and game not in GAMES:
        raise HTTPException(404, 'Unsupported game')
    return runtime.mobile_exports.status(game) if game and hasattr(runtime.mobile_exports, 'require_scope') else runtime.mobile_exports.status()


@app.post("/api/setup/mobile-export/browse/cancel")
def mobile_export_browse_cancel(request: Request, payload: MobileExportOptions | None = None,
                                x_proxy_transcript: str | None = Header(default=None)) -> dict:
    setup_access(request, x_proxy_transcript, write=True)
    game = payload.game if payload else None
    try:
        with export_scope(request, game):
            return {'cancelled': runtime.mobile_exports.close_picker(game) if game else runtime.mobile_exports.close_picker()}
    except (OSError, TimeoutExpired):
        raise HTTPException(409, "Windows is still closing the folder browser. Try Close picker again.") from None


@app.post("/api/setup/mobile-export/cancel")
def mobile_export_cancel(request: Request, payload: MobileExportOptions | None = None,
                         x_proxy_transcript: str | None = Header(default=None)) -> dict:
    setup_access(request, x_proxy_transcript, write=True)
    game = payload.game if payload else None
    with export_scope(request, game):
        return {'cancelled': runtime.mobile_exports.cancel(game) if game else runtime.mobile_exports.cancel()}


@app.get("/api/setup/report")
def setup_report(request: Request) -> dict:
    setup_access(request)
    return runtime.installation.report()


@app.post("/api/setup/games/{game}")
def setup_folder(game: str, payload: SetupFolder, request: Request,
                 x_proxy_transcript: str | None = Header(default=None)) -> dict:
    setup_access(request, x_proxy_transcript, write=True)
    if game not in GAMES:
        raise HTTPException(404, "Unsupported game")
    if runtime.installation.status()["native"].get("folders"):
        raise HTTPException(409, "Finish the Windows folder picker first")
    try:
        if payload.use_automatic and payload.path is None:
            clear_install(game)
        elif not payload.use_automatic and payload.path and payload.path.strip():
            value = payload.path.strip()
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
            save_install(game, Path(value))
        else:
            raise ValueError("Choose a folder or explicitly use automatic detection")
    except (ValueError, OSError):
        raise HTTPException(400, "Required game files were not found. Choose the installation folder shown in Setup; the previous folder was kept.") from None
    runtime.refresh_game(game)
    return runtime.installation.status()


@app.post("/api/setup/games/{game}/tools")
def setup_tools(game: str, payload: SetupAction, request: Request,
                x_proxy_transcript: str | None = Header(default=None)) -> dict:
    setup_access(request, x_proxy_transcript, write=True)
    try:
        started = runtime.installation.prepare(game)
    except ValueError as error:
        raise HTTPException(400, str(error)) from None
    return {"started": started}


@app.post("/api/setup/games/{game}/refresh")
def setup_refresh(game: str, payload: SetupAction, request: Request,
                  x_proxy_transcript: str | None = Header(default=None)) -> dict:
    setup_access(request, x_proxy_transcript, write=True)
    if game not in GAMES:
        raise HTTPException(404, "Unsupported game")
    if not runtime.setup_install(game):
        raise HTTPException(400, "Choose an installed game folder first")
    from .game_tools import missing_tools
    if missing_tools(PROJECT_ROOT, game):
        raise HTTPException(409, "Install this game's tools before refreshing")
    return {"started": runtime.refresh_game(game)}


@app.post("/api/setup/native/{kind}")
def setup_native(kind: str, payload: SetupAction, request: Request,
                 x_proxy_transcript: str | None = Header(default=None)) -> dict:
    setup_access(request, x_proxy_transcript, write=True)
    try:
        return {"started": runtime.installation.launch_native(kind)}
    except (ValueError, OSError):
        raise HTTPException(400, "The setup dialog could not open. Re-run Install.cmd on Windows and retry.") from None


@app.post("/api/setup/complete")
def setup_complete(payload: SetupComplete, request: Request,
                   x_proxy_transcript: str | None = Header(default=None)) -> dict:
    setup_access(request, x_proxy_transcript, write=True)
    runtime.installation.complete(payload.auto_start)
    if payload.auto_start:
        runtime.capture.start()
    return {"completed": True}


@app.get("/api/settings", response_model=AppSettings)
def get_settings() -> AppSettings:
    return runtime.settings.get()


@app.patch("/api/settings", response_model=AppSettings)
async def update_settings(settings: AppSettings) -> AppSettings:
    saved = runtime.settings.save(settings)
    await runtime.hub.broadcast({"type": "settings", "settings": saved.model_dump(mode="json")})
    return saved


@app.get("/api/lines", response_model=list[TranscriptLine])
def get_lines(
    limit: int = Query(default=250, ge=1, le=1000),
    before_id: int | None = Query(default=None, ge=1),
    game: str | None = Query(default=None, pattern="^(zzz|pragmata|hito|cyberpunk|wuwa|witcher3|nte|beyond|heavyrain|honkai3|starrail|genshin|endfield|riseofthetombraider|shadowofthetombraider|spyro|mgsvtpp|mgsvgz|deathstranding|plaguetaleinnocence|detroit|portal|portal2|halflife|halflife2|persona5royal|deusexhrdc)$"),
) -> list[TranscriptLine]:
    return [
        presented(runtime.speakers.enrich(line) if line.game == "zzz" else line)
        for line in runtime.transcript.list(limit=limit, before_id=before_id, game=game)
        if line.game == "hito" or ((line.voiced or line.is_comic or line.voice_status == 'unvoiced') and (
            runtime.pragmata.is_capture_text(line.text_id, line.english, line.channel)
            if line.game == "pragmata"
            else runtime.game_indexes[line.game].is_capture_text(line.text_id, line.english, line.channel)
            if line.game in runtime.game_indexes
            else runtime.textmaps.is_capture_text(line.text_id, line.english, line.channel)
        ))
    ]


@app.get("/api/favorites", response_model=list[TranscriptLine])
def get_favorites(
    game: str | None = Query(default=None, pattern="^(zzz|pragmata|hito|cyberpunk|wuwa|witcher3|nte|beyond|heavyrain|honkai3|starrail|genshin|endfield|riseofthetombraider|shadowofthetombraider|spyro|mgsvtpp|mgsvgz|deathstranding|plaguetaleinnocence|detroit|portal|portal2|halflife|halflife2|persona5royal|deusexhrdc)$"),
) -> list[TranscriptLine]:
    return [runtime.speakers.enrich(line) if line.game == "zzz" else line
            for line in runtime.transcript.list_favorites(game=game)]


@app.get("/api/lines/{line_id}/audio")
def get_line_audio(line_id: int) -> FileResponse:
    filename = runtime.transcript.audio_path(line_id)
    if not filename:
        raise HTTPException(status_code=404, detail="This line has no captured voice clip")
    audio_dir = (DATA_DIR / "audio").resolve()
    path = (audio_dir / filename).resolve()
    if path.parent != audio_dir or not path.is_file():
        raise HTTPException(status_code=404, detail="Audio file is unavailable")
    media_type = "audio/mpeg" if path.suffix.casefold() == ".mp3" else "audio/wav"
    return FileResponse(path, media_type=media_type, headers={"Cache-Control": "no-store"})


@app.patch("/api/lines/{line_id}/favorite", response_model=TranscriptLine)
async def update_line_favorite(line_id: int, payload: FavoriteUpdate) -> TranscriptLine:
    line = runtime.transcript.set_favorite(line_id, payload.favorite)
    if line is None:
        raise HTTPException(status_code=404, detail="Transcript line not found")
    await runtime.on_line(line)
    return line


@app.get("/api/lexirise")
def lexirise_status(language: str = 'zh') -> dict:
    context = read_context()
    result = integration_status(language)
    check_read_context(context)
    return {**result, 'context': context}


def integration_status(language: str = 'zh', *, refresh_settings=True) -> dict:
    account = runtime.accounts.status()['active'] if hasattr(runtime, 'accounts') else 'legacy'
    try:
        session = runtime.lexirise.pin(language)
    except LexiriseError:
        return {'configured': False, 'sent': {}, 'decks': {}, 'account': account}
    status = session.status()
    if refresh_settings and status["configured"] and not hasattr(session, "_settings_scope"):
        try:
            account_settings(session)
        except LexiriseError:
            pass  # Reading/panel errors remain actionable without blocking capture.
    sources = {'zh'}
    if hasattr(runtime, 'languages'):
        account = runtime.accounts.status()['active']
        sources.update(study_language(locale) for game in GAME_LOCALES
                       if (locale := runtime.languages.selected(game, account)))
    by_language = {source: runtime.lexirise.pin(source).status() for source in sources if source in STUDY_LANGUAGES}
    status['sent'] = {ref: deck for value in by_language.values() for ref, deck in value['sent'].items()}
    status['by_language'] = by_language
    status['account'] = account
    return status


@app.get('/api/lexirise/accounts')
def lexirise_accounts(request: Request) -> dict:
    setup_access(request)
    try:
        return runtime.accounts.status()
    except LexiriseError as error:
        raise HTTPException(503, str(error)) from None


class AccountSelection(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str = Field(min_length=1, max_length=80)


@app.post('/api/lexirise/accounts/select')
async def lexirise_select_account(payload: AccountSelection, request: Request,
                                  x_proxy_transcript: str = Header(default='')) -> dict:
    setup_access(request)
    if x_proxy_transcript != 'lexirise':
        raise HTTPException(403, 'Use the companion account selector.')
    try:
        result = runtime.accounts.select(payload.id)
        if hasattr(runtime, 'mobile_exports') and hasattr(runtime.mobile_exports, 'cancel_all'):
            runtime.mobile_exports.cancel_all()
        if hasattr(runtime, 'capture'):
            runtime.capture._scan_epoch += 1
        await runtime.hub.broadcast({'type': 'account_changed', 'account': result['active']})
        return result
    except LexiriseError as error:
        raise HTTPException(400, str(error)) from None


def line_reader(line):
    return runtime.reading_for(line) if hasattr(runtime, 'reading_for') else runtime.reading


def presented(line):
    return runtime.present_line(line) if hasattr(runtime, 'present_line') else line


@app.get("/api/lexirise/decks")
def lexirise_available_decks(language: str = 'zh') -> dict:
    try:
        return {"decks":runtime.lexirise.pin(language).available_decks() if hasattr(runtime.lexirise, "pin") else runtime.lexirise.available_decks()}
    except LexiriseError as error:
        raise HTTPException(503,str(error)) from None


@app.post("/api/lexirise/decks")
def lexirise_configure_deck(payload:dict,x_proxy_transcript:str=Header(default="")) -> dict:
    if x_proxy_transcript != "lexirise":
        raise HTTPException(403,"Use the companion's destination controls.")
    if set(payload)-{"game","deck_id","create","language"} or type(payload.get("game")) is not str or (payload.get("create") is not True and type(payload.get("deck_id")) is not int):
        raise HTTPException(422,"Select a destination or explicitly create one.")
    if payload.get("create") is True and "deck_id" in payload:
        raise HTTPException(422,"Choose selection or creation, not both.")
    try:
        session = runtime.lexirise.pin(payload.get("language", "zh")) if hasattr(runtime.lexirise, "pin") else runtime.lexirise
        session.configure_game_deck(payload["game"],None if payload.get("create") is True else payload["deck_id"])
        return session.status()
    except LexiriseError as error:
        raise HTTPException(503,str(error)) from None


@app.get("/api/lexirise/settings")
def lexirise_get_settings() -> dict:
    try:
        return account_settings(runtime.lexirise.pin())
    except LexiriseError as error:
        raise HTTPException(status_code=502, detail=str(error)) from None


@app.patch("/api/lexirise/settings")
def lexirise_patch_settings(payload: dict, x_proxy_transcript: str = Header(default="")) -> dict:
    if x_proxy_transcript != "lexirise":
        raise HTTPException(status_code=403, detail="Explicit Lexirise action required.")
    try:
        return account_settings(runtime.lexirise.pin(), payload)
    except LexiriseError as error:
        raise HTTPException(status_code=400, detail=str(error)) from None


@app.get("/api/lines/{line_id}/reading")
def line_reading(line_id: int) -> dict:
    line = runtime.transcript.get(line_id)
    if line is None:
        raise HTTPException(404, "Transcript line not found")
    try:
        return line_reader(line).analyze(line.source_text)
    except LexiriseError as error:
        raise HTTPException(503, str(error)) from None


@app.get("/api/lines/{line_id}/reading/lookup")
def line_word_lookup(line_id: int, start: int) -> dict:
    line = runtime.transcript.get(line_id)
    if line is None:
        raise HTTPException(404, "Transcript line not found")
    try:
        result = line_reader(line).lookup(line.source_text, start)
    except LexiriseError as error:
        raise HTTPException(503, str(error)) from None
    if result is None:
        raise HTTPException(404, "Word not found in this line")
    return result


@app.post("/api/lines/{line_id}/reading/grammar")
def line_grammar_known(line_id: int, payload: GrammarKnownUpdate,
                       x_proxy_transcript: str = Header(default="")) -> dict:
    if x_proxy_transcript != "lexirise":
        raise HTTPException(403, "Use the companion's grammar controls.")
    line = runtime.transcript.get(line_id)
    if line is None:
        raise HTTPException(404, "Transcript line not found")
    try:
        result = line_reader(line).set_grammar_known(line.source_text, payload.slug, payload.known)
    except LexiriseError as error:
        raise HTTPException(503, str(error)) from None
    if result is None:
        raise HTTPException(404, "Grammar rule not found in this line")
    return result


@app.get("/api/lines/{line_id}/reading/context")
def line_word_context(line_id: int, start: int = Query(ge=0)) -> dict:
    line = runtime.transcript.get(line_id)
    if line is None:
        raise HTTPException(404, "Transcript line not found")
    try:
        result = line_reader(line).context(line.source_text, start)
    except LexiriseError as error:
        raise HTTPException(503, str(error)) from None
    if result is None:
        raise HTTPException(404, "Word not found in this line")
    return result


@app.get("/api/lines/{line_id}/reading/notes")
def line_word_notes(line_id: int, start: int = Query(ge=0)) -> dict:
    line = runtime.transcript.get(line_id)
    if line is None:
        raise HTTPException(404, "Transcript line not found")
    try:
        result = line_reader(line).notes(line.source_text, start)
    except LexiriseError as error:
        raise HTTPException(503, str(error)) from None
    if result is None:
        raise HTTPException(404, "Word not found in this line")
    return result


@app.post("/api/lines/{line_id}/reading/context")
def ask_line_word_context(line_id: int, payload: WordContextQuestion,
                          x_proxy_transcript: str = Header(default="")) -> dict:
    if x_proxy_transcript != "lexirise":
        raise HTTPException(403, "Use the companion's word controls.")
    question = payload.question.strip()
    if not question:
        raise HTTPException(422, "Question cannot be blank")
    line = runtime.transcript.get(line_id)
    if line is None:
        raise HTTPException(404, "Transcript line not found")
    try:
        result = line_reader(line).context(line.source_text, payload.start, question)
    except LexiriseError as error:
        raise HTTPException(503, str(error)) from None
    if result is None:
        raise HTTPException(404, "Word not found in this line")
    return result


@app.get("/api/lines/{line_id}/reading/examples")
def line_word_examples(line_id: int, start: int = Query(ge=0)) -> dict:
    line = runtime.transcript.get(line_id)
    if line is None:
        raise HTTPException(404, "Transcript line not found")
    try:
        result = line_reader(line).examples(line.source_text, start)
    except LexiriseError as error:
        raise HTTPException(503, str(error)) from None
    if result is None:
        raise HTTPException(404, "Word not found in this line")
    return result


@app.get("/api/lines/{line_id}/reading/similar")
def line_word_similar(line_id: int, start: int = Query(ge=0)) -> dict:
    line = runtime.transcript.get(line_id)
    if line is None:
        raise HTTPException(404, "Transcript line not found")
    try:
        result = line_reader(line).similar(line.source_text, start)
    except LexiriseError as error:
        raise HTTPException(503, str(error)) from None
    if result is None:
        raise HTTPException(404, "Word not found in this line")
    return result


@app.post("/api/lines/{line_id}/reading/examples/{example_index}/save")
def save_line_word_example(line_id: int, example_index: int, start: int = Query(ge=0),
                           x_proxy_transcript: str = Header(default="")) -> dict:
    if x_proxy_transcript != "lexirise":
        raise HTTPException(403, "Use the companion's example bookmark.")
    line = runtime.transcript.get(line_id)
    if line is None:
        raise HTTPException(404, "Transcript line not found")
    try:
        result = line_reader(line).save_example(line.source_text, start, example_index)
    except LexiriseError as error:
        raise HTTPException(503, str(error)) from None
    if result is None:
        raise HTTPException(404, "Example not found for this word")
    return result


@app.get("/api/lines/{line_id}/reading/characters")
def line_word_characters(line_id: int, start: int = Query(ge=0)) -> dict:
    line = runtime.transcript.get(line_id)
    if line is None:
        raise HTTPException(404, "Transcript line not found")
    try:
        result = line_reader(line).characters(line.source_text, start)
    except LexiriseError as error:
        raise HTTPException(503, str(error)) from None
    if result is None:
        raise HTTPException(404, "Word not found in this line")
    return result


@app.post("/api/lines/{line_id}/reading/proficiency")
def line_word_proficiency(line_id: int, payload: WordProficiencyUpdate,
                          x_proxy_transcript: str = Header(default="")) -> dict:
    if x_proxy_transcript != "lexirise":
        raise HTTPException(403, "Use the companion's word controls.")
    line = runtime.transcript.get(line_id)
    if line is None:
        raise HTTPException(404, "Transcript line not found")
    try:
        result = line_reader(line).set_proficiency(line.source_text, payload.start, payload.proficiency)
    except LexiriseError as error:
        raise HTTPException(503, str(error)) from None
    if result is None:
        raise HTTPException(404, "Word not found in this line")
    return result


@app.post("/api/lines/{line_id}/lexirise")
def send_line_to_lexirise(line_id: int, x_proxy_transcript: str = Header(default="")) -> dict:
    # Custom header forces cross-origin browsers through the existing allowlist.
    if x_proxy_transcript != "lexirise":
        raise HTTPException(403, "Use the companion's Lexirise button.")
    line = runtime.transcript.get(line_id)
    if line is None:
        raise HTTPException(404, "This line is no longer in local history.")
    if not line.voiced and line.voice_status != 'unvoiced':
        raise HTTPException(409, "This line needs a verified original voice or confirmed unvoiced dialogue before export.")
    if line.game == "zzz":
        line = runtime.speakers.enrich(line)
    root = (DATA_DIR / "audio").resolve()
    path = (root / (runtime.transcript.audio_path(line_id) or "missing")).resolve()
    if path.parent != root:
        raise HTTPException(404, "Voice file unavailable.")
    try:
        line = presented(line)
        result = runtime.lexirise.pin(line.source_language).send(ref=f"line:{line_id}", game=line.game, chinese=line.source_text,
            english=line.translation_text, speaker=" / ".join(filter(None, [line.speaker_english, line.speaker_chinese])),
            audio=None if line.voice_status == 'unvoiced' else path, audio_source=line.audio_source)
        return {**result, 'audio_included': line.voice_status != 'unvoiced'}
    except LexiriseError as error:
        raise HTTPException(409, str(error)) from None
    except OSError:
        raise HTTPException(409, "The local voice clip became unavailable. Try a saved favorite.") from None


@app.post("/api/capture/start")
async def start_capture() -> dict[str, object]:
    started = runtime.capture.start()
    return {"started": started, "capture": runtime.capture.snapshot().model_dump(mode="json")}


@app.post("/api/capture/stop")
async def stop_capture() -> dict[str, object]:
    stopped = await runtime.capture.stop()
    return {"stopped": stopped, "capture": runtime.capture.snapshot().model_dump(mode="json")}


@app.get("/api/capture/preview.jpg")
async def capture_preview(
    left: float | None = Query(default=None, ge=0, le=1),
    top: float | None = Query(default=None, ge=0, le=1),
    width: float | None = Query(default=None, gt=0, le=1),
    height: float | None = Query(default=None, gt=0, le=1),
    picture_area: Literal["window", "16:9"] | None = Query(default=None),
) -> Response:
    values = (left, top, width, height)
    if all(value is not None for value in values):
        try:
            region = CaptureRegion(left=left, top=top, width=width, height=height)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        preview = await asyncio.to_thread(runtime.capture.preview_for_region, region, picture_area)
    else:
        preview = await asyncio.to_thread(runtime.capture.preview_bytes)
    if not preview:
        raise HTTPException(status_code=404, detail="No capture preview is available yet")
    return Response(
        content=preview,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-store, max-age=0"},
    )


@app.post("/api/textmaps/update")
def update_textmaps() -> dict[str, object]:
    started = runtime.refresh_game("zzz")
    return {"started": started, "textmaps": runtime.textmaps.status()}


@app.post("/api/games/{game}/update")
def update_local_game(game: str) -> dict:
    updater = runtime.game_updaters.get(game)
    if updater is None:
        raise HTTPException(404, "Unsupported game-file index")
    return {"started": runtime.refresh_game(game), "updates": updater.status()}


@app.post("/api/hito/update")
def update_hito_text() -> dict[str, object]:
    raise HTTPException(status_code=410, detail="Hito's World support is disabled. Existing history is preserved.")


@app.post("/api/updates/check")
def check_updates() -> dict[str, object]:
    prepared = runtime.languages.entries()
    runtime.languages.refresh_prepared()
    return {"started": bool(prepared), "updates": runtime.update_status()}


@app.post("/api/ingest", response_model=TranscriptLine)
async def manual_ingest(payload: ManualIngest) -> TranscriptLine:
    if not runtime.textmaps.ready:
        raise HTTPException(status_code=409, detail="TextMaps are not ready")
    match = await asyncio.to_thread(
        runtime.textmaps.match_text,
        payload.text,
        runtime.settings.get().fuzzy_threshold,
    )
    if match is None:
        raise HTTPException(status_code=404, detail="No bilingual TextMap match found")
    line = runtime.transcript.add(match, runtime.capture.session_id)
    await runtime.on_line(line)
    return line


@app.get("/api/windows")
def windows() -> list[dict[str, object]]:
    return [
        {
            "handle": window.handle,
            "title": window.title,
            "process_name": window.process_name,
            "bounds": window.bounds,
        }
        for window in list_visible_windows()
    ]


@app.get("/api/ndi/sources")
async def ndi_sources(request: Request) -> dict:
    # Discovery only lists sender names; it never opens a video receiver.
    setup_access(request)
    try:
        sources = await asyncio.to_thread(list_ndi_sources)
    except NdiUnavailable as error:
        return {"available": False, "message": str(error), "sources": [], "link": NDI_LINK}
    return {"available": True, "message": None, "sources": sources, "link": NDI_LINK}


@app.websocket("/api/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await runtime.hub.connect(websocket)
    try:
        snapshot = await asyncio.to_thread(runtime.status)
        event = {"type": "snapshot", "snapshot": snapshot}
        if 'context' in snapshot:
            event['context'] = snapshot['context']
        await websocket.send_json(event)
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await runtime.hub.disconnect(websocket)
    except Exception:
        await runtime.hub.disconnect(websocket)


class ToolkitUpdatePreferences(BaseModel):
    enabled: bool = Field(strict=True)


@app.get('/api/toolkit-update')
def toolkit_update_status():
    return runtime.toolkit_updater.status()


@app.post('/api/toolkit-update/check')
def toolkit_update_check(x_proxy_transcript: str = Header(default='')):
    if x_proxy_transcript != 'setup':
        raise HTTPException(403, 'Use Setup on this PC to update the toolkit.')
    if runtime.standby:
        raise HTTPException(409, 'The replacement is still preparing.')
    return {'started': runtime.toolkit_updater.request()}


@app.post('/api/toolkit-update/preferences')
def toolkit_update_preferences(payload: ToolkitUpdatePreferences, x_proxy_transcript: str = Header(default='')):
    if x_proxy_transcript != 'setup':
        raise HTTPException(403, 'Use Setup on this PC to change toolkit updates.')
    runtime.toolkit_updater.configure(payload.enabled)
    return runtime.toolkit_updater.status()
