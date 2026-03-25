import {
  createEmptyRunEventSafety,
  createRunEventKey,
  parseOrderedRunEventList,
  parseRunHistoryListResponse,
  parseRunHistoryRunSnapshot,
  type CanonicalRunEvent,
  type RunHistoryRetentionMetadata,
  type RunHistoryRunSnapshot,
  type RunHistoryRunSummary,
} from "./browser-contracts.js";
import { resolveRunAnswer, segmentStructuredAnswer } from "./answer-rendering.js";
import {
  createRun,
  subscribeToRunEvents,
  type RunStreamSubscription,
} from "./api-client.js";
import { initialRunState, reduceRunState, type RunState } from "./state.js";
import type { RunMode } from "./browser-contracts.js";
import { toRunEventTimelineRows } from "./timeline.js";
import { resolvePageContext } from "./page-context.js";

interface SelectedRunView {
  kind: "empty" | "history" | "preview" | "live";
  runId: string | null;
  finalAnswer: string | null;
  events: CanonicalRunEvent[];
  retention: RunHistoryRetentionMetadata | null;
  updatedAt: string | null;
  label: string;
}

const RUN_MODE_DETAILS: Record<
  RunMode,
  {
    label: string;
    description: string;
  }
> = {
  quick: {
    label: "Quick search",
    description: "Fastest path. One quick web-grounded pass for a concise answer.",
  },
  agentic: {
    label: "Agentic search",
    description: "Balanced exploration. Uses bounded search and crawl steps before answering.",
  },
  deep_research: {
    label: "Deep research",
    description: "Longest path. Runs broader background research and streams progress over time.",
  },
};

const pageContext = resolvePageContext(window.location.pathname);

const promptInput = requireElement<HTMLTextAreaElement>("prompt-input");
const phaseLabel = requireElement<HTMLElement>("phase-label");
const pageTitle = requireElement<HTMLElement>("page-title");
const pageLead = requireElement<HTMLElement>("page-lead");
const promptLabel = requireElement<HTMLElement>("prompt-label");
const modeInputs = document.querySelectorAll<HTMLInputElement>('input[name="run-mode"]');
const promptError = requireElement<HTMLElement>("prompt-error");
const modeHint = requireElement<HTMLElement>("mode-hint");
const runForm = requireElement<HTMLFormElement>("run-form");
const runButton = requireElement<HTMLButtonElement>("run-submit");
const previewButton = requireElement<HTMLButtonElement>("preview-events");
const runStatus = requireElement<HTMLElement>("run-status");
const runDetails = requireElement<HTMLElement>("run-details");
const historyStatus = requireElement<HTMLElement>("history-status");
const historyRefreshButton = requireElement<HTMLButtonElement>("history-refresh");
const historyList = requireElement<HTMLOListElement>("history-list");
const runViewHeader = requireElement<HTMLElement>("run-view-header");
const runViewMeta = requireElement<HTMLElement>("run-view-meta");
const finalAnswer = requireElement<HTMLElement>("final-answer");
const sourceList = requireElement<HTMLElement>("source-list");
const retentionNote = requireElement<HTMLElement>("retention-note");
const timelineEmpty = requireElement<HTMLElement>("timeline-empty");
const timelineList = requireElement<HTMLElement>("timeline-list");
const inspectorEmpty = requireElement<HTMLElement>("inspector-empty");
const inspectorHeader = requireElement<HTMLElement>("inspector-header");
const inspectorMeta = requireElement<HTMLElement>("inspector-meta");
const inspectorInput = requireElement<HTMLElement>("payload-input");
const inspectorOutput = requireElement<HTMLElement>("payload-output");
const inspectorError = requireElement<HTMLElement>("payload-error");
const inspectorFinalAnswer = requireElement<HTMLElement>("payload-final-answer");

let state = reduceRunState(initialRunState, {
  type: "mode_updated",
  mode: pageContext.mode,
});
let streamSubscription: RunStreamSubscription | null = null;
let durationTimer: number | null = null;
let historyRuns: RunHistoryRunSummary[] = [];
let selectedRunView: SelectedRunView = createEmptyRunView();
let selectedEventKey: string | null = null;
let historyRefreshInFlight = false;

