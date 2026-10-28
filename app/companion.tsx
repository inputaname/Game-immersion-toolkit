'use client';
import {useInterfaceLanguage, useInterfaceTranslation} from '../lib/interface-language';
import {languageName} from '../public/mobile-capture/interface-language.mjs';

import { SettingsPanel, ReadingOptionsDialog, restoreLocalSettings, type LocalSettings, isStudyLanguage } from '@firebird55/lexirise-components';
import { settingsAdapter } from './lexirise-settings';
import {StateEvents, StatePoll, type StateContext} from './state-sync';
import {AccountSwitcher} from './account-switcher';
import { GameDeckSettings } from './game-deck-settings';
import { ToolkitSetup } from './toolkit-setup';
import {LanguageSetup} from './language-setup';
import {GamePicker, useTargetLanguage} from './game-picker';
import {GAME_NAMES, captureRegionKey, type GameId} from '../lib/games';
import {NdiSourceSettings, type CaptureSourceSettings} from './ndi-source-settings';
import { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Activity,
  Crosshair,
  Database,
  MessageSquareText,
  Pause,
  Play,
  Radio,
  RefreshCw,
  ScanLine,
  Settings2,
  Star,
  Volume2,
  Gamepad2,
  Send,
  Check,
  Loader2,
} from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { ReadingText, DEFAULT_READING_OPTIONS,
  restoreReadingOptions, type ReadingOptions } from '@/app/reading-text';
import { shouldHideTranslation, restoreTranslationLimit, type ReadingSummary, type TranslationLimit } from '@/app/translation-visibility';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';

const API_URL = 'http://127.0.0.1:8766';
const WS_URL = 'ws://127.0.0.1:8766/api/ws';
const HISTORY_LIMIT = 50;
const HISTORY_PAGE_SIZE = 10;

type CaptureRegion = { left: number; top: number; width: number; height: number };
type Settings = Record<`${Exclude<GameId, 'zzz' | 'pragmata'>}_region`, CaptureRegion> & {
  preferred_game: 'auto' | GameId;
  process_names: string[];
  window_title_contains: string[];
  region: CaptureRegion;
  tip_region: CaptureRegion;
  cinematic_region: CaptureRegion;
  hito_region: CaptureRegion;
  hito_tip_region: CaptureRegion;
  hito_auto_regions: boolean;
  cyberpunk_region: CaptureRegion;
  cyberpunk_tip_region: CaptureRegion;
  cyberpunk_capture_chatter: boolean;
  zzz_proxy_voice: 'unconfigured' | 'female' | 'male';
  cyberpunk_v_voice: 'unconfigured' | 'female' | 'male';
  wuwa_region: CaptureRegion;
  wuwa_tip_region: CaptureRegion;
  wuwa_capture_chatter: boolean;
  wuwa_cinematic_region: CaptureRegion;
  wuwa_capture_cinematic: boolean;
  wuwa_rover_voice: 'unconfigured' | 'female' | 'male';
  beyond_region: CaptureRegion;
  heavyrain_region: CaptureRegion;
  riseofthetombraider_region: CaptureRegion;
  shadowofthetombraider_region: CaptureRegion;
  starrail_region: CaptureRegion;
  starrail_player_voice: 'unconfigured' | 'female' | 'male';
  genshin_region: CaptureRegion;
  genshin_player_voice: 'unconfigured' | 'female' | 'male';
  endfield_region: CaptureRegion;
  endfield_player_voice: 'unconfigured' | 'female' | 'male';
  nte_region: CaptureRegion;
  nte_picture_area: 'window' | '16:9';
  nte_player_voice: 'unconfigured' | 'female' | 'male';
  honkai3_region: CaptureRegion;
  honkai3_picture_area: 'window' | '16:9';
  witcher3_region: CaptureRegion;
  witcher3_tip_region: CaptureRegion;
  witcher3_capture_chatter: boolean;
  scan_interval_ms: number;
  stable_frames: number;
  fuzzy_threshold: number;
  auto_start: boolean;
  save_unmatched: boolean;
  capture_unvoiced: boolean;
} & CaptureSourceSettings;
type CaptureStatus = {
  visible_text_ids: string[];
  running: boolean;
  phase: string;
  message: string;
  active_game: 'zzz' | 'pragmata' | 'hito' | 'cyberpunk' | 'wuwa' | 'witcher3' | 'nte' | 'beyond' | 'heavyrain' | 'starrail' | 'genshin' | 'endfield' | 'riseofthetombraider' | 'shadowofthetombraider' | null;
  window_title: string | null;
  window_bounds: [number, number, number, number] | null;
  crop_bounds: [number, number, number, number] | null;
  tip_crop_bounds: [number, number, number, number] | null;
  cinematic_crop_bounds: [number, number, number, number] | null;
  last_ocr: string;
  last_ocr_confidence: number | null;
  last_tip_ocr: string;
  last_tip_ocr_confidence: number | null;
  last_tip_match_score: number | null;
  last_cinematic_ocr: string;
  last_cinematic_ocr_confidence: number | null;
  last_cinematic_match_score: number | null;
  last_match_score: number | null;
  last_scan_at: string | null;
  last_error: string | null;
};
type TextMapStatus = { ready: boolean; state: string; message: string; entry_count: number };
type TranscriptLine = {
  id: number;
  created_at: string;
  session_id: string;
  game: GameId;
  source_ocr: string;
  source_language?:string; source_locale?:string; source_text?:string; translation_text?:string; translation_locale?:string; audio_locale?:string;
  english: string;
  chinese: string;
  text_id: string;
  score: number;
  match_kind: string;
  ambiguous: boolean;
  channel: 'dialogue' | 'gameplay' | 'tip' | 'cinematic';
  voiced: boolean;
  voice_status?: 'voiced' | 'unvoiced' | 'unavailable' | 'unknown';
  dialogue_kind?: string | null;
  has_audio: boolean;
  audio_pending?: boolean;
  audio_source?: 'original' | 'recording';
  speaker_english?: string | null;
  speaker_chinese?: string | null;
  favorite: boolean;
};
function isComicLine(line: TranscriptLine) {
  return line.game === 'zzz' && line.channel === 'cinematic' && /^Comic_[0-9a-f]{32}(?::[MF])?$/i.test(line.text_id);
}
function voicePlaybackLabel(line: TranscriptLine) {
  return line.dialogue_kind?.endsWith('_full_track') ? 'Original audio · full track' : 'Original voice';
}
function isReadableLine(line: TranscriptLine) {
  return line.voiced || line.voice_status === 'unvoiced' || line.game === 'hito' || isComicLine(line);
}
type UpdateStatus = {
  state: string;
  message: string;
  progress: number | null;
  elapsed_seconds?: number;
  stage_seconds?: number;
  queued?: number;
  items?: {game: string; locale: string; state: string; message: string; retry_after?: string}[];
  automatic: boolean;
  last_checked: string | null;
  last_error: string | null;
};
type StatusPayload = {
  capture: CaptureStatus;
  textmaps: TextMapStatus;
  selected_languages?:Partial<Record<GameId,{source_locale:string;source_language:string}>>;
  game_textmaps?: Record<GameId, TextMapStatus>;
  audio: { ready: boolean; message: string };
  updates?: UpdateStatus;
  settings: Settings;
  session: { id: string; line_count: number; total_line_count: number };
};
type CompanionSnapshot = {context:StateContext; status:StatusPayload; lines:TranscriptLine[]; lexirise:LexiriseStatus};
type TranscriptTab = 'history' | 'favorites';
function newestFirst(left: TranscriptLine, right: TranscriptLine) {
  return Date.parse(right.created_at) - Date.parse(left.created_at) || right.id - left.id;
}
type LexiriseStatus = {account?:string; by_language?:Record<string,{decks?:Record<string,{id:number;title:string}>}>; configured: boolean; sent: Record<string, number>; decks?:Record<string,{id:number;title:string}> };
type ReadingMode = 'migaku' | 'lexirise';
const LexiriseButton = memo(function LexiriseButton({ sent, busy, disabled, game, onClick, compact = false }: {
  sent: boolean; busy: boolean; disabled: boolean; game: GameId; onClick: () => void; compact?: boolean;
}) {
  const uiText=useInterfaceTranslation();
  if (game === 'hito') return null;
  const title = sent ? 'Already sent to Lexirise' : `Save sentence to Lexirise · ${GAME_NAMES[game]}`;
  return <button type="button" className={`lexirise-send ${sent ? 'is-sent' : ''}`} translate="no"
    disabled={disabled || busy || sent} onClick={onClick} title={title} aria-label={title} aria-busy={busy}>
    {busy ? <Loader2 size={16} className="animate-spin" /> : sent ? <Check size={16} /> : <Send size={16} />}
    {!compact && <span>{busy ? uiText("Sending…") : sent ? uiText("Sent to Lexirise") : uiText("Lexirise")}</span>}
  </button>;
});

const timeFormatter = new Intl.DateTimeFormat(undefined, {
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
  hour12: false,
});

function formatTime(value: string) {
  return timeFormatter.format(new Date(value));
}

function sameStringArray(left: string[], right: string[]) {
  return left.length === right.length && left.every((value, index) => value === right[index]);
}

function sameBounds(
  left: [number, number, number, number] | null,
  right: [number, number, number, number] | null,
) {
  if (left === right) return true;
  return !!left && !!right && left.every((value, index) => value === right[index]);
}

function captureStatusEqual(left: CaptureStatus, right: CaptureStatus, includeDiagnostics: boolean) {
  const visibleStateMatches = left.running === right.running
    && left.phase === right.phase
    && left.message === right.message
    && left.active_game === right.active_game
    && left.last_error === right.last_error
    && sameStringArray(left.visible_text_ids, right.visible_text_ids);
  if (!visibleStateMatches || !includeDiagnostics) return visibleStateMatches;

  return left.window_title === right.window_title
    && sameBounds(left.window_bounds, right.window_bounds)
    && sameBounds(left.crop_bounds, right.crop_bounds)
    && sameBounds(left.tip_crop_bounds, right.tip_crop_bounds)
    && sameBounds(left.cinematic_crop_bounds, right.cinematic_crop_bounds)
    && left.last_ocr === right.last_ocr
    && left.last_ocr_confidence === right.last_ocr_confidence
    && left.last_tip_ocr === right.last_tip_ocr
    && left.last_tip_ocr_confidence === right.last_tip_ocr_confidence
    && left.last_tip_match_score === right.last_tip_match_score
    && left.last_cinematic_ocr === right.last_cinematic_ocr
    && left.last_cinematic_ocr_confidence === right.last_cinematic_ocr_confidence
    && left.last_cinematic_match_score === right.last_cinematic_match_score
    && left.last_match_score === right.last_match_score;
}

function transcriptLineEqual(left: TranscriptLine, right: TranscriptLine) {
  const leftEntries = Object.entries(left);
  const rightEntries = Object.entries(right);
  return leftEntries.length === rightEntries.length
    && leftEntries.every(([key, value]) => Object.is(value, right[key as keyof TranscriptLine]));
}

function mergeTranscriptSnapshot(current: TranscriptLine[], snapshot: TranscriptLine[]) {
  const currentById = new Map(current.map((line) => [line.id, line]));
  // The complete snapshot has already replayed newer live events. Missing IDs
  // are authoritative (including deletions missed while disconnected); retaining
  // the previous newest row here would resurrect an empty game indefinitely.
  return snapshot.map((line) => {
    const existing = currentById.get(line.id);
    return existing && transcriptLineEqual(existing, line) ? existing : line;
  }).sort(newestFirst);
}

function phaseLabel(phase: string) {
  const labels: Record<string, string> = {
    starting: 'Starting',
    waiting_for_game: 'Waiting for game',
    loading_textmaps: 'Loading TextMaps',
    listening: 'Reading subtitles',
    unmatched: 'Reading subtitle',
    excluded_screen: 'History UI ignored',
    matched: 'Matched',
    error: 'Retrying',
    stopped: 'Paused',
    unvoiced_disabled: 'Enable text-message capture',
  };
  return labels[phase] ?? phase.replaceAll('_', ' ');
}

export function Companion() {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  if (!mounted) return <main className="companion-shell" aria-busy="true" />;
  return <CompanionClient />;
}

const StableText = memo(function StableText({ text, className, lang }: { text: string; className?: string; lang?: string }) {
  const element = useRef<HTMLParagraphElement>(null);
  useEffect(() => {
    if (element.current && element.current.textContent !== text) {
      // Migaku rewrites target-language text into its own spans. React must not
      // reconcile those injected children or it can crash on the next update.
      element.current.replaceChildren(document.createTextNode(text));
    }
  }, [text]);
  return <p ref={element} className={className} lang={lang} />;
});

const StableInline = memo(function StableInline({ text, className }: { text: string; className?: string }) {
  const element = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    if (element.current && element.current.textContent !== text) {
      element.current.replaceChildren(document.createTextNode(text));
    }
  }, [text]);
  return <span ref={element} className={className} />;
});

const MigakuCurrentText = memo(function MigakuCurrentText({ text, lineId, locale }: { text: string; lineId: number; locale: string }) {
  const host = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!host.current) return;
    const paragraph = document.createElement('p');
    paragraph.className = 'current-chinese';
    paragraph.lang = locale;
    paragraph.dataset.migakuLineId = String(lineId);
    paragraph.textContent = text;
    // A fresh node is important: Migaku processes newly inserted transcript
    // nodes, but does not reliably revisit text replaced inside an old node.
    host.current.replaceChildren(paragraph);
  }, [lineId, text, locale]);
  return <div className="current-chinese-host" ref={host} />;
});

function EnglishTranslation({ line, summary, limit, current = false }: {
  line: TranscriptLine; summary: ReadingSummary | null; limit: TranslationLimit; current?: boolean;
}) {
 const uiText=useInterfaceTranslation();
  const [revealed, setRevealed] = useState<string | null>(null);
  const key = JSON.stringify([line.id, line.chinese, line.english, limit]);
  const count = summary?.id === line.id && summary.text === (line.source_text??line.chinese) ? summary.unknownWords : null;
  const hidden = shouldHideTranslation(limit, count) && revealed !== key;
  if (line.translation_text === '') return <p className="translation-unavailable">{uiText("Official")} {line.translation_locale} {uiText("translation unavailable. Prepare its table in Setup → Languages.")}</p>;
  if (!hidden) return <StableText className={current ? "current-english" : undefined} lang={line.translation_locale ?? 'en'} text={line.translation_text??line.english} />;
  return <button type="button" className={`english-reveal ${current ? 'current-english-reveal' : ''}`}
    onClick={() => setRevealed(key)} aria-label={uiText("Show translation")}>
    <span>{uiText("Translation hidden · Tap to reveal")}</span>
    <small>{count} {uiText("unknown")} {count === 1 ? uiText("word") : uiText("words")}</small>
  </button>;
}

const TranscriptRow = memo(function TranscriptRow({
  line,
  readingMode,
  readingOptions,
  canUseLexirise,
  sendingRef,
  sentToLexirise,
  onPlay,
  onToggleFavorite,
  onSendToLexirise,
}: {
  line: TranscriptLine;
  readingMode: ReadingMode;
  readingOptions: ReadingOptions;
  canUseLexirise: boolean;
  sendingRef: string | null;
  sentToLexirise: boolean;
  onPlay: (line: TranscriptLine) => void;
  onToggleFavorite: (line: TranscriptLine) => void;
  onSendToLexirise: (kind: 'line', id: number | string) => void;
}) {
  const uiText=useInterfaceTranslation();
  const [readingSummary, setReadingSummary] = useState<ReadingSummary | null>(null);
  const ref = `line:${line.id}`;
  return <article className="transcript-line">
    <div className="line-time">
      <time dateTime={line.created_at}>{formatTime(line.created_at)}</time>
      <small className={line.channel !== 'dialogue' ? "is-tip" : ''}>{line.channel === 'tip' ? line.game === 'hito' ? uiText("TOP BOX") : uiText("TOP-RIGHT") : line.channel === 'cinematic' ? uiText("CINEMATIC") : line.channel === 'gameplay' ? uiText("GAMEPLAY") : uiText("DIALOGUE")}</small>
    </div>
    <div className="line-language">
      {line.speaker_english && <StableInline className="line-speaker" text={line.speaker_english} />}
      <EnglishTranslation line={line} summary={readingSummary} limit={readingMode === 'lexirise' ? readingOptions.hideEnglishAt : "off"} />
    </div>
    <div className="line-language">
      {line.speaker_chinese && <StableInline className="line-speaker speaker-chinese" text={line.speaker_chinese} />}
      {readingMode === 'lexirise' ? <ReadingText id={line.id} text={line.source_text??line.chinese} sourceLanguage={line.source_language??'zh'} sentenceTranslation={line.translation_text??line.english} options={readingOptions} onSummary={setReadingSummary} /> : <StableText lang={line.source_locale ?? line.source_language ?? 'zh-Hans'} text={line.source_text??line.chinese} />}
    </div>
    <div className="line-meta">
      <span className={line.score < 90 ? "is-low-score" : ''}>{Math.round(line.score)}%</span>
      <div className="line-actions">
        <button type="button" onClick={() => onPlay(line)} disabled={!line.has_audio} aria-label={`${voicePlaybackLabel(line)}: ${line.english}`} title={voicePlaybackLabel(line)}><Volume2 size={16} /></button>
        <button type="button" className={line.favorite ? "is-favorite" : ''} onClick={() => onToggleFavorite(line)} aria-label={line.favorite ? uiText("Remove from favorites") : uiText("Favorite line")} title={line.favorite ? uiText("Remove favorite") : uiText("Keep forever")}><Star size={16} fill={line.favorite ? "currentColor" : "none"} /></button>
        <LexiriseButton
          sent={sentToLexirise}
          busy={sendingRef === ref}
          disabled={!canUseLexirise || !(line.has_audio || line.voice_status === 'unvoiced') || (sendingRef !== null && sendingRef !== ref)}
          game={line.game}
          onClick={() => onSendToLexirise('line', line.id)}
          compact
        />
      </div>
    </div>
  </article>;
});