render();
void refreshRunHistory({ selectLatest: true });

promptInput.addEventListener("input", () => {
  dispatch({
    type: "prompt_updated",
    prompt: promptInput.value,
  });
});

for (const input of modeInputs) {
  input.addEventListener("change", () => {
    if (!input.checked) {
      return;
    }

    dispatch({
      type: "mode_updated",
      mode: parseRunModeInput(input.value),
    });
  });
}

previewButton.addEventListener("click", () => {
  closeRunStream();
  setSelectedRunView({
    kind: "preview",
    runId: "preview-run",
    finalAnswer:
      "Search succeeded, crawl failed safely, and the agent kept the error visible.",
    events: createPreviewEvents(),
    retention: {
      maxRuns: 25,
      maxEventsPerRun: 100,
      maxPayloadBytes: 32_768,
      duplicateEventsIgnored: 0,
      outOfOrderEventsRejected: 0,
      eventsDropped: 0,
      payloadTruncations: [
        {
          eventSeq: 2,
          eventType: "tool_call_succeeded",
          fields: ["tool_output"],
          omittedBytes: 512,
        },
      ],
    },
    updatedAt: "2026-03-17T12:00:04.000Z",
    label: "Preview payload view",
  });
  render();
});

historyRefreshButton.addEventListener("click", () => {
  void refreshRunHistory({ preserveSelection: true });
});

runForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const prompt = promptInput.value.trim();
  dispatch({
    type: "prompt_updated",
    prompt,
  });

  if (prompt.length === 0) {
    dispatch({
      type: "run_failed",
      message: "Prompt is required.",
    });
    return;
  }

  closeRunStream();
  dispatch({ type: "run_requested" });

  const result = await createRun({ prompt, mode: state.selectedMode });
  if (result.ok) {
    dispatch({
      type: "run_started",
      response: result.data,
    });
    setSelectedRunView({
      kind: "live",
      runId: result.data.runId,
      finalAnswer: null,
      events: [],
      retention: null,
      updatedAt: null,
      label: "Current live run",
    });
    syncSelectedRunViewFromState();
    render();
    openRunStream(result.data.runId);
    return;
  }

  dispatch({
    type: "run_failed",
    message: result.message,
  });
});

function dispatch(action: Parameters<typeof reduceRunState>[1]) {
  state = reduceRunState(state, action);
  syncSelectedRunViewFromState();
  render();
}

function render() {
  phaseLabel.textContent = pageContext.phaseLabel;
  pageTitle.textContent = pageContext.pageTitle;
  pageLead.textContent = pageContext.lead;
  promptLabel.textContent = pageContext.promptLabel;
  promptInput.value = state.prompt;
  const runInFlight = state.phase === "starting" || state.phase === "running";
  for (const input of modeInputs) {
    input.checked = input.value === state.selectedMode;
    input.disabled = runInFlight;
  }
  runButton.disabled = runInFlight;
  historyRefreshButton.disabled = historyRefreshInFlight;

  promptError.textContent =
    state.phase === "failed" && state.prompt.length === 0
      ? state.error
      : "";
  modeHint.textContent = describeMode(state.selectedMode);

  runStatus.textContent = statusLabel(state);
  runStatus.dataset.phase = state.phase;

  runDetails.textContent = detailsLabel(state);
  renderHistoryList();
  renderRunViewSummary();
  renderTimeline();
  renderInspector();
  syncDurationTimer();
}

function statusLabel(currentState: RunState): string {
  switch (currentState.phase) {
    case "idle":
      return "Idle";
    case "starting":
      return "Starting";
    case "running":
      return "Running";
    case "completed":
      return "Completed";
    case "failed":
      return "Failed";
  }
}

function detailsLabel(currentState: RunState): string {
  const modeLabel = formatModeLabel(currentState.selectedMode);
  switch (currentState.phase) {
    case "idle":
      return `Selected mode: ${modeLabel}. Enter a prompt to start one run, select prior history, or load the preview.`;
    case "starting":
      return `Creating ${modeLabel} run...`;
    case "running":
      return currentState.activeRunId === null
        ? `${modeLabel} run active.`
        : `${modeLabel} run ${currentState.activeRunId} is active. Live events stream into the run viewer below.`;
    case "completed":
      return currentState.finalAnswer ?? "Run completed.";
    case "failed":
      return currentState.error ?? "Run could not be started.";
  }
}

function formatModeLabel(mode: RunMode): string {
  return RUN_MODE_DETAILS[mode].label;
}

function describeMode(mode: RunMode): string {
  return RUN_MODE_DETAILS[mode].description;
}

function parseRunModeInput(input: string): RunMode {
  if (input === "quick" || input === "agentic" || input === "deep_research") {
    return input;
  }

  throw new Error(`Unsupported run mode: ${input}`);
}

function renderHistoryList() {
  historyList.replaceChildren(
    ...historyRuns.map((run) => {
      const item = document.createElement("li");
      item.className = "history-item";

      const button = document.createElement("button");
      button.type = "button";
      button.className = "history-button";
      button.dataset.selected = String(run.runId === selectedRunView.runId);
      button.addEventListener("click", () => {
        void loadRunHistoryDetail(run.runId);
      });

      const title = document.createElement("p");
      title.className = "history-run-id";
      title.textContent = run.runId;

      const answer = document.createElement("p");
      answer.className = "history-run-answer";
      answer.textContent =
        run.finalAnswer ?? "No final answer stored for this run yet.";

      const meta = document.createElement("p");
      meta.className = "history-run-meta";
      meta.textContent = `${run.eventCount} events · updated ${formatDateTime(run.updatedAt)}`;

      button.append(title, answer, meta);
      item.append(button);
      return item;
    }),
  );
}

function renderRunViewSummary() {
  if (selectedRunView.kind === "empty") {
    runViewHeader.textContent = "No run selected";
    runViewMeta.textContent =
      "Start a run, refresh history, or load the preview to inspect a cohesive answer and trace view.";
    renderAnswerSummary({
      text: "Final answers for the selected run appear here.",
      structuredAnswer: null,
      sources: [],
    });
    retentionNote.textContent =
      "Retention bounds and truncation markers will be shown when present.";
    return;
  }

  runViewHeader.textContent =
    selectedRunView.runId === null
      ? selectedRunView.label
      : `${selectedRunView.label} · ${selectedRunView.runId}`;
  runViewMeta.textContent = `${selectedRunView.events.length} ordered events${
    selectedRunView.updatedAt === null
      ? ""
      : ` · updated ${formatDateTime(selectedRunView.updatedAt)}`
  }`;
  renderAnswerSummary(
    resolveRunAnswer(
      selectedRunView.events,
      selectedRunView.finalAnswer ?? "No final answer stored for this run.",
    ),
  );
  retentionNote.textContent = describeRetention(selectedRunView.retention);
}