function CompanionClient() {
 const {t: uiText, locale: interfaceLocale}=useInterfaceLanguage();
  const [status, setStatus] = useState<StatusPayload | null>(null);
  const [lines, setLines] = useState<TranscriptLine[]>([]);
  const [online, setOnline] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const settingsOpenRef = useRef(false);
  const [draftSettings, setDraftSettings] = useState<Settings | null>(null);
  const [previewTick, setPreviewTick] = useState(0);
  const [setupChannel, setSetupChannel] = useState<'dialogue' | 'tip' | 'cinematic'>('dialogue');
  const [saving, setSaving] = useState(false);
  const [refreshingMaps, setRefreshingMaps] = useState(false);
  const [snapshotLoaded, setSnapshotLoaded] = useState(false);
  const [transcriptTab, setTranscriptTab] = useState<TranscriptTab>('history');
  const transcriptTabRef = useRef<TranscriptTab>('history');
  const [historyPage, setHistoryPage] = useState(0);
  const changeTranscriptTab = useCallback((tab: TranscriptTab, resetHistory = false) => {
    if (resetHistory || transcriptTabRef.current !== tab) setHistoryPage(0);
    transcriptTabRef.current = tab;
    setTranscriptTab(tab);
  }, []);
  const [selectedGame, setSelectedGame] = useState<GameId>('zzz');
  const archivedHistory = selectedGame === 'hito';
  const [accountLanguage,setAccountLanguage]=useState('zh');
  const lastActiveGame = useRef<GameId | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pollOwner = useRef<StatePoll<CompanionSnapshot> | null>(null);
  const knownLineIds = useRef(new Set<number>());
  const historyList = useRef<HTMLDivElement>(null);
  const playback = useRef<HTMLAudioElement | null>(null);
  const [playbackRate, setPlaybackRate] = useState(1);
  const [lexirise, setLexirise] = useState<LexiriseStatus>({ configured: false, sent: {} });
  // A generation distinguishes A → B → A from an outstanding request for A.
  const accountScope = useRef({ account: 'legacy', generation: 0, ready: false });
  const [readingMode, setReadingMode] = useState<ReadingMode>('migaku');
  const gamePicker = useTargetLanguage(readingMode, lexirise.account, lexirise.configured);
  const [readingOptions, setReadingOptions] = useState<LocalSettings>(restoreLocalSettings(DEFAULT_READING_OPTIONS));
  const [currentReadingSummary, setCurrentReadingSummary] = useState<ReadingSummary | null>(null);
  const [readerSettingsOpen, setReaderSettingsOpen] = useState<{language: import('@firebird55/lexirise-components').StudyLanguage; account: string} | null>(null);
  const [accountSettingsOpen, setAccountSettingsOpen] = useState(false);
  const [accountSection, setAccountSection] = useState<'connection'|'preferences'>('connection');
  const [sendingRef, setSendingRef] = useState<string | null>(null);
  const [studyMessage, setStudyMessage] = useState('');
  const sendingStudy = useRef(false);
  const saveReadingOptions = useCallback((next: LocalSettings, owner?: {language: string; account: string}) => {
    setReadingOptions(next);
    window.localStorage.setItem('proxy-transcript-reading-options', JSON.stringify(next));
    const language=owner?.language??status?.selected_languages?.[selectedGame]?.source_language??'zh';
    window.localStorage.setItem('proxy-transcript-reading-options:'+ (owner?.account??lexirise.account??'legacy')+':'+language,JSON.stringify(next));
    window.dispatchEvent(new Event('lexirise-local-reading-options'));
  }, [selectedGame,status?.selected_languages,lexirise.account]);

  useEffect(() => { setReaderSettingsOpen(null); }, [lexirise.account]);

  useEffect(() => {
    const saved = Number(window.localStorage.getItem('proxy-transcript-playback-rate'));
    if ([1, 0.85, 0.75, 0.6].includes(saved)) setPlaybackRate(saved);
    const reader = window.localStorage.getItem('proxy-transcript-reading-mode');
    if (reader === 'migaku' || reader === 'lexirise') setReadingMode(reader);
    try {
      const saved = window.localStorage.getItem('proxy-transcript-reading-options');
      if (saved) setReadingOptions(restoreLocalSettings(JSON.parse(saved)));
      else {
        const pinyin = window.localStorage.getItem('proxy-transcript-pinyin-mode');
        if (pinyin === 'unknown' || pinyin === 'all' || pinyin === 'off')
          setReadingOptions({ ...DEFAULT_READING_OPTIONS, pinyin });
      }
    } catch { setReadingOptions(DEFAULT_READING_OPTIONS); }
  }, []);

  useEffect(() => {
    settingsOpenRef.current = settingsOpen;
  }, [settingsOpen]);

  const loadSnapshot = useCallback(() => pollOwner.current?.request() ?? Promise.resolve(), []);

  useEffect(() => {
    let accountContext = '';
    type StateEvent = {context:StateContext; type:string; line?:TranscriptLine; line_id?:number; capture?:CaptureStatus; settings?:Settings; textmaps?:StatusPayload['textmaps']; updates?:StatusPayload['updates']};
    const events = new StateEvents<StateEvent>();
    const retireAccount = () => {
      accountScope.current.generation++;
      accountScope.current.ready = false;
      setLexirise({ configured: false, sent: {} });
      setStudyMessage('');
    };
    const owner = new StatePoll<CompanionSnapshot>(async signal => {
      const response = await fetch(`${API_URL}/api/snapshot`, {cache:'no-store', signal});
      if (!response.ok) throw Error('Companion service unavailable');
      return await response.json() as CompanionSnapshot;
    }, value => {
      const key = `${value.context.runtime_id}:${value.context.account_generation}`;
      if (key !== accountContext) {
        const previous = accountContext;
        retireAccount(); accountContext = key;
        if (previous) window.dispatchEvent(new CustomEvent('lexirise-credentials-changed', {detail:owner}));
      }
      // One synchronous commit after the complete, versioned payload is ready.
      setStatus(value.status);
      if (!settingsOpenRef.current) setDraftSettings(value.status.settings);
      setLines(current => {
        const merged = mergeTranscriptSnapshot(current, value.lines);
        knownLineIds.current = new Set(merged.map(line => line.id));

        return merged;
      });
      accountScope.current.account = value.lexirise.account ?? 'legacy';
      accountScope.current.ready = value.lexirise.configured;
      setLexirise(value.lexirise);
      setOnline(true);
      setSnapshotLoaded(true);
    }, () => setOnline(false), value => events.reconcile(value, (snapshot,event) => {
      if (event.type === 'line' && event.line && isReadableLine(event.line)) {
        const exists = snapshot.lines.some(line => line.id === event.line!.id);
        return {...snapshot, lines:[...snapshot.lines.filter(line => line.id !== event.line!.id), event.line],
          status:{...snapshot.status, session:{...snapshot.status.session,
            line_count:snapshot.status.session.line_count + (exists ? 0 : 1),
            total_line_count:snapshot.status.session.total_line_count + (exists ? 0 : 1)}}};
      }
      if (event.type === 'line_deleted') {
        const exists = snapshot.lines.some(line => line.id === event.line_id);
        return {...snapshot, lines:snapshot.lines.filter(line => line.id !== event.line_id),
          status:{...snapshot.status, session:{...snapshot.status.session,
            line_count:Math.max(0,snapshot.status.session.line_count - (exists ? 1 : 0)),
            total_line_count:Math.max(0,snapshot.status.session.total_line_count - (exists ? 1 : 0))}}};
      }
      if (event.type === 'capture_status' && event.capture) return {...snapshot,status:{...snapshot.status,capture:event.capture}};
      if (event.type === 'settings' && event.settings) return {...snapshot,status:{...snapshot.status,settings:event.settings}};
      if (event.type === 'textmaps_status' && event.textmaps) return {...snapshot,status:{...snapshot.status,textmaps:event.textmaps}};
      if (event.type === 'update_status' && event.updates) return {...snapshot,status:{...snapshot.status,updates:event.updates}};
      return snapshot;
    }));
    pollOwner.current = owner;
    const changed = (event:Event) => {
      if (event instanceof CustomEvent && event.detail === owner) return;
      owner.reset();
      retireAccount();
      void owner.request();
    };
    window.addEventListener('lexirise-credentials-changed', changed);
    void owner.request();
    const poll = window.setInterval(() => void owner.request(), 10000);
    let closed = false;
    let socket: WebSocket | null = null;

    const connect = () => {
      socket = new WebSocket(WS_URL);
      const connection = socket;
      socket.onopen = () => {
        if (closed || socket !== connection) return;
        owner.reset(true);
        events.reset();
        accountContext = '';
        retireAccount();
        window.dispatchEvent(new Event('companion-runtime-reset'));
        setOnline(true);
        void owner.request();
      };
      socket.onmessage = (message) => {
        if (closed || socket !== connection) return;
        let event;
        try {event = JSON.parse(message.data);} catch {return;}
        if (!owner.accept(event.context, true)) return;
        const key = `${event.context.runtime_id}:${event.context.account_generation}`;
        if (key !== accountContext) {
          const previous = accountContext;
          accountContext = key;
          events.reset();
          retireAccount();
          if (previous) {
            owner.reset();
            window.dispatchEvent(new CustomEvent('lexirise-credentials-changed', {detail:owner}));
            void owner.request();
          }
        }
        // The initial WS snapshot contains only status. The complete HTTP read
        // owns snapshot publication; a late status-only read must not replace it.
        if (event.type === 'snapshot' || event.type === 'account_changed') return;
        const domain = event.type === 'line' ? `line:${event.line?.id}`
          : event.type === 'line_deleted' ? `line:${event.line_id}` : event.type;
        if (!events.record(domain,event)) return;
        if (event.type === 'capture_status') {
          const nextCapture = event.capture as CaptureStatus;
          setStatus((current) => current && !captureStatusEqual(current.capture, nextCapture, settingsOpenRef.current)
            ? { ...current, capture: nextCapture }
            : current);
        }
        if (event.type === 'textmaps_status') {
          setRefreshingMaps(false);
          setStatus((current) => current ? { ...current, textmaps: event.textmaps } : current);
        }
        if (event.type === 'update_status') {
          setStatus((current) => current ? { ...current, updates: event.updates } : current);
        }
        if (event.type === 'settings') {
          if (!settingsOpenRef.current) setDraftSettings(event.settings);
          setStatus((current) => current ? { ...current, settings: event.settings } : current);
        }
        if (event.type === 'line') {
          const line = event.line as TranscriptLine;
          if (!isReadableLine(line)) return;
          const isNew = !knownLineIds.current.has(line.id);
          knownLineIds.current.add(line.id);
          setLines((current) => {
            const existing = current.some((item) => item.id === line.id);
            return (existing
              ? current.map((item) => item.id === line.id ? line : item)
              : [line, ...current]
            ).sort(newestFirst);
          });
          setStatus((current) => current ? {
            ...current,
            session: {
              ...current.session,
              line_count: current.session.line_count + (isNew ? 1 : 0),
              total_line_count: current.session.total_line_count + (isNew ? 1 : 0),
            },
          } : current);
        }
        if (event.type === 'line_deleted') {
          const lineId = Number(event.line_id);
          const existed = knownLineIds.current.delete(lineId);
          setLines((current) => current.filter((item) => item.id !== lineId));
          if (existed) {
            setStatus((current) => current ? {
              ...current,
              session: {
                ...current.session,
                line_count: Math.max(0, current.session.line_count - 1),
                total_line_count: Math.max(0, current.session.total_line_count - 1),
              },
            } : current);
          }
        }
      };
      socket.onclose = () => {
        // A prepared update replaces the socket while the local API stays
        // available. Confirm service health without discarding the reader.
        if (!closed && socket === connection) {
          socket = null;
          owner.reset(true);
          events.reset();
          accountContext = '';
          retireAccount();
          window.dispatchEvent(new Event('companion-runtime-reset'));
          reconnectTimer.current = setTimeout(connect, 1500);
        }
      };
      socket.onerror = () => connection.close();
    };

    connect();
    return () => {
      closed = true;
      owner.close();
      if (pollOwner.current === owner) pollOwner.current = null;
      window.clearInterval(poll);
      window.removeEventListener('lexirise-credentials-changed', changed);
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      socket?.close();
    };
  }, []);

  useEffect(() => {
    if (!settingsOpen) return;
    setPreviewTick(Date.now());
    const timer = window.setInterval(() => setPreviewTick(Date.now()), 1100);
    return () => window.clearInterval(timer);
  }, [settingsOpen]);

  const activeGameAvailable = gamePicker.games.some(game => game.id === status?.capture.active_game);
  useEffect(() => {
    const active = status?.capture.active_game;
    if (active && activeGameAvailable && active !== lastActiveGame.current) {
      lastActiveGame.current = active;
      setSelectedGame(active);
      setHistoryPage(0);
    }
  }, [activeGameAvailable, status?.capture.active_game]);

  useEffect(() => {
    if (selectedGame !== 'hito' && gamePicker.games.length && !gamePicker.games.some(game => game.id === selectedGame)) {
      setSelectedGame((activeGameAvailable ? status!.capture.active_game : gamePicker.games[0].id) as GameId);
      setHistoryPage(0);
    }
  }, [gamePicker.target, selectedGame, activeGameAvailable, status?.capture.active_game]);

  const recentLines = useMemo(
    () => lines.filter((line) => line.game === selectedGame).slice(0, HISTORY_LIMIT),
    [lines, selectedGame],
  );
  const visibleLine = recentLines.find((line) =>
    line.session_id === status?.session.id
    && isReadableLine(line)
    && status?.capture.running
    && status.capture.visible_text_ids?.includes(line.text_id)
  ) ?? null;
  const latestSessionLine = recentLines.find((line) =>
    line.session_id === status?.session.id && isReadableLine(line)
  ) ?? null;
  // Keep confirmed dialogue readable between subtitles, including comics and
  // unvoiced lines. Session/game filtering prevents carrying it into another game.
  const latestLine = archivedHistory ? null : visibleLine ?? latestSessionLine;
  const activeReadingSource = latestLine?.source_language ?? status?.selected_languages?.[selectedGame]?.source_language ?? 'zh';
  const providerReadingSource = isStudyLanguage(activeReadingSource) ? activeReadingSource : null;
  const openReadingOptions = () => setReaderSettingsOpen(providerReadingSource
    ? {language: providerReadingSource, account: lexirise.account ?? 'legacy'} : null);
  const historyLines = useMemo(
    () => recentLines.filter((line) => line.id !== latestLine?.id),
    [recentLines, latestLine?.id],
  );
  const favoriteLines = useMemo(
    () => lines.filter((line) => line.game === selectedGame && line.favorite),
    [lines, selectedGame],
  );
  const historyPageCount = Math.max(1, Math.ceil(historyLines.length / HISTORY_PAGE_SIZE));
  const currentHistoryPage = Math.min(historyPage, historyPageCount - 1);
  const visibleTranscriptLines = transcriptTab === 'favorites'
    ? favoriteLines
    : historyLines.slice(
        currentHistoryPage * HISTORY_PAGE_SIZE,
        (currentHistoryPage + 1) * HISTORY_PAGE_SIZE,
      );
  const columnLanguage = (kind: 'source' | 'translation') => {
    const locales = new Set(visibleTranscriptLines.map(line => kind === 'source'
      ? line.source_locale ?? line.source_language ?? 'zh-Hans'
      : line.translation_locale ?? 'en'));
    if (locales.size === 1) return languageName([...locales][0], interfaceLocale);
    if (!locales.size && kind === 'source') {
      const selected = status?.selected_languages?.[selectedGame];
      if (selected) return languageName(selected.source_locale, interfaceLocale);
    }
    return uiText(kind === 'source' ? 'Game text' : 'Translation');
  };
  const sessionId = status?.session.id;
  const sessionLines = useMemo(
    () => lines.filter((line) => line.game === selectedGame && (!sessionId || line.session_id === sessionId)),
    [lines, selectedGame, sessionId],
  );
  useEffect(() => {
    if (historyList.current) historyList.current.scrollTop = 0;
  }, [historyLines.length, favoriteLines.length, transcriptTab, currentHistoryPage]);

  async function toggleCapture() {
    if (!status) return;
    const action = status.capture.running ? 'stop' : 'start';
    await fetch(`${API_URL}/api/capture/${action}`, { method: 'POST' });
    await loadSnapshot();
  }

  function updateRegion(field: keyof CaptureRegion, percent: number) {
    setDraftSettings((current) => {
      if (!current) return current;
      const regionKey = captureRegionKey(selectedGame, setupChannel);
      const value = percent / 100;
      const nextRegion = { ...(selectedGame === 'hito' && current.hito_auto_regions ? activeRegion ?? current[regionKey] : current[regionKey]), [field]: value };
      if (field === 'left') nextRegion.width = Math.min(nextRegion.width, 1 - value);
      if (field === 'top') nextRegion.height = Math.min(nextRegion.height, 1 - value);
      if (field === 'width') nextRegion.width = Math.min(value, 1 - nextRegion.left);
      if (field === 'height') nextRegion.height = Math.min(value, 1 - nextRegion.top);
      return { ...current, ...(selectedGame === 'hito' ? { hito_auto_regions: false } : {}), [regionKey]: nextRegion };
    });
  }

  async function saveSettings() {
    if (!draftSettings) return;
    setSaving(true);
    try {
      const response = await fetch(`${API_URL}/api/settings`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(draftSettings),
      });
      if (!response.ok) throw new Error('Could not save capture settings');
      // The response can arrive after a newer settings event. Refresh through
      // the same versioned owner instead of publishing an unversioned result.
      setSettingsOpen(false);
      await loadSnapshot();
    } finally {
      setSaving(false);
    }
  }

  async function refreshTextMaps() {
    setRefreshingMaps(true);
    try {
      const endpoint = selectedGame === 'hito' ? '/api/hito/update' : ['cyberpunk', 'wuwa', 'witcher3', 'nte', 'beyond', 'heavyrain', 'starrail', 'genshin', 'endfield', 'riseofthetombraider', 'shadowofthetombraider'].includes(selectedGame) ? `/api/games/${selectedGame}/update` : '/api/textmaps/update';
      await fetch(`${API_URL}${endpoint}`, { method: 'POST' });
      await loadSnapshot();
    } finally {
      setRefreshingMaps(false);
    }
  }

  const toggleFavorite = useCallback(async (line: TranscriptLine) => {
    const favorite = !line.favorite;
    setLines((current) => current.map((item) => item.id === line.id ? { ...item, favorite } : item));
    const response = await fetch(`${API_URL}/api/lines/${line.id}/favorite`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ favorite }),
    });
    if (!response.ok) await loadSnapshot();
  }, [loadSnapshot]);

  const playLine = useCallback((line: TranscriptLine) => {
    if (!line.has_audio) return;
    playback.current?.pause();
    // Send Origin: the backend rejects cross-site media loads without one.
    const audio = new Audio();
    audio.crossOrigin = 'anonymous';
    audio.src = `${API_URL}/api/lines/${line.id}/audio?v=${line.id}-${line.audio_source ?? 'recording'}`;
    audio.playbackRate = playbackRate;
    playback.current = audio;
    void audio.play();
  }, [playbackRate]);

  const sendToLexirise = useCallback(async (kind: 'line', id: number | string, game: GameId) => {
    if (sendingStudy.current || !accountScope.current.ready) return;
    const scope = { ...accountScope.current };
    const isCurrent = () => scope.generation === accountScope.current.generation && scope.account === accountScope.current.account && accountScope.current.ready;
    sendingStudy.current = true;
    const ref = `${kind}:${id}`;
    setSendingRef(ref);
    setStudyMessage('Saving sentence to Lexirise…');
    try {
      const response = await fetch(`${API_URL}/api/lines/${id}/lexirise`, {
        method: 'POST', headers: { 'X-Proxy-Transcript': 'lexirise','X-Proxy-Transcript-Account':scope.account },
      });
      const result = await response.json() as { detail?: string; deck_id: number; already_sent?: boolean; audio_included?: boolean };
      if (!isCurrent()) return;
      if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : 'Could not send to Lexirise.');
      pollOwner.current?.reset(); // A previously read ledger cannot erase this completed export.
      setLexirise(current => ({ ...current, sent: { ...current.sent, [ref]: result.deck_id } }));
      setStudyMessage(`${result.already_sent ? 'Already saved' : result.audio_included === false ? 'Sentence saved' : 'Sentence and voice saved'} in Lexirise · ${GAME_NAMES[game]}.`);
    } catch (error) {
      if (isCurrent()) setStudyMessage(error instanceof Error ? error.message : 'Could not reach Lexirise. Please retry.');
    } finally {
      sendingStudy.current = false;
      setSendingRef(null);
    }
  }, []);

  function studyButton(kind: 'line', id: number | string, game: GameId, canExport: boolean, compact = false) {
    const ref = `${kind}:${id}`;
    return <LexiriseButton sent={!!lexirise.sent[ref]} busy={sendingRef === ref}
      disabled={!online || !lexirise.configured || !canExport || (sendingRef !== null && sendingRef !== ref)}
      game={game} onClick={() => void sendToLexirise(kind, id, game)} compact={compact} />;
  }

  function changePlaybackRate(value: number) {
    setPlaybackRate(value);
    window.localStorage.setItem('proxy-transcript-playback-rate', String(value));
    if (playback.current) playback.current.playbackRate = value;
  }

  const capture = status?.capture;
  const mapStatus = status?.game_textmaps?.[selectedGame] ?? status?.textmaps;
  const updateStatus = status?.updates;
  const currentCount = sessionLines.length;
  const manualRegion = draftSettings ? draftSettings[captureRegionKey(selectedGame, setupChannel)] : null;
  const detectedBounds = setupChannel === 'tip' ? capture?.tip_crop_bounds : capture?.crop_bounds;
  const gameBounds = capture?.window_bounds;
  const setupRegionLabel = setupChannel === 'dialogue' ? 'Dialogue'
    : setupChannel === 'cinematic' ? selectedGame === 'wuwa' ? 'Centered story cards' : 'Cutscenes & comics'
    : selectedGame === 'hito' ? 'Top box' : selectedGame === 'cyberpunk' || selectedGame === 'witcher3' ? 'NPC chatter' : 'Top-right tips';
  const activeRegion = selectedGame === 'hito' && draftSettings?.hito_auto_regions
    && capture?.active_game === 'hito' && detectedBounds && gameBounds
    ? { left: (detectedBounds[0] - gameBounds[0]) / gameBounds[2],
        top: (detectedBounds[1] - gameBounds[1]) / gameBounds[3],
        width: detectedBounds[2] / gameBounds[2], height: detectedBounds[3] / gameBounds[3] }
    : manualRegion;
  const previewRegionQuery = draftSettings
    ? new URLSearchParams({
        left: String(activeRegion?.left),
        top: String(activeRegion?.top),
        width: String(activeRegion?.width),
        height: String(activeRegion?.height),
        ...(selectedGame === 'nte' ? { picture_area: draftSettings[`${selectedGame}_picture_area`] ?? 'window' } : {}),
        t: String(previewTick),
      }).toString()
    : `t=${previewTick}`;

  // The first visible render already has the correct controls and transcript
  // structure. This avoids a large reconciliation while Migaku parses the page.
  if (!snapshotLoaded) return <main className="companion-shell" aria-busy="true" />;

  return (
    <main className="companion-shell" style={{'--lexirise-font-size': (readingOptions.fontSize ?? 27) + 'px'} as React.CSSProperties}>
      <header className="topbar">
        <div>
          <p className="eyebrow">{GAME_NAMES[selectedGame]}</p>
          <h1>Game immersion toolkit</h1>
          {!archivedHistory && <a href={'/mobile-capture/?pc=1&game='+selectedGame} target="_blank" rel="noopener noreferrer">{uiText("Share transcript to another device")}</a>}
        </div>
        <div className={`live-state ${online ? '' : 'is-offline'}`}>
          <span className="live-pulse" />
          <StableInline text={online ? phaseLabel(capture?.phase ?? 'starting') : "Service offline"} />
        </div>
      </header>

      <div className="game-tabs">
        <span><Gamepad2 size={15} /> {uiText("Games & Languages")}</span>
        {status?.capture.active_game && <small>{uiText("Capturing")} {GAME_NAMES[status.capture.active_game]}</small>}
        <div className="reading-controls" aria-label={uiText("Reading options")}>
        <label>{uiText("Reading")}<select aria-label={uiText("Reading")} value={readingMode} onChange={event => {
          const value = event.target.value as ReadingMode;
          setReadingMode(value); window.localStorage.setItem('proxy-transcript-reading-mode', value);
        }}><option value="migaku">{uiText("Migaku")}</option><option value="lexirise" disabled={!lexirise.configured}>{uiText("Lexirise")}</option></select></label>
        {readingMode === 'lexirise' && <button type="button" className="reader-options-button" onClick={openReadingOptions} disabled={!providerReadingSource}
          title={!providerReadingSource ? uiText('Lexirise reading tools are unavailable for this language.') : undefined}
          aria-label={uiText("Lexirise reading options")}><Settings2 size={15} /> {uiText("Reading options")}</button>}
        {readingMode === 'lexirise' && <button type="button" className="reader-options-button" onClick={() => {setAccountSection('connection');setAccountLanguage(status?.selected_languages?.[selectedGame]?.source_language??'zh');setAccountSettingsOpen(true);}}>{uiText("Account settings")}</button>}
        </div>
      </div>
      <GamePicker picker={gamePicker} mode={readingMode} selectedGame={selectedGame}
        sourceLocale={status?.selected_languages?.[selectedGame]?.source_locale ?? (lexirise.account === 'legacy' ? 'zh-Hans' : undefined)}
        onGameChange={game => {setSelectedGame(game as GameId); setHistoryPage(0); if (game !== 'zzz') setSetupChannel('dialogue');}} />

      {!archivedHistory && online && !status?.selected_languages?.[selectedGame]?.source_locale && (capture?.phase === 'needs_language_setup' || !mapStatus?.ready) && <div className="game-start-card">
        <div><h2>Prepare {GAME_NAMES[selectedGame]} for play</h2><p>Choose the subtitles and original voice you use in the game, then prepare them here. Preparation continues in the background.</p></div>
        <LanguageSetup game={selectedGame} compact targetLanguage={gamePicker.target} showAccount={false} onConfigure={() => {}} onChanged={() => void loadSnapshot()}/>
      </div>}

      <section className="status-strip" aria-label={uiText("Companion status")}>
        <div>
          <Radio size={17} />
          <span>{archivedHistory ? 'Archived history' : selectedGame !== 'zzz' ? uiText("Subtitle OCR + original voice") : uiText("3-zone OCR + voice")}</span>
          <strong><StableInline text={archivedHistory ? "Capture disabled" : capture?.running ? phaseLabel(capture.phase) : "Paused"} /></strong>
        </div>
        <div>
          <Database size={17} />
          <span>{archivedHistory ? 'Saved records' : selectedGame !== 'zzz' ? uiText("Official game text") : uiText("TextMaps")}</span>
          <strong><StableInline text={archivedHistory ? `${recentLines.length} saved lines` : mapStatus?.ready && mapStatus.state !== 'missing_voice' ? `${mapStatus.entry_count.toLocaleString()} pairs` : mapStatus?.message ?? 'Connecting'} /></strong>
        </div>
        <div>
          <Activity size={17} />
          <span>{uiText("This session")}</span>
          <strong><StableInline text={`${currentCount} ${currentCount === 1 ? 'line' : 'lines'}`} /></strong>
        </div>
      </section>

      {!archivedHistory && updateStatus && ['checking','updating','retrying','error'].includes(updateStatus.state) && <section className={`update-progress is-${updateStatus.state}`} aria-label={uiText("Automatic data update status")}>
        <div className="update-progress-copy">
          <RefreshCw size={16} className={updateStatus.state === 'checking' || updateStatus.state === 'updating' ? "is-spinning" : ''} />
          <strong>{uiText("Game language updates")}</strong>
          <StableInline text={updateStatus.message} />
        </div>
        {updateStatus.progress != null && <Progress value={updateStatus.progress} aria-label={`${updateStatus.progress}% complete`} />}
        <span className="update-progress-value">{updateStatus.elapsed_seconds != null && updateStatus.state === 'updating' ? `${Math.floor(updateStatus.elapsed_seconds / 60)}m ${updateStatus.elapsed_seconds % 60}s` : updateStatus.state === 'ready' ? 'Ready' : ''}</span>
        {!!updateStatus.queued && <span>{updateStatus.queued} queued</span>}
        {!!updateStatus.items?.length && <details><summary>Details for all games</summary>{updateStatus.items.map(item => <p key={item.game + item.locale}><strong>{GAME_NAMES[item.game as GameId] ?? item.game} · {item.locale} — {uiText(item.state === 'ready' ? 'Ready' : item.state === 'error' ? 'Preparation failed' : item.state === 'preparing' ? 'Preparing' : item.state)}</strong><br/>{item.message} {item.retry_after}</p>)}</details>}
      </section>}

      {capture && ['needs_language_setup','unvoiced_disabled'].includes(capture.phase) && <p role="status" className="toolkit-setup-note">{capture.message}</p>}

      {!archivedHistory && <section className={`current-line game-${selectedGame} ${latestLine ? '' : 'is-empty'}`} aria-labelledby="current-heading">
        <div className="section-label">
          <span id="current-heading"><Crosshair size={16} /> {uiText("Current line")}</span>
          {latestLine ? (
            <StableInline
              className="match-label"
              text={latestLine.game === 'hito' ? `${latestLine.channel === 'tip' ? 'Top box' : 'Dialogue'} · Game-file text · ${Math.round(latestLine.score)}%` : `${latestLine.game === 'pragmata' ? 'PRAGMATA dialogue' : latestLine.channel === 'tip' ? 'Top-right voice' : latestLine.channel === 'cinematic' ? latestLine.game === 'wuwa' ? 'Centered story card' : 'Cinematic / comic' : latestLine.channel === 'gameplay' ? latestLine.game === 'cyberpunk' || latestLine.game === 'witcher3' ? 'NPC chatter' : 'Gameplay voice' : 'Dialogue'} · ${latestLine.voice_status === 'unvoiced' ? 'Unvoiced' : latestLine.voiced ? 'Voiced' : isComicLine(latestLine) ? 'Game-file text' : 'Checking voice…'} · ${Math.round(latestLine.score)}%`}
            />
          ) : null}
        </div>
        {latestLine ? (
          <div className="current-pair">
            {(latestLine.speaker_english || latestLine.speaker_chinese) && <div className="current-speaker">
              {latestLine.speaker_english && <StableInline text={latestLine.speaker_english} />}
              {latestLine.speaker_chinese && <StableInline className="speaker-chinese" text={latestLine.speaker_chinese} />}
            </div>}
            <EnglishTranslation line={latestLine} summary={currentReadingSummary} limit={readingMode === 'lexirise' ? readingOptions.hideEnglishAt : 'off'} current />
            {readingMode === 'lexirise' ? <ReadingText id={latestLine.id} text={latestLine.source_text??latestLine.chinese} sourceLanguage={latestLine.source_language??'zh'} sentenceTranslation={latestLine.translation_text??latestLine.english} options={readingOptions} current onSummary={setCurrentReadingSummary} /> : <MigakuCurrentText text={latestLine.source_text??latestLine.chinese} lineId={latestLine.id} locale={latestLine.source_locale ?? latestLine.source_language ?? 'zh-Hans'} />}
            <div className="current-actions">
              {latestLine.voice_status === 'unvoiced' ? <span className="text-muted">{uiText('Unvoiced dialogue')}</span> : <button type="button" onClick={() => playLine(latestLine)} disabled={!latestLine.has_audio} aria-label={latestLine.has_audio ? 'Play current voice line' : latestLine.audio_pending ? 'Preparing original voice' : 'Original voice unavailable'} title={latestLine.has_audio ? 'Play voice line' : latestLine.audio_pending ? 'Preparing original game audio' : 'Subtitle captured; original voice extraction is unavailable'}>
                <Volume2 size={18} /> {latestLine.audio_pending ? 'Preparing voice…' : !latestLine.has_audio ? 'Voice unavailable' : latestLine.audio_source === 'original' ? voicePlaybackLabel(latestLine) : 'Play voice'}
              </button>}
              <button type="button" className={latestLine.favorite ? 'is-favorite' : ''} onClick={() => toggleFavorite(latestLine)} aria-label={latestLine.favorite ? 'Remove current line from favorites' : 'Favorite current line'} title={latestLine.favorite ? 'Remove favorite' : 'Keep forever'}>
                <Star size={18} fill={latestLine.favorite ? 'currentColor' : 'none'} /> {latestLine.favorite ? 'Saved' : 'Favorite'}
              </button>
              {studyButton('line', latestLine.id, latestLine.game, latestLine.has_audio || latestLine.voice_status === 'unvoiced')}
            </div>
          </div>
        ) : (
          <div className="current-empty">
            <ScanLine size={28} />
            <div>
              <strong>{uiText('Waiting for dialogue')}</strong>
              <p>{uiText('Matched game dialogue appears here. Previous lines stay in History.')}</p>
            </div>
          </div>
        )}
      </section>}

      <div className="study-status" role="status" aria-live="polite">
        {studyMessage || (online && !lexirise.configured ? 'Lexirise is not configured on this computer.' : '')}
      </div>
      {archivedHistory && <p role="status">Hito’s World capture is disabled. Your saved history and favorites remain available.</p>}
      <section className="transcript" aria-labelledby="transcript-heading">
        <div className="transcript-heading">
          <div>
            <p className="eyebrow">{uiText("Saved transcript")}</p>
            <h2 id="transcript-heading">{transcriptTab === 'favorites' ? uiText("Favorites") : uiText("Earlier lines")}</h2>
          </div>
          {lines.some(line => line.game === 'hito') && <label className="playback-speed archived-history">Archived game history
            <select aria-label="Archived game history" value={archivedHistory ? 'hito' : ''} onChange={event => {
              setSelectedGame(event.target.value === 'hito' ? 'hito' : status?.capture.active_game && status.capture.active_game !== 'hito' ? status.capture.active_game : 'zzz');
              setHistoryPage(0); changeTranscriptTab('history', true);
            }}><option value="">Active games</option><option value="hito">Hito's World (archived)</option></select>
          </label>}
          <p>{transcriptTab === 'favorites' ? `${favoriteLines.length} saved forever` : uiText("10 at a time · up to 50 recent lines")}</p>
        </div>

        <div className="transcript-tabs" role="tablist" aria-label={uiText("Transcript view")}>
          <button
            type="button"
            role="tab"
            aria-selected={transcriptTab === 'history'}
            className={transcriptTab === 'history' ? "is-active" : ''}
            onClick={() => changeTranscriptTab('history', true)}
          >
            {uiText("History")}</button>
          <button
            type="button"
            role="tab"
            aria-selected={transcriptTab === 'favorites'}
            className={transcriptTab === 'favorites' ? "is-active" : ''}
            onClick={() => changeTranscriptTab('favorites', true)}
          >
            <Star size={14} fill={transcriptTab === 'favorites' ? "currentColor" : "none"} />
            {uiText("Favorites")}<span>{favoriteLines.length}</span>
          </button>
        </div>

        <div className="column-labels" aria-hidden="true">
          <span>{uiText("Time / type")}</span><span>{columnLanguage('translation')}</span><span>{columnLanguage('source')}</span><span>{uiText("Match")}</span>
        </div>
        <div className="line-list" ref={historyList}>
          {visibleTranscriptLines.length ? visibleTranscriptLines.map((line) => (
            <TranscriptRow
              key={line.id}
              line={line}
              readingMode={readingMode}
              readingOptions={readingOptions}
              canUseLexirise={online && lexirise.configured}
              sendingRef={sendingRef}
              sentToLexirise={!!lexirise.sent[`line:${line.id}`]}
              onPlay={playLine}
              onToggleFavorite={toggleFavorite}
              onSendToLexirise={(kind, id) => { void sendToLexirise(kind, id, selectedGame); }}
            />
          )) : (
            <div className="transcript-empty">
              {transcriptTab === 'favorites' ? <Star size={24} /> : <Database size={24} />}
              <p>{transcriptTab === 'favorites'
                ? 'Favorite a line with the star button and it will stay here between sessions.'
                : `Your matched ${GAME_NAMES[selectedGame]} lines will remain after a restart.`}</p>
            </div>
          )}
        </div>
        {transcriptTab === 'history' && historyLines.length > HISTORY_PAGE_SIZE && (
          <nav className="history-pagination" aria-label={uiText("Transcript history pages")}>
            <button
              type="button"
              onClick={() => setHistoryPage(Math.max(0, currentHistoryPage - 1))}
              disabled={currentHistoryPage === 0}
            >
              {uiText("Newer 10")}</button>
            <span>
              {currentHistoryPage * HISTORY_PAGE_SIZE + 1}–{Math.min((currentHistoryPage + 1) * HISTORY_PAGE_SIZE, historyLines.length)} {uiText("of")}{historyLines.length}
            </span>
            <button
              type="button"
              onClick={() => setHistoryPage(Math.min(historyPageCount - 1, currentHistoryPage + 1))}
              disabled={currentHistoryPage >= historyPageCount - 1}
            >
              {uiText("Previous 10")}</button>
          </nav>
        )}
      </section>

      <footer className="capture-footer">
        <span className={capture?.phase === 'error' ? "has-error" : ''}>
          <span className="live-pulse" /> <StableInline text={capture?.message ?? 'Connecting to local capture service'} />
        </span>
        <div className="footer-actions">
          <label className="playback-speed">
            <Volume2 size={16} />
            <span>{uiText("Speed")}</span>
            <select value={playbackRate} onChange={(event) => changePlaybackRate(Number(event.target.value))} aria-label={uiText("Voice playback speed")}>
              <option value={1}>1×</option>
              <option value={0.85}>0.85×</option>
              <option value={0.75}>0.75×</option>
              <option value={0.6}>0.6×</option>
            </select>
          </label>
          <Button
            variant="outline"
            className={capture?.running ? "capture-toggle is-running" : "capture-toggle"}
            onClick={toggleCapture}
            disabled={archivedHistory || !online || !status}
          >
            <Pause className="capture-pause-icon" />
            <Play className="capture-play-icon" />
            <span className="capture-pause-label">{uiText("Pause")}</span>
            <span className="capture-play-label">{uiText("Start")}</span>
          </Button>
          <Button onClick={() => { if (status) setDraftSettings(status.settings); setSettingsOpen(true); }} disabled={archivedHistory || !online || !draftSettings}>
            <Settings2 /> {uiText("Capture setup")}</Button>
          <ToolkitSetup key={lexirise.account ?? 'legacy'} online={online} game={archivedHistory ? 'zzz' : selectedGame} onGameChange={setSelectedGame} readingMode={readingMode} targetLanguage={gamePicker.target} allowedGames={gamePicker.games.map(game => game.id)}
            onReadingMode={value => { setReadingMode(value); window.localStorage.setItem('proxy-transcript-reading-mode', value); }}
            onCapture={() => { if (archivedHistory) setSelectedGame('zzz'); if (status) setDraftSettings(status.settings); setSettingsOpen(true); }}
            readingSupported={!!providerReadingSource} onReading={openReadingOptions} onAccount={language => {setAccountSection(language ? 'preferences' : 'connection');setAccountLanguage(language??'zh');setAccountSettingsOpen(true);}} onChanged={() => void loadSnapshot()} />
        </div>
      </footer>

      {readerSettingsOpen && readerSettingsOpen.account === (lexirise.account ?? 'legacy') && <ReadingOptionsDialog initial={readingOptions} onChange={next => saveReadingOptions(next, readerSettingsOpen)} onClose={() => setReaderSettingsOpen(null)} sourceLanguage={readerSettingsOpen.language} />}
      {readingMode === 'lexirise' && accountSettingsOpen && accountSection === 'connection' && <Dialog open onOpenChange={setAccountSettingsOpen}><DialogContent className="toolkit-account-dialog" showCloseButton={false}><button className="account-close" type="button" aria-label="Close Lexirise settings" onClick={() => setAccountSettingsOpen(false)}>×</button><DialogHeader><DialogTitle>{uiText("Lexirise account settings")}</DialogTitle><DialogDescription>Choose your account and where sentences are saved.</DialogDescription></DialogHeader>
        <AccountSwitcher onChanged={() => void loadSnapshot()}/>
        {selectedGame !== 'hito' && <details open><summary>Sentence destination · {GAME_NAMES[selectedGame]}</summary><GameDeckSettings key={lexirise.account ?? 'legacy'} game={selectedGame} title={GAME_NAMES[selectedGame]} language={status?.selected_languages?.[selectedGame]?.source_language??'zh'} current={(lexirise.by_language?.[status?.selected_languages?.[selectedGame]?.source_language??'zh']?.decks??lexirise.decks)?.[selectedGame]} onConfigured={() => void loadSnapshot()} /></details>}
        <Button className="account-preferences" variant="outline" onClick={() => setAccountSection('preferences')}>Study languages, dictionaries and account preferences</Button>
      </DialogContent></Dialog>}
      {readingMode === 'lexirise' && accountSettingsOpen && accountSection === 'preferences' && <SettingsPanel title={uiText("Lexirise account preferences")} showReadingOptions={false} initial={readingOptions} onChange={saveReadingOptions} onClose={() => setAccountSettingsOpen(false)} adapter={settingsAdapter} sourceLanguage={isStudyLanguage(accountLanguage)?accountLanguage:"zh"} connection={<Button variant="outline" onClick={() => setAccountSection('connection')}>Back to account and sentence destination</Button>} />}

      <Dialog open={settingsOpen} onOpenChange={setSettingsOpen}>
        <DialogContent className="setup-dialog sm:max-w-3xl">
          <DialogHeader>
            <DialogTitle>{uiText("Capture setup")}</DialogTitle>
            <DialogDescription>
              {selectedGame === 'hito' ? uiText("Tune the bottom dialogue box and top message box independently.") : selectedGame === 'zzz' ? uiText("Tune dialogue, top-right subtitles, and cinematics independently.") : uiText("Tune the subtitle area, including wrapped English and Chinese lines.")}
            </DialogDescription>
          </DialogHeader>

          <p>{uiText("Capture adjustments are saved on this PC.")}{selectedGame !== 'hito' && 'Choose and prepare the study language and its matching original voice in Setup → Languages.'}</p>
          {draftSettings && <label className="toolkit-setup-checkbox"><input type="checkbox" checked={draftSettings.capture_unvoiced ?? false}
            onChange={event => setDraftSettings(current => current ? {...current, capture_unvoiced: event.target.checked} : current)} /> {uiText('Include unvoiced dialogue')}
          </label>}
          <p className="toolkit-setup-note">{uiText('Applies to all games. Includes text the game identifies as unvoiced; missing voice files are reported separately. Saved history is kept when this is off.')}</p>
          {draftSettings && selectedGame !== 'hito' && <NdiSourceSettings game={selectedGame}
            value={{capture_source: draftSettings.capture_source ?? 'window', ndi_source: draftSettings.ndi_source ?? '', ndi_game: draftSettings.ndi_game ?? null}}
            onChange={next => setDraftSettings(current => current ? {...current, ...next} : current)} />}
          {selectedGame === 'zzz' && draftSettings && <label>{uiText("Proxy voice")}<select aria-label={uiText("Proxy voice")} value={draftSettings.zzz_proxy_voice ?? 'unconfigured'}
              onChange={event => setDraftSettings(current => current ? { ...current, zzz_proxy_voice: event.target.value as Settings['zzz_proxy_voice'] } : current)}>
              <option value="unconfigured">{uiText("Choose the Proxy for variant lines")}</option>
              <option value="female">{uiText("Belle")}</option><option value="male">{uiText("Wise")}</option>
            </select>
          </label>}
          {selectedGame === 'cyberpunk' && draftSettings && <label>{uiText("V voice")}<select value={draftSettings.cyberpunk_v_voice} onChange={event => setDraftSettings(current => current ? { ...current, cyberpunk_v_voice: event.target.value as Settings['cyberpunk_v_voice'] } : current)}>
              <option value="unconfigured">{uiText("Choose V's voice to capture variant lines")}</option>
              <option value="female">{uiText("Female")}</option><option value="male">{uiText("Male")}</option>
            </select>
          </label>}
          {selectedGame === 'wuwa' && draftSettings && <label>{uiText("Rover voice")}<select value={draftSettings.wuwa_rover_voice} onChange={event => setDraftSettings(current => current ? { ...current, wuwa_rover_voice: event.target.value as Settings['wuwa_rover_voice'] } : current)}>
              <option value="unconfigured">{uiText("Choose Rover's voice to capture variant lines")}</option>
              <option value="female">{uiText("Female")}</option><option value="male">{uiText("Male")}</option>
            </select>
          </label>}
          {(['starrail', 'genshin', 'endfield'] as const).map(game => selectedGame === game && draftSettings && <label key={game}>
            {{starrail: 'Trailblazer voice', genshin: 'Traveler voice', endfield: 'Endministrator voice'}[game]}
            <select aria-label={{starrail: 'Trailblazer voice', genshin: 'Traveler voice', endfield: 'Endministrator voice'}[game]} value={draftSettings[`${game}_player_voice`] ?? 'unconfigured'}
              onChange={event => setDraftSettings(current => current ? {...current, [`${game}_player_voice`]: event.target.value} : current)}>
              <option value="unconfigured">Choose when needed</option><option value="female">Female</option><option value="male">Male</option>
            </select></label>)}
          {selectedGame === 'nte' && draftSettings && <label>{uiText("Zero voice")}<select aria-label={uiText("Zero voice")} value={draftSettings.nte_player_voice ?? 'unconfigured'}
              onChange={event => setDraftSettings(current => current ? { ...current, nte_player_voice: event.target.value as Settings['nte_player_voice'] } : current)}>
              <option value="unconfigured">{uiText("Choose Zero's voice for movie variants")}</option>
              <option value="female">{uiText("Female")}</option><option value="male">{uiText("Male")}</option>
            </select>
          </label>}
          {selectedGame === 'hito' && draftSettings && <label>
            <input type="checkbox" checked={draftSettings.hito_auto_regions}
              onChange={event => setDraftSettings(current => current ? { ...current, hito_auto_regions: event.target.checked } : current)} />
            {' '}{uiText("Automatically follow Hito message boxes at the current resolution and zoom")}</label>}

          {(selectedGame === 'cyberpunk' || selectedGame === 'wuwa' || selectedGame === 'witcher3') && draftSettings && <label>
            <input type="checkbox" checked={draftSettings[`${selectedGame}_capture_chatter`]}
              onChange={event => setDraftSettings(current => current ? { ...current, [`${selectedGame}_capture_chatter`]: event.target.checked } : current)} />
            {' '}{selectedGame === 'wuwa' ? uiText("Capture top-right voices (experimental; off by default)") : uiText("Capture conversations above NPC heads")}
          </label>}
          {(selectedGame === 'cyberpunk' || selectedGame === 'witcher3' || selectedGame === 'wuwa') && <p className="setup-note">
            {uiText("Extra voices require an exact subtitle match. Main dialogue takes priority; response choices are excluded.")}</p>}

          {selectedGame === 'wuwa' && draftSettings && <label>
            <input type="checkbox" checked={draftSettings.wuwa_capture_cinematic}
              onChange={event => setDraftSettings(current => current ? { ...current, wuwa_capture_cinematic: event.target.checked } : current)} />
            {' '}{uiText("Capture centered story cards on dark backgrounds")}</label>}

          <div className="capture-tabs" role="tablist" aria-label={uiText("Capture region")}>
            <button
              type="button"
              className={setupChannel === 'dialogue' ? "is-active" : ''}
              onClick={() => setSetupChannel('dialogue')}
            >
              <MessageSquareText size={16} /> {uiText("Dialogue")}</button>
            {(selectedGame === 'zzz' || selectedGame === 'hito' || selectedGame === 'wuwa' || selectedGame === 'cyberpunk' || selectedGame === 'witcher3') && <button
              type="button"
              className={setupChannel === 'tip' ? "is-active" : ''}
              onClick={() => setSetupChannel('tip')}
            >
              <ScanLine size={16} /> {selectedGame === 'hito' ? uiText("Top box") : selectedGame === 'cyberpunk' || selectedGame === 'witcher3' ? uiText("NPC chatter") : uiText("Top-right tips")}
            </button>}
            {(selectedGame === 'zzz' || selectedGame === 'wuwa') && <button
              type="button"
              className={setupChannel === 'cinematic' ? "is-active" : ''}
              onClick={() => setSetupChannel('cinematic')}
            >
              <Volume2 size={16} /> {selectedGame === 'wuwa' ? uiText("Centered story cards") : uiText("Cutscenes & comics")}
            </button>}
          </div>

          {(selectedGame === 'nte') && draftSettings && <label>{uiText("Game picture area")}<select aria-label={uiText("Game picture area")} value={draftSettings[`${selectedGame}_picture_area`] ?? 'window'}
              onChange={event => setDraftSettings(current => current ? { ...current, [`${selectedGame}_picture_area`]: event.target.value } : current)}>
              <option value="window">{uiText("Full game window")}</option>
              <option value="16:9">{uiText("Centered 16:9 picture inside black bars")}</option>
            </select>
          </label>}
          {(selectedGame === 'nte') && <p className="setup-note">
            {uiText("Choose the picture inside black bars only when your game is letterboxed. Check the live crop after changing resolution or subtitle size. Movie captions use the game's original subtitle timings and Original voices. Select Zero's voice to capture movies with player variants.")}</p>}
          {(selectedGame === 'nte') && draftSettings && <button type="button" className="secondary-button"
            onClick={() => setDraftSettings(current => current ? { ...current, [`${selectedGame}_region`]: { left: .10, top: .70, width: .80, height: .28 } } : current)}>
            {uiText("Use tested dialogue crop")}</button>}

          <div className="capture-preview">
            {capture?.active_game === selectedGame && capture?.window_bounds ? (
              <img
                key={previewTick}
                crossOrigin="anonymous"
                src={`${API_URL}/api/capture/preview.jpg?${previewRegionQuery}`}
                alt={`Live preview of the ${setupRegionLabel.toLowerCase()} capture region`}
              />
            ) : (
              <div className="preview-placeholder"><ScanLine /> {uiText("Start the selected game to see the capture preview.")}</div>
            )}
            <span>{setupRegionLabel} {uiText("live crop")}</span>
          </div>

          {draftSettings ? (
            <div className="region-controls">
              {([
                ['left', 'Left edge'],
                ['width', 'Width'],
                ['top', 'Top edge'],
                ['height', 'Height'],
              ] as const).map(([field, label]) => (
                <label key={field}>
                  <span>{label}<strong>{Math.round((activeRegion ?? draftSettings.region)[field] * 100)}%</strong></span>
                  <input
                    type="range"
                    min={field === 'width' || field === 'height' ? 5 : 0}
                    max={100}
                    step={1}
                    value={Math.round((activeRegion ?? draftSettings.region)[field] * 100)}
                    onChange={(event) => updateRegion(field, Number(event.target.value))}
                  />
                </label>
              ))}
            </div>
          ) : null}

          <div className="ocr-readout">
            <span>{uiText("Latest OCR")}</span>
            <StableText text={(setupChannel === 'tip' ? capture?.last_tip_ocr : setupChannel === 'cinematic' ? capture?.last_cinematic_ocr : capture?.last_ocr) || 'No subtitle text detected in the current region.'} />
            <small><StableInline text={(setupChannel === 'tip' ? capture?.last_tip_ocr_confidence : setupChannel === 'cinematic' ? capture?.last_cinematic_ocr_confidence : capture?.last_ocr_confidence) ? `${Math.round((setupChannel === 'tip' ? capture?.last_tip_ocr_confidence : setupChannel === 'cinematic' ? capture?.last_cinematic_ocr_confidence : capture?.last_ocr_confidence) ?? 0)}% OCR confidence` : "Waiting for text"} /></small>
          </div>

          <div className="setup-actions">
            <Button variant="outline" onClick={refreshTextMaps} disabled={refreshingMaps}>
              <RefreshCw className={refreshingMaps ? "is-spinning" : ''} />
              <StableInline text={refreshingMaps ? "Updating…" : selectedGame === 'hito' ? "Refresh from game" : "Update TextMaps"} />
            </Button>
            <Button onClick={saveSettings} disabled={!draftSettings || saving}>
              <StableInline text={saving ? "Saving…" : "Save capture settings"} />
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </main>
  );
}