function renderTimeline() {
  const rows = toRunEventTimelineRows(selectedRunView.events);
  timelineEmpty.hidden = rows.length > 0;
  timelineEmpty.textContent =
    selectedRunView.kind === "empty"
      ? "No event activity yet."
      : "No events are available for the selected run.";

  timelineList.replaceChildren(
    ...rows.map((row) => {
      const item = document.createElement("li");
      item.className = "timeline-item";

      const button = document.createElement("button");
      button.className = "timeline-row";
      button.type = "button";
      button.dataset.eventType = row.eventType;
      button.dataset.selected = String(row.eventKey === selectedEventKey);
      button.addEventListener("click", () => {
        selectedEventKey = row.eventKey;
        renderInspector();
        renderTimeline();
      });

      const primary = document.createElement("div");
      primary.className = "timeline-primary";

      const eventType = document.createElement("p");
      eventType.className = "timeline-tool";
      eventType.textContent =
        row.toolName === null
          ? row.eventTypeLabel
          : `${row.eventTypeLabel} / ${row.toolName}`;

      const meta = document.createElement("p");
      meta.className = "timeline-meta";
      meta.textContent =
        row.summary === null
          ? `#${row.eventSeq} at ${row.timestampLabel}`
          : `#${row.eventSeq} at ${row.timestampLabel} · ${row.summary}`;
      primary.append(eventType, meta);

      const badges = document.createElement("div");
      badges.className = "timeline-badges";

      const eventBadge = document.createElement("span");
      eventBadge.className = "timeline-badge";
      eventBadge.dataset.kind = "event";
      eventBadge.textContent = row.eventTypeLabel;
      badges.append(eventBadge);

      for (const indicator of row.safetyIndicators) {
        const indicatorBadge = document.createElement("span");
        indicatorBadge.className = "timeline-badge";
        indicatorBadge.dataset.kind = indicator.includes("redacted")
          ? "redaction"
          : "truncation";
        indicatorBadge.textContent = indicator;
        badges.append(indicatorBadge);
      }

      button.append(primary, badges);
      item.append(button);
      return item;
    }),
  );
}

function renderInspector() {
  const selectedEvent = selectedRunView.events.find(
    (event) => createRunEventKey(event) === selectedEventKey,
  );

  inspectorEmpty.hidden = selectedEvent !== undefined;

  if (selectedEvent === undefined) {
    inspectorHeader.textContent = "Select a timeline event";
    inspectorMeta.textContent =
      "Tool input, output, and error payloads appear here with safety markers.";
    renderPayloadSlot(inspectorInput, "Input payload", undefined, undefined);
    renderPayloadSlot(inspectorOutput, "Output payload", undefined, undefined);
    renderPayloadSlot(inspectorError, "Error payload", undefined, undefined);
    renderFinalAnswer(undefined);
    return;
  }

  inspectorHeader.textContent = formatInspectorHeader(selectedEvent);
  inspectorMeta.textContent = `run_id ${selectedEvent.run_id} · event_seq ${selectedEvent.event_seq} · ${selectedEvent.ts}`;

  renderPayloadSlot(
    inspectorInput,
    "Input payload",
    selectedEvent.tool_input,
    selectedEvent.safety.tool_input,
  );
  renderPayloadSlot(
    inspectorOutput,
    "Output payload",
    selectedEvent.tool_output,
    selectedEvent.safety.tool_output,
  );
  renderPayloadSlot(
    inspectorError,
    "Error payload",
    selectedEvent.error_output,
    selectedEvent.safety.error_output,
  );
  renderFinalAnswer(selectedEvent.final_answer);
}

function syncDurationTimer() {
  if (state.phase === "running" && selectedRunView.kind === "live") {
    if (durationTimer === null) {
      durationTimer = window.setInterval(() => {
        renderTimeline();
      }, 200);
    }
    return;
  }

  if (durationTimer !== null) {
    window.clearInterval(durationTimer);
    durationTimer = null;
  }
}

function openRunStream(runId: string) {
  streamSubscription = subscribeToRunEvents(runId, {
    onRunState: (event) => {
      dispatch({
        type: "run_state_received",
        event,
      });
    },
    onRetrievalAction: (event) => {
      dispatch({
        type: "retrieval_action_received",
        event,
      });
    },
    onToolCall: (event) => {
      dispatch({
        type: "tool_call_received",
        event,
      });
    },
    onRunComplete: (event) => {
      dispatch({
        type: "run_completed",
        event,
      });
      void refreshRunHistory({ selectRunId: event.runId });
      closeRunStream();
    },
    onRunError: (event) => {
      dispatch({
        type: "run_error_received",
        event,
      });
      void refreshRunHistory({ selectRunId: event.runId });
      closeRunStream();
    },
    onInvalidEvent: () => {
      dispatch({
        type: "run_failed",
        message: "Run stream returned an invalid event.",
      });
      closeRunStream();
    },
    onTransportError: () => {
      if (state.phase === "running") {
        runDetails.textContent =
          "Connection lost. Waiting for terminal run update.";
      }
    },
  });
}

function closeRunStream() {
  streamSubscription?.close();
  streamSubscription = null;
}

async function refreshRunHistory(options: {
  selectLatest?: boolean;
  selectRunId?: string;
  preserveSelection?: boolean;
} = {}) {
  historyRefreshInFlight = true;
  historyStatus.textContent = "Refreshing stored run history.";
  render();

  try {
    const response = await fetch("/api/runs/history");
    const payload = parseRunHistoryListResponse(await response.json());
    historyRuns = payload.runs;

    historyStatus.textContent =
      historyRuns.length === 0
        ? "No stored runs yet. Start a run or load the preview."
        : `${historyRuns.length} runs available. Select one to inspect answer and trace.`;

    const preferredRunId =
      options.selectRunId ??
      (options.preserveSelection ? selectedRunView.runId : null) ??
      (options.selectLatest ? historyRuns[0]?.runId ?? null : null);

    if (
      preferredRunId !== null &&
      historyRuns.some((run) => run.runId === preferredRunId)
    ) {
      await loadRunHistoryDetail(preferredRunId);
    } else if (historyRuns.length === 0 && selectedRunView.kind === "history") {
      setSelectedRunView(createEmptyRunView());
    }
  } catch (error: unknown) {
    historyStatus.textContent =
      error instanceof Error
        ? error.message
        : "Failed to refresh stored run history.";
  } finally {
    historyRefreshInFlight = false;
    render();
  }
}

async function loadRunHistoryDetail(runId: string) {
  const response = await fetch(`/api/runs/${encodeURIComponent(runId)}/history`);
  const snapshot = parseRunHistoryRunSnapshot(await response.json());
  setSelectedRunView(fromHistorySnapshot(snapshot));
  render();
}

function syncSelectedRunViewFromState() {
  if (selectedRunView.kind !== "live") {
    return;
  }

  if (state.activeRunId === null) {
    selectedRunView = createEmptyRunView();
    selectedEventKey = null;
    return;
  }

  const nextEvents = parseOrderedRunEventList(state.runEvents);
  const nextSelectedKey = resolveSelectedEventKey(nextEvents, selectedEventKey);

  selectedRunView = {
    kind: "live",
    runId: state.activeRunId,
    finalAnswer: state.finalAnswer,
    events: nextEvents,
    retention: null,
    updatedAt: nextEvents.at(-1)?.ts ?? null,
    label: "Current live run",
  };
  selectedEventKey = nextSelectedKey;
}

function setSelectedRunView(view: SelectedRunView) {
  selectedRunView = {
    ...view,
    events: parseOrderedRunEventList(view.events),
  };
  selectedEventKey = resolveSelectedEventKey(
    selectedRunView.events,
    selectedEventKey,
  );
}

function resolveSelectedEventKey(
  events: CanonicalRunEvent[],
  currentKey: string | null,
): string | null {
  if (
    currentKey !== null &&
    events.some((event) => createRunEventKey(event) === currentKey)
  ) {
    return currentKey;
  }

  const latestEvent = events.at(-1);
  return latestEvent === undefined ? null : createRunEventKey(latestEvent);
}

function createEmptyRunView(): SelectedRunView {
  return {
    kind: "empty",
    runId: null,
    finalAnswer: null,
    events: [],
    retention: null,
    updatedAt: null,
    label: "No run selected",
  };
}

function fromHistorySnapshot(snapshot: RunHistoryRunSnapshot): SelectedRunView {
  return {
    kind: "history",
    runId: snapshot.runId,
    finalAnswer: snapshot.finalAnswer,
    events: snapshot.events,
    retention: snapshot.retention,
    updatedAt: snapshot.updatedAt,
    label: "Stored run history",
  };
}

function renderPayloadSlot(
  container: HTMLElement,
  heading: string,
  payload: unknown,
  safety: CanonicalRunEvent["safety"]["tool_input"] | undefined,
) {
  container.replaceChildren();

  const title = document.createElement("p");
  title.className = "payload-heading";
  title.textContent = heading;
  container.append(title);

  if (payload === undefined) {
    const empty = document.createElement("p");
    empty.className = "payload-empty";
    empty.textContent = "No payload for this event.";
    container.append(empty);
    return;
  }

  const markers = document.createElement("div");
  markers.className = "payload-markers";

  if (safety?.redaction.active) {
    markers.append(
      createSignalBadge("Redaction", safety.redaction.paths, safety.redaction.reason),
    );
  }

  if (safety?.truncation.active) {
    markers.append(
      createSignalBadge(
        "Truncation",
        safety.truncation.paths,
        safety.truncation.omitted_bytes === undefined
          ? safety.truncation.reason
          : `${safety.truncation.omitted_bytes} bytes omitted`,
      ),
    );
  }

  if (markers.childElementCount > 0) {
    container.append(markers);
  }

  const pre = document.createElement("pre");
  pre.className = "payload-json";
  pre.textContent = JSON.stringify(payload, null, 2);
  container.append(pre);
}

function renderFinalAnswer(answer: string | undefined) {
  inspectorFinalAnswer.replaceChildren();

  const title = document.createElement("p");
  title.className = "payload-heading";
  title.textContent = "Final answer";
  inspectorFinalAnswer.append(title);

  const body = document.createElement("p");
  body.className = answer === undefined ? "payload-empty" : "payload-answer";
  body.textContent = answer ?? "No final answer on this event.";
  inspectorFinalAnswer.append(body);
}

function renderAnswerSummary(answerView: ReturnType<typeof resolveRunAnswer>) {
  finalAnswer.replaceChildren();
  sourceList.replaceChildren();

  const body = document.createElement("p");
  body.className = "answer-value";

  if (answerView.structuredAnswer === null) {
    body.textContent = answerView.text ?? "No final answer stored for this run.";
  } else {
    for (const segment of segmentStructuredAnswer(
      answerView.structuredAnswer,
      answerView.sources,
    )) {
      if (segment.kind === "text") {
        body.append(segment.text);
        continue;
      }

      const link = document.createElement("a");
      link.className = "answer-citation";
      link.href = segment.citation.url;
      link.target = "_blank";
      link.rel = "noreferrer";
      link.title = segment.source?.title ?? segment.citation.title;
      link.textContent = segment.text;
      body.append(link);

      const marker = document.createElement("sup");
      marker.className = "answer-citation-index";
      marker.textContent = `[${segment.citationNumber}]`;
      body.append(marker);
    }
  }

  finalAnswer.append(body);

  if (answerView.sources.length === 0) {
    const empty = document.createElement("p");
    empty.className = "source-empty";
    empty.textContent = "No sources were stored for this run.";
    sourceList.append(empty);
    return;
  }

  const list = document.createElement("ol");
  list.className = "source-list";

  for (const [index, source] of answerView.sources.entries()) {
    const item = document.createElement("li");
    item.className = "source-item";

    const link = document.createElement("a");
    link.className = "source-link";
    link.href = source.url;
    link.target = "_blank";
    link.rel = "noreferrer";
    link.textContent = `[${index + 1}] ${source.title}`;

    const snippet = document.createElement("p");
    snippet.className = "source-snippet";
    snippet.textContent = source.snippet;

    item.append(link, snippet);
    list.append(item);
  }

  sourceList.append(list);
}

function describeRetention(retention: RunHistoryRetentionMetadata | null): string {
  if (retention === null) {
    return "Live runs update continuously. Stored retention metadata appears after history is persisted.";
  }

  const notes: string[] = [];

  if (retention.eventsDropped > 0) {
    notes.push(`${retention.eventsDropped} older events dropped`);
  }

  if (retention.payloadTruncations.length > 0) {
    notes.push(`${retention.payloadTruncations.length} payloads truncated`);
  }

  if (retention.duplicateEventsIgnored > 0) {
    notes.push(`${retention.duplicateEventsIgnored} duplicates ignored`);
  }

  if (retention.outOfOrderEventsRejected > 0) {
    notes.push(`${retention.outOfOrderEventsRejected} out-of-order events rejected`);
  }

  return notes.length === 0
    ? `Bounded to ${retention.maxRuns} runs, ${retention.maxEventsPerRun} events per run, and ${retention.maxPayloadBytes} bytes per event payload.`
    : `Bounds active: ${notes.join("; ")}.`;
}

function formatDateTime(timestamp: string): string {
  const parsed = new Date(timestamp);

  if (Number.isNaN(parsed.getTime())) {
    return timestamp;
  }

  return parsed.toLocaleString([], {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function createSignalBadge(
  label: string,
  paths: string[],
  detail: string | undefined,
): HTMLElement {
  const badge = document.createElement("p");
  badge.className = "payload-signal";
  badge.textContent = `${label}: ${paths.length > 0 ? paths.join(", ") : "applied"}${
    detail ? ` (${detail})` : ""
  }`;
  return badge;
}

function requireElement<TElement extends HTMLElement>(id: string): TElement {
  const element = document.getElementById(id);
  if (!(element instanceof HTMLElement)) {
    throw new Error(`Missing required element: ${id}`);
  }

  return element as TElement;
}

function createPreviewEvents(): CanonicalRunEvent[] {
  return parseOrderedRunEventList([
    {
      run_id: "preview-run",
      event_seq: 0,
      event_type: "run_started",
      ts: "2026-03-17T12:00:00.000Z",
      tool_input: {
        prompt: "Compare retrieval SDKs and highlight reliability risks.",
      },
      safety: createEmptyRunEventSafety(),
    },
    {
      run_id: "preview-run",
      event_seq: 1,
      event_type: "research_planning_started",
      ts: "2026-03-17T12:00:00.500Z",
      progress: {
        stage: "planning",
        message: "Sketching the retrieval plan and selecting initial source paths.",
      },
      tool_input: {
        prompt: "Compare retrieval SDKs and highlight reliability risks.",
      },
      safety: createEmptyRunEventSafety(),
    },
    {
      run_id: "preview-run",
      event_seq: 2,
      event_type: "research_search_started",
      ts: "2026-03-17T12:00:00.700Z",
      progress: {
        stage: "search",
        message: "Searching and reranking candidate sources.",
      },
      tool_input: {
        query: "retrieval sdk reliability release notes",
      },
      safety: createEmptyRunEventSafety(),
    },
    {
      run_id: "preview-run",
      event_seq: 3,
      event_type: "research_sources_expanded",
      ts: "2026-03-17T12:00:00.800Z",
      progress: {
        stage: "source_expansion",
        message: "Collecting broad coverage from search before targeted crawling.",
        completed: 1,
        total: 2,
      },
      tool_output: {
        strategy: "search-first",
        sourceCount: 2,
      },
      safety: createEmptyRunEventSafety(),
    },
    {
      run_id: "preview-run",
      event_seq: 4,
      event_type: "tool_call_started",
      ts: "2026-03-17T12:00:01.000Z",
      tool_name: "web_search",
      tool_call_id: "tool-success",
      tool_input: {
        query: "retrieval sdk reliability release notes",
        headers: {
          authorization: "[Redacted]",
        },
      },
      safety: {
        ...createEmptyRunEventSafety(),
        tool_input: {
          redaction: {
            active: true,
            paths: ["headers.authorization"],
            reason: "secret",
          },
          truncation: {
            active: false,
            paths: [],
          },
        },
      },
    },
    {
      run_id: "preview-run",
      event_seq: 5,
      event_type: "tool_call_succeeded",
      ts: "2026-03-17T12:00:02.000Z",
      tool_name: "web_search",
      tool_call_id: "tool-success",
      tool_output: {
        results: [
          {
            title: "Retrieval SDK release notes",
            snippet: "Top result snippet kept.",
          },
          {
            title: "Long provider payload",
            snippet: "[Truncated]",
          },
        ],
      },
      safety: {
        ...createEmptyRunEventSafety(),
        tool_output: {
          redaction: {
            active: false,
            paths: [],
          },
          truncation: {
            active: true,
            paths: ["results.1.snippet"],
            omitted_bytes: 512,
          },
        },
      },
    },
    {
      run_id: "preview-run",
      event_seq: 6,
      event_type: "research_crawl_started",
      ts: "2026-03-17T12:00:02.300Z",
      progress: {
        stage: "crawl",
        message: "Selecting an objective-driven page crawl.",
      },
      tool_input: {
        url: "https://example.com/private",
      },
      safety: createEmptyRunEventSafety(),
    },
    {
      run_id: "preview-run",
      event_seq: 7,
      event_type: "tool_call_failed",
      ts: "2026-03-17T12:00:03.000Z",
      tool_name: "open_url",
      tool_call_id: "tool-failure",
      tool_input: {
        url: "https://example.com/private",
        apiKey: "[Redacted]",
      },
      error_output: {
        code: "POLICY_DENIED",
        message: "Fetch blocked by policy.",
        token: "[Redacted]",
      },
      safety: {
        ...createEmptyRunEventSafety(),
        tool_input: {
          redaction: {
            active: true,
            paths: ["apiKey"],
            reason: "secret",
          },
          truncation: {
            active: false,
            paths: [],
          },
        },
        error_output: {
          redaction: {
            active: true,
            paths: ["token"],
            reason: "secret",
          },
          truncation: {
            active: false,
            paths: [],
          },
        },
      },
    },
    {
      run_id: "preview-run",
      event_seq: 8,
      event_type: "research_verification_started",
      ts: "2026-03-17T12:00:03.250Z",
      progress: {
        stage: "verification",
        message: "Validating the strongest supporting evidence before synthesis.",
        completed: 2,
        total: 2,
      },
      tool_output: {
        sourcesConsidered: 2,
      },
      safety: createEmptyRunEventSafety(),
    },
    {
      run_id: "preview-run",
      event_seq: 9,
      event_type: "research_synthesis_started",
      ts: "2026-03-17T12:00:03.500Z",
      progress: {
        stage: "synthesis",
        message: "Combining retrieved evidence into a concise answer.",
        completed: 2,
        total: 2,
      },
      tool_output: {
        sourcesConsidered: 2,
        conflictingClaims: 0,
      },
      safety: createEmptyRunEventSafety(),
    },
    {
      run_id: "preview-run",
      event_seq: 10,
      event_type: "final_answer_generated",
      ts: "2026-03-17T12:00:04.000Z",
      final_answer:
        "Search succeeded, crawl failed safely, and the agent kept the error visible.",
      tool_output: {
        answer: {
          text: "Search succeeded, crawl failed safely, and the agent kept the error visible.",
          citations: [
            {
              source_id: "release-notes",
              title: "Retrieval SDK release notes",
              url: "https://example.com/release-notes",
              start_index: 0,
              end_index: 16,
            },
            {
              source_id: "incident-summary",
              title: "Provider incident summary",
              url: "https://status.example.com/incidents/123",
              start_index: 18,
              end_index: 43,
            },
          ],
        },
        sources: [
          {
            source_id: "release-notes",
            title: "Retrieval SDK release notes",
            url: "https://example.com/release-notes",
            snippet: "Primary evidence for the reliability notes.",
          },
          {
            source_id: "incident-summary",
            title: "Provider incident summary",
            url: "https://status.example.com/incidents/123",
            snippet: "Operational context for the failure mode.",
          },
        ],
      },
      safety: createEmptyRunEventSafety(),
    },
  ]);
}

function formatInspectorHeader(event: CanonicalRunEvent): string {
  switch (event.event_type) {
    case "research_planning_started":
      return "planning";
    case "research_search_started":
      return "search";
    case "research_crawl_started":
      return "crawl";
    case "research_verification_started":
      return "verification";
    case "research_sources_expanded":
      return "source expansion";
    case "research_synthesis_started":
      return "synthesis";
    default:
      return event.tool_name
        ? `${event.event_type} / ${event.tool_name}`
        : event.event_type;
  }
}
