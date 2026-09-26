import QtQuick
import QtQuick.Controls
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import qs.Commons
import qs.Ui

BarWidget {
  id: root
  moduleName: "ask-omar.assistant"

  property bool opened: false
  property bool settingsExpanded: false
  property bool busy: false
  property string busyLabel: ""
  property string requestState: "idle"
  property string activityText: "Thinking"
  property int activityDots: 0
  property string queryText: ""
  property string replyText: ""
  property string submittedQuery: ""
  property string pendingActionId: ""
  property string failedQuery: ""
  property string failedActionId: ""
  property bool failedReset: false
  property string responseText: ""
  property string errorText: ""
  property bool resultVisible: false
  property bool actionsExpanded: false
  property bool clearHistoryPending: false
  // "chat" | "answers" | "answer" — Past answers is a drill-down over the live chat, never a second chat.
  property string panelView: "chat"
  property string historyQueryText: ""
  property string historyEntryKind: ""
  property string historyItemResponse: ""
  property string retryWarning: ""
  property var historyEntries: []
  property var conversationTurns: []
  property var historyPreview: null
  property bool replyExpanded: false
  property bool restoringDraft: false
  // Latest exchange by default; full Pi thread only when the user asks for it.
  property bool threadExpanded: false
  property bool freshNotice: false
  property bool answersFromSettings: false
  property double lastAnswerAt: 0
  readonly property bool historyExpanded: panelView === "answers" || panelView === "answer"
  readonly property bool historyItemOpen: panelView === "answer"
  readonly property bool showBackToChat: historyExpanded && (conversationTurns.length > 0 || busy)
  readonly property bool showBackToSettings: historyExpanded && answersFromSettings
  readonly property int lastAskIndex: {
    for (var i = conversationTurns.length - 1; i >= 0; i--)
      if (String(conversationTurns[i].role || "") === "you") return i
    return conversationTurns.length > 0 ? 0 : -1
  }
  readonly property var visibleTurns: {
    if ((!resultVisible && !busy) || lastAskIndex < 0) return []
    // Allow once is the only job — don't also stack the ask above it.
    if (busy && pendingConfirmation !== null) return []
    if (threadExpanded) return conversationTurns
    // Working: show the ask in flight. Answered: Omar's reply only — not the question.
    if (busy) return conversationTurns.slice(lastAskIndex)
    var out = []
    for (var i = lastAskIndex + 1; i < conversationTurns.length; i++)
      out.push(conversationTurns[i])
    return out
  }
  readonly property int foldedAskCount: {
    if (threadExpanded) return 0
    var limit = ((!resultVisible && !busy) || lastAskIndex < 0)
      ? conversationTurns.length
      : lastAskIndex
    var count = 0
    for (var i = 0; i < limit; i++)
      if (String(conversationTurns[i].role || "") === "you") count++
    return count
  }
  readonly property int rememberedAskCount: {
    var count = 0
    for (var i = 0; i < conversationTurns.length; i++)
      if (String(conversationTurns[i].role || "") === "you") count++
    return count
  }
  // Compact chrome under the bar on focus (New / settings / X).
  readonly property bool showResultPanel: true
  // Show chat / Hide chat — live thread, not Past answers.
  readonly property bool showChatToggle: !busy && !settingsExpanded && !historyExpanded
    && resultVisible && (threadExpanded || conversationTurns.length > visibleTurns.length)
  property bool copied: false
  property bool copyFailed: false
  property string micState: "idle"
  property bool voxtypeAvailable: true
  property string healthStatus: "unknown"
  property string healthMessage: ""
  property string healthProvider: ""
  property string healthModel: ""
  property string healthThinking: ""
  property string healthSystemAccess: "ask"
  property bool healthChecked: false
  property bool backendInstalled: true
  property string recapText: ""
  property bool showSlowHint: false
  property var pendingConfirmation: null
  // Only auto-open the panel the first time we see a given confirmation id —
  // later activity polls must not undo a click-away dismiss.
  property string surfacedConfirmationId: ""
  // While Allow/Deny is in flight, ignore activity echoes of the same id and
  // keep a snapshot so a failed confirm can restore the prompt.
  property string confirmInFlightId: ""
  property var confirmSnapshot: null
  property bool scratchpadMode: false
  property bool restoringScratchpad: false
  property bool scratchpadDeletePending: false
  property string scratchpadText: ""
  property var scratchpadNotes: [""]
  property int scratchpadNoteIndex: 0
  property bool screenshotMenuExpanded: false
  property string screenshotMode: "smart"
  property string screenshotTarget: "assistant"
  property bool recordingActive: false
  property string recordingTarget: "assistant"
  property bool aiSettingsHelpExpanded: false
  property var availableModels: []
  property var thinkingLevels: ["off", "minimal", "low", "medium", "high", "xhigh", "max"]
  property string modelsMessage: ""
  property bool modelsLoading: false
  property bool agentSaving: false
  property string agentSaveMessage: ""
  property bool accessSaving: false
  property bool fullAccessPending: false
  property string accessSaveMessage: ""
  property bool restarting: false
  property bool quitting: false
  property bool quitRequested: false
  property string draftSaveState: "saved"
  property string draftSaveError: ""
  property int draftVersion: 0
  property int savedDraftVersion: 0
  property string scratchpadSaveState: "saved"
  property string scratchpadSaveError: ""
  property int scratchpadVersion: 0
  property int savedScratchpadVersion: 0
  property bool hideFromBarPending: false
  property bool hideAfterQuit: false
  property bool micPointerActive: false
  property string micPointerInitialState: "idle"
  property double micPointerStartedAt: 0
  property real fieldX: 0
  property real fieldY: 0
  property bool openPending: false
  property bool settingsPending: false
  property bool historyPending: false

  readonly property color foreground: bar ? bar.barForeground : Color.foreground
  readonly property color accent: bar ? bar.urgent : Color.accent
  readonly property int configuredWidth: Math.max(260, Number(setting("width", 420)) || 420)
  readonly property int iconWidth: Math.max(24, barSize)
  readonly property var ownScreen: root.QsWindow.window ? root.QsWindow.window.screen : null
  readonly property var availableScreens: {
    var screens = []
    for (var i = 0; i < Quickshell.screens.length; i++) {
      var screen = Quickshell.screens[i]
      if (screen.width > 0 && screen.height > 0) screens.push(screen)
    }
    return screens
  }
  readonly property var selectedDisplayNames: {
    var configured = setting("displays", [])
    if (Array.isArray(configured) && configured.length > 0) return configured
    var all = []
    for (var i = 0; i < availableScreens.length; i++) all.push(String(availableScreens[i].name))
    return all
  }
  readonly property bool hiddenFromBar: setting("hiddenFromBar", false) === true
  readonly property bool controlInstance: !ownScreen || availableScreens.length === 0
    || ownScreen.name === availableScreens[0].name
  readonly property bool shownOnOwnDisplay: !!ownScreen && selectedDisplayNames.indexOf(String(ownScreen.name)) !== -1
  readonly property bool showIdleNotices: !busy && !resultVisible && conversationTurns.length === 0
    && !historyExpanded && !settingsExpanded && !freshNotice
  readonly property bool showChatThread: !settingsExpanded && !historyExpanded
    && (visibleTurns.length > 0 || busy || errorText !== "" || pendingConfirmation !== null)
  // Reply only after an answer lands — never while Working.
  readonly property bool showReplyChrome: showChatThread && !busy && pendingConfirmation === null
  readonly property bool showAnswersChrome: showBackToChat || (historyItemOpen && historyPreview !== null)
  readonly property bool showPanelComposer: showReplyChrome && replyExpanded
  readonly property bool showReplyButton: showReplyChrome && !replyExpanded

  visible: shownOnOwnDisplay && !hiddenFromBar
  implicitWidth: vertical ? barSize : configuredWidth
  implicitHeight: barSize

  component CaptureMenuButton: BorderSurface {
    id: captureAction

    property string text: ""
    property color foreground: Color.foreground
    property color accent: Color.accent
    signal clicked()

    implicitHeight: captureLabel.implicitHeight + Style.space(14)
    radius: Style.cornerRadius
    color: captureMouse.pressed ? Style.pressedFillFor(foreground, accent)
      : captureMouse.containsMouse ? Style.hoverFillFor(foreground, accent)
      : "transparent"
    borderSpec: captureMouse.containsMouse
      ? Border.controlSpec("hover-cursor", foreground, accent)
      : Border.none()
    opacity: enabled ? 1 : 0.45
    activeFocusOnTab: true
    Accessible.role: Accessible.Button
    Accessible.name: text

    Keys.onReturnPressed: if (enabled) clicked()
    Keys.onEnterPressed: if (enabled) clicked()
    Keys.onSpacePressed: if (enabled) clicked()

    Text {
      textFormat: Text.PlainText
      id: captureLabel
      anchors.right: parent.right
      anchors.rightMargin: Style.space(10)
      anchors.verticalCenter: parent.verticalCenter
      text: captureAction.text
      color: captureAction.foreground
      font.family: root.bar ? root.bar.fontFamily : Style.font.family
      font.pixelSize: Style.font.body
    }

    MouseArea {
      id: captureMouse
      anchors.fill: parent
      enabled: captureAction.enabled
      hoverEnabled: true
      cursorShape: Qt.PointingHandCursor
      onClicked: captureAction.clicked()
    }
  }

  component MicButton: BorderSurface {
    id: micButton

    property string iconText: ""
    property string tooltipText: ""
    property color foreground: Color.foreground
    property color hoverColor: foreground
    property string fontFamily: Style.font.family
    property real size: Math.max(Style.space(22), Style.font.icon + Style.spacing.sm * 2)
    property bool focusable: false
    signal clicked()
    signal pointerPressed()
    signal pointerReleased()

    activeFocusOnTab: focusable
    implicitWidth: size
    implicitHeight: size
    radius: Style.cornerRadius
    color: micMouse.containsMouse && enabled
      ? Style.hoverFillFor(hoverColor, hoverColor)
      : "transparent"
    borderSpec: focusable && activeFocus
      ? Border.controlSpec("focus", hoverColor, hoverColor)
      : Border.none()

    Keys.onReturnPressed: if (focusable) clicked()
    Keys.onEnterPressed: if (focusable) clicked()
    Keys.onSpacePressed: if (focusable) clicked()

    Text {
      textFormat: Text.PlainText
      anchors.centerIn: parent
      text: micButton.iconText
      color: micButton.enabled ? micButton.foreground : Qt.darker(micButton.foreground, 2.0)
      font.family: micButton.fontFamily
      font.pixelSize: Style.font.icon
    }

    MouseArea {
      id: micMouse
      anchors.fill: parent
      enabled: micButton.enabled
      hoverEnabled: true
      cursorShape: micButton.enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
      onPressed: {
        if (micButton.focusable) micButton.forceActiveFocus()
        micButton.pointerPressed()
      }
      onReleased: micButton.pointerReleased()
      onCanceled: micButton.pointerReleased()
    }

    PanelToolTip {
      visible: micButton.tooltipText !== "" && micMouse.containsMouse
      text: micButton.tooltipText
      fontFamily: micButton.fontFamily
    }
  }

  function displayLabel(screen) {
    if (!screen) return "Unknown display"
    var model = String(screen.model || "").trim()
    var connector = String(screen.name || "").trim()
    return model !== "" && model !== connector ? model + " (" + connector + ")" : connector
  }

  function displayLabelForName(name) {
    for (var i = 0; i < availableScreens.length; i++) {
      if (String(availableScreens[i].name) === String(name)) return displayLabel(availableScreens[i])
    }
    return String(name)
  }

  function shownOnSummary() {
    var labels = []
    for (var i = 0; i < selectedDisplayNames.length; i++)
      labels.push(displayLabelForName(selectedDisplayNames[i]))
    return "Shown on: " + (labels.length > 0 ? labels.join(", ") : "No displays")
  }

  function updateGeometry() {
    var window = root.QsWindow.window
    if (!window || !window.contentItem) return
    var point = root.mapToItem(window.contentItem, 0, 0)
    fieldX = point.x
    fieldY = point.y
  }

  function appendConversationTurn(role, text) {
    var value = String(text || "")
    if (value === "") return
    conversationTurns = conversationTurns.concat([{ role: String(role || "omar"), text: value }])
    resultVisible = true
    scrollChatToEnd()
  }

  function clearConversationTurns() {
    conversationTurns = []
    replyExpanded = false
    historyPreview = null
    historyItemResponse = ""
    threadExpanded = false
  }

  function backToChat() {
    panelView = "chat"
    historyPreview = null
    historyItemResponse = ""
    historyQueryText = ""
    historyEntryKind = ""
    retryWarning = ""
    clearHistoryPending = false
    replyExpanded = false
    threadExpanded = false
    answersFromSettings = false
    settingsExpanded = false
    resultVisible = conversationTurns.length > 0 || busy || pendingConfirmation !== null
    if (busy) loadActivity()
    scrollChatToEnd()
    Qt.callLater(function() { root.focusComposer() })
  }

  function backToSettings() {
    panelView = "chat"
    historyPreview = null
    historyItemResponse = ""
    historyQueryText = ""
    historyEntryKind = ""
    retryWarning = ""
    clearHistoryPending = false
    replyExpanded = false
    answersFromSettings = false
    resultVisible = false
    settingsExpanded = true
    Qt.callLater(function() {
      if (historyButton.visible) historyButton.forceActiveFocus()
    })
  }

  function backFromAnswers() {
    if (answersFromSettings) backToSettings()
    else if (conversationTurns.length > 0) backToChat()
    else {
      panelView = "chat"
      historyPreview = null
      historyItemResponse = ""
      answersFromSettings = false
      resultVisible = false
    }
  }

  function toggleThread() {
    threadExpanded = !threadExpanded
    if (threadExpanded) resultVisible = true
    scrollChatToEnd()
  }

  function openAnswersList(fromSettings) {
    answersFromSettings = fromSettings === true
    panelView = "answers"
    historyPreview = null
    historyItemResponse = ""
    historyQueryText = ""
    historyEntryKind = ""
    retryWarning = ""
    clearHistoryPending = false
    replyExpanded = false
    actionsExpanded = false
    settingsExpanded = false
    resultVisible = false
    loadHistory()
  }

  function relativeTime(epochSeconds) {
    var at = Number(epochSeconds || 0)
    if (!(at > 0)) return ""
    var sec = Math.max(0, Math.floor(Date.now() / 1000 - at))
    if (sec < 60) return "now"
    if (sec < 3600) return Math.floor(sec / 60) + "m"
    if (sec < 86400) return Math.floor(sec / 3600) + "h"
    if (sec < 172800) return "Yesterday"
    return Math.floor(sec / 86400) + "d"
  }

  function openReply() {
    if (!showReplyChrome || busy) return
    panelView = "chat"
    historyPreview = null
    historyItemResponse = ""
    replyExpanded = true
    // Keep any in-progress reply draft — do not wipe on reopen.
    Qt.callLater(function() {
      if (panelComposerField.visible) panelComposerField.forceActiveFocus()
    })
  }

  function collapseReply() {
    replyExpanded = false
    replyText = ""
  }

  function clearPendingConfirmation() {
    pendingConfirmation = null
    surfacedConfirmationId = ""
    confirmInFlightId = ""
    confirmSnapshot = null
  }

  function handleConfirm(raw) {
    var inflightId = confirmInFlightId
    var snapshot = confirmSnapshot
    confirmInFlightId = ""
    confirmSnapshot = null
    var result
    try {
      result = JSON.parse(String(raw || "").trim())
    } catch (error) {
      errorText = "Ask Omar could not send that approval."
      if (snapshot) {
        pendingConfirmation = snapshot
        resultVisible = true
      }
      return
    }
    if (result.ok) return
    var message = String(result.error || "Ask Omar could not send that approval.")
    if (String(result.error_code || "") === "stale_confirmation")
      message = "That approval request is no longer pending."
    errorText = message
    // Restore the prompt only when the same request is still the one we tried.
    if (snapshot && String(snapshot.id || "") === inflightId) {
      pendingConfirmation = snapshot
      resultVisible = true
      if (!opened) {
        opened = true
        updateGeometry()
      }
    }
  }

  function scrollChatToEnd() {
    Qt.callLater(function() {
      if (!resultFlickable.visible) return
      var maxY = Math.max(0, resultFlickable.contentHeight - resultFlickable.height)
      resultFlickable.contentY = maxY
    })
  }

  function focusComposer() {
    // New questions and default focus stay in the menu-bar field. The panel
    // reply field only takes focus after an explicit Reply action.
    if (replyExpanded && showPanelComposer && panelComposerField.visible && panelComposerField.enabled)
      panelComposerField.forceActiveFocus()
    else
      queryField.forceActiveFocus()
  }

  function reveal() {
    updateGeometry()
    scratchpadMode = false
    settingsExpanded = false
    actionsExpanded = false
    panelView = "chat"
    historyPreview = null
    historyItemResponse = ""
    clearHistoryPending = false
    answersFromSettings = false
    threadExpanded = false
    freshNotice = false
    // Keep Working / Allow-once visible across a quick dismiss. Otherwise a short
    // grace keeps the last reply if you bounce out and back.
    var graceMs = 30000
    if (busy || pendingConfirmation !== null)
      resultVisible = true
    else if (conversationTurns.length > 0 && lastAnswerAt > 0 && (Date.now() - lastAnswerAt) < graceMs)
      resultVisible = true
    else
      resultVisible = false
    // Restore an unfinished reply draft after click-away (needs the panel
    // body visible so showReplyChrome / the composer can appear).
    if (!busy && pendingConfirmation === null && String(replyText || "").trim() !== "") {
      replyExpanded = true
      resultVisible = true
    }
    opened = true
    if (!healthChecked) checkHealth()
    if (busy) loadActivity()
    Qt.callLater(function() {
      root.updateGeometry()
      root.focusComposer()
    })
    // Layer-shell focus can settle after the first frame; re-assert the
    // menu-bar caret for new questions once the overlay is up.
    Qt.callLater(function() {
      if (root.opened && !root.scratchpadMode && !(root.showPanelComposer && panelComposerField.enabled))
        queryField.forceActiveFocus()
    })
  }

  function open() {
    quitting = false
    if (hiddenFromBar) updateSetting("hiddenFromBar", false)
    settingsPending = false
    historyPending = false
    if (serviceStartProcess.running) {
      openPending = true
      return
    }
    openPending = true
    serviceStartProcess.command = ["systemctl", "--user", "start", "ask-omar.service"]
    serviceStartProcess.running = true
  }

  function showSettings() {
    quitting = false
    if (hiddenFromBar) updateSetting("hiddenFromBar", false)
    settingsPending = true
    historyPending = false
    openPending = true
    if (serviceStartProcess.running) return
    serviceStartProcess.command = ["systemctl", "--user", "start", "ask-omar.service"]
    serviceStartProcess.running = true
  }

  function showHistory() {
    quitting = false
    if (hiddenFromBar) updateSetting("hiddenFromBar", false)
    if (opened) {
      openAnswersList()
      return
    }
    settingsPending = false
    historyPending = true
    openPending = true
    if (serviceStartProcess.running) return
    serviceStartProcess.command = ["systemctl", "--user", "start", "ask-omar.service"]
    serviceStartProcess.running = true
  }

  function toggleSettings() {
    settingsExpanded = !settingsExpanded
    fullAccessPending = false
    accessSaveMessage = ""
    panelView = "chat"
    historyPreview = null
    historyItemResponse = ""
    actionsExpanded = false
    resultVisible = false
    clearHistoryPending = false
    replyExpanded = false
    if (settingsExpanded) {
      checkHealth()
      loadModels()
    }
  }

  function updateSetting(name, value) {
    var entry = { id: root.moduleName }
    for (var key in root.settings) if (key !== "id" && key !== "allMonitors") entry[key] = root.settings[key]
    entry[name] = value
    root.settings = entry
    if (root.bar && root.bar.shell && typeof root.bar.shell.updateEntryInline === "function")
      root.bar.shell.updateEntryInline(root.moduleName, entry)
  }

  function toggleDisplay(name) {
    var next = selectedDisplayNames.slice()
    var index = next.indexOf(String(name))
    if (index === -1) next.push(String(name))
    else if (next.length > 1) next.splice(index, 1)
    updateSetting("displays", next)
  }

  function close(cancelVoice) {
    if (cancelVoice === undefined) cancelVoice = true
    if (cancelVoice && (micState === "recording" || micState === "transcribing") && bar)
      bar.run("voxtype record cancel")
    // Dismissing the panel is not Deny — an Allow-once prompt must survive a
    // click-away so you can reopen and approve. Use Deny / Stop / Escape to refuse.
    openPending = false
    settingsPending = false
    historyPending = false
    opened = false
    scratchpadMode = false
    settingsExpanded = false
    resultVisible = false
    actionsExpanded = false
    panelView = "chat"
    historyPreview = null
    historyItemResponse = ""
    clearHistoryPending = false
    replyExpanded = false
    screenshotMenuExpanded = false
    aiSettingsHelpExpanded = false
    fullAccessPending = false
    accessSaveMessage = ""
    hideFromBarPending = false
  }

  function quitApplication() {
    quitRequested = true
    draftSaveTimer.stop()
    scratchpadSaveTimer.stop()
    flushPendingSaves()
  }

  function flushPendingSaves() {
    if (!quitRequested) return
    if (draftSaveState === "error" || scratchpadSaveState === "error") {
      quitRequested = false
      hideAfterQuit = false
      if (!opened) {
        opened = true
        updateGeometry()
      }
      if (scratchpadSaveState === "error") scratchpadMode = true
      else errorText = draftSaveError
      return
    }
    if (draftSaveProcess.running || scratchpadSaveProcess.running) return
    if (draftVersion !== savedDraftVersion) {
      saveDraft()
      return
    }
    if (scratchpadVersion !== savedScratchpadVersion) {
      saveScratchpad()
      return
    }
    finishQuit()
  }

  function finishQuit() {
    quitRequested = false
    quitting = true
    openPending = false
    settingsPending = false
    historyPending = false
    if (pendingConfirmation) respondToConfirmation("Deny")
    else clearPendingConfirmation()
    activityTimer.stop()
    if (healthProcess.running) healthProcess.running = false
    if (draftLoadProcess.running) draftLoadProcess.running = false
    if (scratchpadLoadProcess.running) scratchpadLoadProcess.running = false
    quitProcess.command = ["systemctl", "--user", "stop", "ask-omar.service"]
    quitProcess.running = true
    close(false)
    if (hideAfterQuit) {
      hideAfterQuit = false
      updateSetting("hiddenFromBar", true)
    }
  }

  function hideFromBar() {
    if (!hideFromBarPending) {
      hideFromBarPending = true
      return
    }
    hideAfterQuit = true
    quitApplication()
  }

  function restartApplication() {
    if (restartProcess.running) return
    quitting = false
    restarting = true
    restartProcess.command = ["systemctl", "--user", "restart", "ask-omar.service"]
    restartProcess.running = true
  }

  function toggle() {
    if (opened) close()
    else open()
  }

  function loadHistory() {
    if (historyProcess.running) return
    historyProcess.command = ["ask-omar", "history"]
    historyProcess.running = true
  }

  function toggleHistory() {
    if (busy) return
    actionsExpanded = false
    clearHistoryPending = false
    replyExpanded = false
    if (historyExpanded) {
      backToChat()
      return
    }
    openAnswersList()
    Qt.callLater(function() { root.focusComposer() })
  }

  function showHistoryEntry(entry) {
    if (!entry || !entry.response) return
    // Document preview of one saved answer — never hijack the live thread or Copy buffer.
    historyPreview = entry
    historyQueryText = String(entry.query || "")
    historyEntryKind = String(entry.kind || "")
    historyItemResponse = String(entry.response || "")
    retryWarning = ""
    panelView = "answer"
    replyExpanded = false
    resultVisible = false
  }

  function clearHistoryPreview() {
    historyPreview = null
    historyItemResponse = ""
    historyQueryText = ""
    historyEntryKind = ""
    retryWarning = ""
    panelView = "answers"
  }

  function startStdinCommand(proc, argv, body) {
    proc.pendingStdin = String(body ?? "")
    proc.stdinEnabled = true
    proc.command = argv
    proc.running = true
  }

  // Python's len() counts a Unicode code point once; QML string.length counts
  // each half of an astral character separately. Match the backend limits.
  function characterCount(value) {
    var text = String(value || "")
    var count = 0
    for (var i = 0; i < text.length; i++) {
      var first = text.charCodeAt(i)
      if (first >= 0xd800 && first <= 0xdbff && i + 1 < text.length) {
        var second = text.charCodeAt(i + 1)
        if (second >= 0xdc00 && second <= 0xdfff) i++
      }
      count++
    }
    return count
  }

  function submit(text) {
    var value = String(text || "").trim()
    if (!value || busy || queryProcess.running) return
    if (characterCount(value) > 2000) {
      errorText = "Question exceeds 2,000 characters. Shorten it before sending."
      resultVisible = true
      return
    }
    if (aiUnavailable()) {
      resultVisible = conversationTurns.length > 0
      panelView = "chat"
      historyPreview = null
      historyItemResponse = ""
      settingsExpanded = false
      checkHealth()
      return
    }
    queryText = value
    submittedQuery = value
    pendingActionId = ""
    failedQuery = ""
    failedActionId = ""
    failedReset = false
    actionsExpanded = false
    panelView = "chat"
    historyPreview = null
    historyItemResponse = ""
    replyExpanded = false
    // One job while Working: never keep the full thread open mid-flight.
    threadExpanded = false
    freshNotice = false
    errorText = ""
    retryWarning = ""
    recapText = ""
    showSlowHint = false
    clearPendingConfirmation()
    appendConversationTurn("you", value)
    queryText = ""
    replyText = ""
    replyExpanded = false
    // Don't let a stale draft reappear in the bar while Working.
    draftSaveTimer.stop()
    saveDraft()
    requestState = "working"
    activityText = "Thinking"
    activityDots = 0
    busyLabel = "Working…"
    busy = true
    slowHintTimer.restart()
    startStdinCommand(queryProcess, ["ask-omar", "query", "--stdin"], value)
  }

  function runAction(actionId) {
    if (!actionId || busy || queryProcess.running) return
    submittedQuery = ""
    pendingActionId = String(actionId)
    failedQuery = ""
    failedActionId = ""
    failedReset = false
    resultVisible = false
    actionsExpanded = false
    panelView = "chat"
    historyPreview = null
    historyItemResponse = ""
    errorText = ""
    recapText = ""
    showSlowHint = false
    clearPendingConfirmation()
    requestState = "working"
    activityText = "Running action"
    activityDots = 0
    busyLabel = "Running action…"
    busy = true
    queryProcess.command = ["ask-omar", "action", String(actionId)]
    queryProcess.running = true
  }

  function retry() {
    if (failedReset) newConversation()
    else if (failedActionId !== "") runAction(failedActionId)
    else if (failedQuery !== "") submit(failedQuery)
  }

  function acceptField() {
    if (replyExpanded && showPanelComposer)
      submit(panelComposerField.text)
    else
      submit(queryField.text)
  }

  function copyResponse() {
    if (responseText === "" || copyProcess.running) return
    var selection = String(answerText.selectedText || "")
    var value = selection !== "" ? selection : responseText
    copyFailed = false
    copied = false
    startStdinCommand(copyProcess, ["wl-copy"], value)
  }

  function newConversation() {
    if (busy || newConversationProcess.running) return
    submittedQuery = ""
    pendingActionId = ""
    failedQuery = ""
    failedActionId = ""
    failedReset = false
    errorText = ""
    resultVisible = false
    actionsExpanded = false
    panelView = "chat"
    historyPreview = null
    historyItemResponse = ""
    threadExpanded = false
    freshNotice = false
    recapText = ""
    showSlowHint = false
    slowHintTimer.stop()
    requestState = "resetting"
    activityText = "Starting a new conversation"
    activityDots = 0
    busyLabel = "Starting a new conversation…"
    busy = true
    newConversationProcess.command = ["ask-omar", "new-conversation"]
    newConversationProcess.running = true
  }

  function handleNewConversation(raw) {
    busy = false
    requestState = "idle"
    busyLabel = ""
    var result
    try {
      result = JSON.parse(String(raw || "").trim())
    } catch (error) {
      failedReset = true
      errorText = "Ask Omar could not reset the conversation."
      return
    }
    if (!result.ok) {
      failedReset = true
      errorText = String(result.error || "Ask Omar could not reset the conversation.")
      return
    }
    failedReset = false
    queryText = ""
    responseText = ""
    historyEntries = []
    clearConversationTurns()
    errorText = ""
    resultVisible = false
    threadExpanded = false
    freshNotice = true
    Qt.callLater(function() { root.focusComposer() })
  }

  function handleHistory(raw) {
    var result
    try {
      result = JSON.parse(String(raw || "").trim())
    } catch (error) {
      historyEntries = []
      errorText = "Ask Omar could not read local history."
      panelView = "chat"
      historyPreview = null
      historyItemResponse = ""
      return
    }
    if (!result.ok || !result.history) {
      historyEntries = []
      errorText = String(result.error || "Ask Omar could not read local history.")
      panelView = "chat"
      historyPreview = null
      historyItemResponse = ""
      return
    }
    historyEntries = result.history
    Qt.callLater(function() {
      historyButton.forceActiveFocus()
    })
  }

  function clearHistory() {
    if (!historyExpanded || busy || historyEntries.length === 0) return
    if (!clearHistoryPending) {
      clearHistoryPending = true
      return
    }
    clearHistoryPending = false
    clearHistoryProcess.command = ["ask-omar", "clear-history"]
    clearHistoryProcess.running = true
  }

  function handleClearHistory(raw) {
    try {
      var result = JSON.parse(String(raw || "").trim())
      if (result.ok) {
        historyEntries = []
        errorText = ""
        panelView = "chat"
        historyPreview = null
        historyItemResponse = ""
        clearHistoryPending = false
      } else {
        errorText = String(result.error || "Ask Omar could not clear local history.")
      }
    } catch (error) {
      errorText = "Ask Omar could not clear local history."
    }
  }

  function camera() {
    if (recordingActive) stopRecording()
    else startScreenshot("smart")
  }

  function showScreenshotChoices() {
    updateGeometry()
    screenshotMenuExpanded = true
    checkRecording()
  }

  function startScreenshot(mode) {
    if (screenshotDelayTimer.running) return
    if (bar) {
      if (micState === "recording" || micState === "transcribing") bar.run("voxtype record cancel")
    }
    screenshotMode = mode
    screenshotTarget = scratchpadMode ? "scratchpad" : "assistant"
    screenshotMenuExpanded = false
    close(false)
    // Let the overlay disappear before launching Omarchy's detached picker.
    screenshotDelayTimer.interval = 200
    screenshotDelayTimer.restart()
  }

  function checkRecording() {
    if (recordingCheckProcess.running) return
    recordingCheckProcess.command = ["pgrep", "-f", "^gpu-screen-recorder"]
    recordingCheckProcess.running = true
  }

  function startRecording(fullscreen) {
    recordingTarget = scratchpadMode ? "scratchpad" : "assistant"
    screenshotMenuExpanded = false
    close(false)
    captureLauncher.command = [
      "ask-omar-capture",
      "record-start",
      fullscreen ? "fullscreen" : "region",
      recordingTarget
    ]
    captureLauncher.startDetached()
  }

  function stopRecording() {
    screenshotMenuExpanded = false
    recordingActive = false
    close(false)
    captureLauncher.command = ["ask-omar-capture", "record-stop", recordingTarget]
    captureLauncher.startDetached()
  }

  function openScratchpad() {
    quitting = false
    updateGeometry()
    scratchpadMode = true
    opened = true
    scratchpadDeletePending = false
    loadScratchpad()
    Qt.callLater(function() {
      root.updateGeometry()
      scratchpadField.forceActiveFocus()
    })
  }

  function showAssistant() {
    scratchpadMode = false
    scratchpadDeletePending = false
    Qt.callLater(function() { queryField.forceActiveFocus() })
  }

  function loadScratchpad() {
    if (scratchpadLoadProcess.running) return
    scratchpadLoadProcess.command = ["ask-omar", "scratchpad-notes"]
    scratchpadLoadProcess.running = true
  }

  function handleScratchpad(raw) {
    try {
      var result = JSON.parse(String(raw || "").trim())
      if (!result.ok) return
      if (scratchpadVersion !== 0) return
      restoringScratchpad = true
      scratchpadNotes = result.notes || [""]
      scratchpadNoteIndex = Math.min(scratchpadNoteIndex, scratchpadNotes.length - 1)
      scratchpadText = String(scratchpadNotes[scratchpadNoteIndex] || "")
      restoringScratchpad = false
    } catch (error) { }
  }

  function saveDraft() {
    if (draftSaveProcess.running) return
    if (characterCount(queryText) > 2000) {
      draftSaveState = "error"
      draftSaveError = "Draft exceeds 2,000 characters. Shorten it to save."
      flushPendingSaves()
      return
    }
    draftSaveState = "pending"
    draftSaveError = ""
    draftSaveProcess.saveVersion = draftVersion
    draftSaveProcess.ackReceived = false
    startStdinCommand(draftSaveProcess, ["ask-omar", "draft", "--stdin"], queryText)
  }

  function saveScratchpad() {
    if (scratchpadSaveProcess.running) return
    if (scratchpadNotes.length > 20 || scratchpadNotes.some(function(note) { return characterCount(note) > 20000 })) {
      scratchpadSaveState = "error"
      scratchpadSaveError = "Use at most 20 notes of 20,000 characters each. Changes are still in this window."
      flushPendingSaves()
      return
    }
    scratchpadSaveState = "pending"
    scratchpadSaveError = ""
    scratchpadSaveProcess.saveVersion = scratchpadVersion
    scratchpadSaveProcess.ackReceived = false
    startStdinCommand(scratchpadSaveProcess, ["ask-omar", "scratchpad-notes-save", "--stdin"], JSON.stringify(scratchpadNotes))
  }

  function handleSave(raw, kind, version) {
    var result
    try { result = JSON.parse(String(raw || "").trim()) }
    catch (error) { result = { ok: false, error: "Could not read the save response." } }
    var isDraft = kind === "draft"
    var currentVersion = isDraft ? draftVersion : scratchpadVersion
    if (result.ok === true) {
      if (isDraft) {
        savedDraftVersion = version
        draftSaveState = version === currentVersion ? "saved" : "pending"
        draftSaveError = ""
      } else {
        savedScratchpadVersion = version
        scratchpadSaveState = version === currentVersion ? "saved" : "pending"
        scratchpadSaveError = ""
      }
      if (version !== currentVersion) Qt.callLater(function() {
        if (isDraft) saveDraft()
        else saveScratchpad()
      })
    } else if (version === currentVersion) {
      if (isDraft) {
        draftSaveState = "error"
        draftSaveError = String(result.error || "Could not save the draft.")
      } else {
        scratchpadSaveState = "error"
        scratchpadSaveError = String(result.error || "Could not save scratchpad notes.")
      }
    } else Qt.callLater(function() {
      if (isDraft) saveDraft()
      else saveScratchpad()
    })
    Qt.callLater(function() { flushPendingSaves() })
  }

  function saveProcessExited(kind, version) {
    var isDraft = kind === "draft"
    var proc = isDraft ? draftSaveProcess : scratchpadSaveProcess
    if (proc.saveVersion !== version) return
    if (!proc.ackReceived) {
      handleSave("", kind, version)
      return
    }
    if (isDraft && draftSaveState === "pending" && draftVersion !== savedDraftVersion)
      saveDraft()
    else if (!isDraft && scratchpadSaveState === "pending" && scratchpadVersion !== savedScratchpadVersion)
      saveScratchpad()
    flushPendingSaves()
  }

  function selectScratchpadNote(index) {
    if (index < 0 || index >= scratchpadNotes.length) return
    scratchpadNoteIndex = index
    restoringScratchpad = true
    scratchpadText = String(scratchpadNotes[index] || "")
    restoringScratchpad = false
    Qt.callLater(function() { scratchpadField.forceActiveFocus() })
  }

  function addScratchpadNote() {
    if (scratchpadNotes.length >= 20) return
    scratchpadNotes = scratchpadNotes.concat([""])
    selectScratchpadNote(scratchpadNotes.length - 1)
    scratchpadVersion++
    scratchpadSaveState = "pending"
    scratchpadSaveError = ""
    scratchpadSaveTimer.restart()
  }

  function deleteScratchpadNote() {
    if (!scratchpadDeletePending && scratchpadText !== "") {
      scratchpadDeletePending = true
      return
    }
    scratchpadDeletePending = false
    if (scratchpadNotes.length <= 1) {
      scratchpadNotes = [""]
      selectScratchpadNote(0)
    } else {
      scratchpadNotes.splice(scratchpadNoteIndex, 1)
      scratchpadNotes = scratchpadNotes.slice()
      selectScratchpadNote(Math.min(scratchpadNoteIndex, scratchpadNotes.length - 1))
    }
    scratchpadVersion++
    scratchpadSaveState = "pending"
    scratchpadSaveError = ""
    scratchpadSaveTimer.restart()
  }

  function copyScratchpad() {
    if (copyProcess.running || scratchpadText === "") return
    var selection = String(scratchpadField.selectedText || "")
    var value = selection !== "" ? selection : scratchpadText
    copyFailed = false
    copied = false
    startStdinCommand(copyProcess, ["wl-copy"], value)
  }

  function checkHealth() {
    if (healthProcess.running) return
    healthStatus = "checking"
    healthChecked = true
    healthProcess.command = ["ask-omar", "health"]
    healthProcess.running = true
  }

  function loadModels() {
    if (modelsProcess.running) return
    modelsLoading = true
    modelsMessage = ""
    modelsProcess.command = ["ask-omar", "models"]
    modelsProcess.running = true
  }

  function handleModels(raw) {
    modelsLoading = false
    try {
      var result = JSON.parse(String(raw || "").trim())
      if (!result.ok) {
        availableModels = []
        modelsMessage = String(result.error || "Ask Omar couldn't list models.")
        return
      }
      availableModels = Array.isArray(result.models) ? result.models : []
      if (Array.isArray(result.thinking_levels) && result.thinking_levels.length > 0)
        thinkingLevels = result.thinking_levels
      if (result.provider) healthProvider = String(result.provider)
      if (result.model) healthModel = String(result.model)
      if (result.thinking) healthThinking = String(result.thinking)
      modelsMessage = String(result.message || "")
    } catch (error) {
      availableModels = []
      modelsMessage = "Ask Omar couldn't read the model list."
    }
  }

  function selectModel(provider, model) {
    if (agentSaving || setAgentProcess.running) return
    saveAgentSettings(String(provider || healthProvider), String(model || ""), healthThinking)
  }

  function selectThinking(level) {
    if (agentSaving || setAgentProcess.running) return
    saveAgentSettings(healthProvider, healthModel, String(level || ""))
  }

  function saveAgentSettings(provider, model, thinking) {
    if (provider === "" || model === "" || thinking === "") {
      agentSaveMessage = "Choose a model and reasoning level first."
      return
    }
    agentSaving = true
    agentSaveMessage = "Saving…"
    setAgentProcess.command = [
      "ask-omar", "set-agent",
      "--provider", provider,
      "--model", model,
      "--thinking", thinking
    ]
    setAgentProcess.running = true
  }

  function handleSetAgent(raw) {
    agentSaving = false
    try {
      var result = JSON.parse(String(raw || "").trim())
      if (!result.ok) {
        agentSaveMessage = String(result.error || "Could not save AI settings.")
        return
      }
      healthProvider = String(result.provider || healthProvider)
      healthModel = String(result.model || healthModel)
      healthThinking = String(result.thinking || healthThinking)
      agentSaveMessage = String(result.message || "AI settings saved.")
      checkHealth()
    } catch (error) {
      agentSaveMessage = "Could not read the AI settings response."
    }
  }

  function selectSystemAccess(mode) {
    if (accessSaving || setAccessProcess.running) return
    if (mode === "full" && !fullAccessPending) {
      fullAccessPending = true
      accessSaveMessage = "Allow All runs routine shell commands without asking. High-risk commands still need approval. Click again to enable it."
      return
    }
    fullAccessPending = false
    accessSaving = true
    accessSaveMessage = "Saving…"
    setAccessProcess.command = ["ask-omar", "set-access", mode]
    setAccessProcess.running = true
  }

  function handleSetAccess(raw) {
    accessSaving = false
    try {
      var result = JSON.parse(String(raw || "").trim())
      if (!result.ok) {
        accessSaveMessage = String(result.error || "Could not save system access.")
        return
      }
      healthSystemAccess = String(result.system_access || "ask")
      accessSaveMessage = String(result.message || "System access updated.")
    } catch (error) {
      accessSaveMessage = "Could not read the system access response."
    }
  }

  function handleHealth(raw) {
    healthChecked = true
    try {
      var result = JSON.parse(String(raw || "").trim())
      if (!result.ok) {
        healthStatus = "error"
        healthMessage = String(result.error || "Ask Omar couldn't check the AI connection.")
        return
      }
      var agent = result.agent || {}
      healthStatus = String(agent.status || "error")
      healthMessage = String(agent.message || "")
      healthProvider = String(result.provider || "")
      healthModel = String(result.model || "")
      healthThinking = String(result.thinking || "")
      healthSystemAccess = String(result.system_access || "ask")
    } catch (error) {
      healthStatus = "error"
      healthMessage = "Ask Omar couldn't read the AI connection check."
    }
  }

  function aiUnavailable() {
    return healthChecked && healthStatus !== "ready" && healthStatus !== "checking"
  }

  function healthTitle() {
    if (healthStatus === "ready") return "AI connection ready"
    if (healthStatus === "signin") return "Connect " + (healthProvider !== "" ? healthProvider : "your provider") + " in Pi"
    if (healthStatus === "configure") return "Choose a model in Settings"
    if (healthStatus === "missing") return "Pi is needed for AI requests"
    if (healthStatus === "checking") return "Checking the AI connection…"
    return "AI connection needs attention"
  }

  function healthLabel() {
    if (healthStatus === "ready")
      return "Pi found. Credentials are available locally; this does not guarantee the provider is online."
    if (healthStatus === "signin")
      return "Open a terminal, run pi, enter /login, then sign in for " + (healthProvider !== "" ? healthProvider : "your provider") + ". Don't paste passwords, tokens, or sign-in codes into Ask Omar."
    if (healthStatus === "configure")
      return "Ask Omar has no provider/model yet. Open Change model or reasoning, or run ask-omar setup after Pi is signed in so Omar can copy Pi's defaults."
    if (healthStatus === "missing")
      return "Ask Omar couldn't find Pi, the separate app that runs its AI requests. Install it from https://pi.dev, then check again. Scratchpad and capture are available now."
    if (healthStatus === "checking") return "Looking for Pi and local provider credentials."
    return healthMessage !== "" ? healthMessage : "Ask Omar couldn't check Pi. Scratchpad and capture are still available."
  }

  function appendScratchpadText(text) {
    var value = String(text || "").trim()
    if (value === "") return
    scratchpadText += (scratchpadText === "" || scratchpadText.endsWith("\n") ? "" : "\n") + value
    Qt.callLater(function() { scratchpadField.forceActiveFocus() })
  }

  function scratchpadImages() {
    var images = []
    var matcher = /!\[Screenshot\]\(<(file:\/\/\/[^>]+)>\)/g
    var match
    while ((match = matcher.exec(scratchpadText)) !== null) images.push(match[1])
    return images
  }

  function activityDisplay() {
    if (showSlowHint)
      return "Still working… You can wait or press Stop."
    var value = String(activityText || "Working").replace(/…$/, "")
    var dots = ""
    for (var index = 0; index < activityDots; index++) dots += "."
    return value + dots
  }

  function loadActivity() {
    if (!busy || activityProcess.running) return
    activityProcess.command = ["ask-omar", "activity"]
    activityProcess.running = true
  }

  function handleActivity(raw) {
    try {
      var result = JSON.parse(String(raw || "").trim())
      if (result.ok) {
        if (result.message) activityText = String(result.message).replace(/…$/, "")
        if (result.confirmation) {
          var nextId = String(result.confirmation.id || "")
          // Don't resurrect the prompt while Allow/Deny for this id is in flight.
          if (confirmInFlightId !== "" && nextId === confirmInFlightId) return
          // After a successful Allow/Deny, activity can still echo the same id
          // briefly — do not put the chrome back once we've cleared it.
          if (
            pendingConfirmation === null
            && confirmInFlightId === ""
            && nextId !== ""
            && nextId === surfacedConfirmationId
          ) return
          pendingConfirmation = result.confirmation
          // First sight of this confirmation opens the panel once. Later polls
          // keep the payload fresh without undoing a click-away dismiss.
          if (nextId !== "" && nextId !== surfacedConfirmationId) {
            surfacedConfirmationId = nextId
            surfacePendingConfirmation()
          }
        } else if (confirmInFlightId === "" && pendingConfirmation !== null) {
          // Backend cleared the pending approval — drop the UI too.
          clearPendingConfirmation()
        }
      }
    } catch (error) { }
  }

  // Approvals must interrupt whatever chrome is up — do not wait for a bar click.
  function surfacePendingConfirmation() {
    if (pendingConfirmation === null) return
    scratchpadMode = false
    settingsExpanded = false
    screenshotMenuExpanded = false
    panelView = "chat"
    historyPreview = null
    historyItemResponse = ""
    clearHistoryPending = false
    answersFromSettings = false
    replyExpanded = false
    resultVisible = true
    if (!opened) {
      opened = true
      updateGeometry()
    }
    Qt.callLater(function() { root.updateGeometry() })
  }

  function respondToConfirmation(response) {
    if (!pendingConfirmation || confirmProcess.running) return
    var requestId = String(pendingConfirmation.id || "")
    if (requestId === "") return
    confirmInFlightId = requestId
    confirmSnapshot = pendingConfirmation
    confirmProcess.command = ["ask-omar", "confirm", requestId, response]
    confirmProcess.running = true
    // Drop the prompt immediately, but keep surfacedConfirmationId so the next
    // activity poll (same id, still pending until Pi acknowledges) cannot
    // treat it as a brand-new confirmation and re-open the panel.
    pendingConfirmation = null
  }

  function focusMicrophoneTarget() {
    if (!opened) open()
    Qt.callLater(function() {
      if (root.scratchpadMode) scratchpadField.forceActiveFocus()
      else queryField.forceActiveFocus()
    })
  }

  function microphone() {
    focusMicrophoneTarget()
    if (!bar) return
    if (micState === "transcribing") bar.run("voxtype record cancel")
    else bar.run("voxtype record toggle")
  }

  function microphonePressed() {
    if (!voxtypeAvailable || micPointerActive) return
    focusMicrophoneTarget()
    micPointerActive = true
    micPointerInitialState = micState
    micPointerStartedAt = Date.now()
    if (!bar) return
    if (micState === "transcribing") bar.run("voxtype record cancel")
    else if (micState !== "recording") bar.run("voxtype record start")
  }

  function microphoneReleased() {
    if (!micPointerActive) return
    var initialState = micPointerInitialState
    var heldMilliseconds = Date.now() - micPointerStartedAt
    micPointerActive = false
    micPointerInitialState = "idle"
    if (!bar || initialState === "transcribing") return
    // A short click starts toggle-style dictation. Holding for at least 350 ms
    // is push-to-talk and transcribes as soon as the pointer is released.
    if (initialState === "recording" || heldMilliseconds >= 350)
      bar.run("voxtype record stop")
  }

  function stopCurrentRequest() {
    if (!busy || submittedQuery === "" || stopProcess.running) return
    requestState = "stopping"
    activityText = "Stopping"
    activityDots = 0
    busyLabel = "Stopping…"
    stopProcess.command = ["ask-omar", "stop"]
    stopProcess.running = true
  }

  function handleStop(raw) {
    var result
    try {
      result = JSON.parse(String(raw || "").trim())
    } catch (error) {
      errorText = "Ask Omar could not confirm the Stop request."
      return
    }
    if (!result.ok) {
      errorText = String(result.error || "Ask Omar could not stop the request.")
      requestState = "working"
      return
    }
    if (String(result.status || "") === "stopping") {
      requestState = "stopping"
      activityText = "Stopping"
      busyLabel = "Stopping…"
    }
  }

  function handleResult(raw) {
    slowHintTimer.stop()
    busy = false
    requestState = "idle"
    activityDots = 0
    busyLabel = ""
    showSlowHint = false
    clearPendingConfirmation()
    var result
    try {
      result = JSON.parse(String(raw || "").trim())
    } catch (error) {
      errorText = "Ask Omar returned an unreadable response."
      failedQuery = submittedQuery
      failedActionId = pendingActionId
      submittedQuery = ""
      pendingActionId = ""
      return
    }
    if (result.kind === "stopped" || result.stopped === true) {
      requestState = "stopped"
      responseText = String(result.message || "Stopped.")
      historyQueryText = submittedQuery
      historyEntryKind = "stopped"
      recapText = ""
      appendConversationTurn("omar", responseText)
      lastAnswerAt = Date.now()
      resultVisible = true
      errorText = ""
      failedQuery = ""
      failedActionId = ""
      queryText = ""
      submittedQuery = ""
      pendingActionId = ""
      return
    }
    if (!result.ok) {
      errorText = String(result.error || "Ask Omar could not complete that request.")
      if (String(result.error_code || "").indexOf("pi_") === 0) checkHealth()
      failedQuery = submittedQuery
      failedActionId = pendingActionId
      submittedQuery = ""
      pendingActionId = ""
      resultVisible = conversationTurns.length > 0
      return
    }
    failedQuery = ""
    failedActionId = ""
    errorText = ""
    freshNotice = false
    responseText = String(result.message || "")
    recapText = String(result.recap || "")
    if (responseText !== "") {
      appendConversationTurn("omar", responseText)
      lastAnswerAt = Date.now()
    }
    resultVisible = conversationTurns.length > 0
    panelView = "chat"
    historyPreview = null
    historyItemResponse = ""
    submittedQuery = ""
    pendingActionId = ""
    if (result.dismiss === true) close(false)
    else {
      Qt.callLater(function() { root.focusComposer() })
    }
  }

  function prepareStoppedRetry() {
    if (historyQueryText === "") return
    queryText = historyQueryText
    retryWarning = "Review before running again. Earlier changes were not undone, so some actions may be repeated."
    historyPreview = null
    historyItemResponse = ""
    panelView = "chat"
    Qt.callLater(function() { root.focusComposer() })
  }

  function updateMic(raw) {
    try {
      var value = JSON.parse(String(raw || ""))
      micState = String(value.alt || value.class || "idle")
    } catch (error) {
      micState = "idle"
    }
  }

  onQueryTextChanged: if (!restoringDraft && !quitting) {
    draftVersion++
    draftSaveState = "pending"
    draftSaveError = ""
    draftSaveTimer.restart()
  }
  onScratchpadTextChanged: {
    if (!restoringScratchpad && !quitting) {
      scratchpadNotes[scratchpadNoteIndex] = scratchpadText
      scratchpadNotes = scratchpadNotes.slice()
      scratchpadVersion++
      scratchpadSaveState = "pending"
      scratchpadSaveError = ""
      scratchpadSaveTimer.restart()
    }
  }
  onResponseTextChanged: {
    copied = false
    copyFailed = false
    answerText.deselect()
  }

  Component.onCompleted: {
    backendCheckProcess.running = true
    draftLoadProcess.command = ["ask-omar", "get-draft"]
    draftLoadProcess.running = true
    loadScratchpad()
    checkRecording()
    voxtypeCheckProcess.command = ["sh", "-c", "command -v voxtype || command -v omarchy-voxtype-status"]
    voxtypeCheckProcess.running = true
    if (setting("openOnStartup", false) === true && !hiddenFromBar) Qt.callLater(root.open)
  }

  IpcHandler {
    enabled: root.controlInstance
    target: "ask-omar"
    function open(): void { root.open() }
    function close(): void { root.close() }
    function show(): void { root.open() }
    function hide(): void { root.close() }
    function quit(): void { root.quitApplication() }
    function toggle(): void { root.toggle() }
    function focus(): void { root.open() }
    function settings(): void { root.showSettings() }
    function setDraft(text: string): void {
      if (root.scratchpadMode) root.appendScratchpadText(text)
      else if (root.replyExpanded) root.replyText = text
      else root.queryText = text
    }
    function getDraft(): string {
      return root.replyExpanded ? root.replyText : root.queryText
    }
    function copyLastAnswer(): string {
      if (root.responseText === "") return "no answer"
      root.copyResponse()
      return "ok"
    }
    function focusAnswer(): string {
      if (!root.resultVisible || root.responseText === "") return "no visible answer"
      answerText.forceActiveFocus()
      return "ok"
    }
    function openHistoryIndex(value: string): string {
      var index = Number(value)
      if (!Number.isInteger(index) || index < 0 || index >= root.historyEntries.length) return "invalid index"
      root.showHistoryEntry(root.historyEntries[index])
      return "ok"
    }
    function showHistory(): void {
      root.showHistory()
    }
    function scratchpad(): void {
      root.openScratchpad()
    }
    function screenshotChoices(): void {
      root.showScreenshotChoices()
    }
    function appendScratchpad(text: string): void {
      root.appendScratchpadText(text)
    }
    function recordingStarted(target: string): void {
      root.recordingTarget = target === "scratchpad" ? "scratchpad" : "assistant"
      root.recordingActive = true
    }
    function recordingStopped(): void {
      root.recordingActive = false
    }
    function debugState(): string {
      return JSON.stringify({
        opened: root.opened,
        busy: root.busy,
        requestState: root.requestState,
        resultVisible: root.resultVisible,
        actionsExpanded: root.actionsExpanded,
        historyExpanded: root.historyExpanded,
        historyCount: root.historyEntries.length,
        hasResponse: root.responseText !== "",
        copied: root.copied,
        copyFailed: root.copyFailed,
        inputFocused: queryField.activeFocus,
        answerFocused: answerText.activeFocus,
        selectedLength: answerText.selectedText.length,
        hasError: root.errorText !== "",
        resetRunning: newConversationProcess.running,
        stopRunning: stopProcess.running
      })
    }
  }

  Process {
    id: draftLoadProcess
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        try {
          var result = JSON.parse(String(text || "").trim())
          if (result.ok && result.draft && root.queryText === "" && !root.busy && !root.replyExpanded) {
            root.restoringDraft = true
            root.queryText = String(result.draft)
            root.restoringDraft = false
          }
        } catch (error) { }
      }
    }
  }

  Process {
    id: backendCheckProcess
    command: ["sh", "-c", "command -v ask-omar >/dev/null 2>&1"]
    onExited: function(exitCode, exitStatus) {
      root.backendInstalled = exitCode === 0
      if (!root.backendInstalled)
        root.errorText = "Ask Omar backend is missing. Install Ask Omar from the marketplace, or run make setup from its source directory."
    }
  }

  Process {
    id: draftSaveProcess
    property string pendingStdin: ""
    property int saveVersion: 0
    property bool ackReceived: false
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        draftSaveProcess.ackReceived = true
        root.handleSave(text, "draft", draftSaveProcess.saveVersion)
      }
    }
    onExited: function(exitCode, exitStatus) {
      var version = draftSaveProcess.saveVersion
      Qt.callLater(function() { root.saveProcessExited("draft", version) })
    }
    onStarted: {
      write(pendingStdin)
      pendingStdin = ""
      stdinEnabled = false
    }
  }

  Process {
    id: scratchpadLoadProcess
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: root.handleScratchpad(text)
    }
  }

  Process {
    id: scratchpadSaveProcess
    property string pendingStdin: ""
    property int saveVersion: 0
    property bool ackReceived: false
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        scratchpadSaveProcess.ackReceived = true
        root.handleSave(text, "scratchpad", scratchpadSaveProcess.saveVersion)
      }
    }
    onExited: function(exitCode, exitStatus) {
      var version = scratchpadSaveProcess.saveVersion
      Qt.callLater(function() { root.saveProcessExited("scratchpad", version) })
    }
    onStarted: {
      write(pendingStdin)
      pendingStdin = ""
      stdinEnabled = false
    }
  }

  Process {
    id: historyProcess
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: root.handleHistory(text)
    }
    stderr: StdioCollector {
      waitForEnd: true
      onStreamFinished: if (String(text || "").trim() !== "") root.errorText = String(text).trim()
    }
  }

  Process {
    id: clearHistoryProcess
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: root.handleClearHistory(text)
    }
    stderr: StdioCollector {
      waitForEnd: true
      onStreamFinished: if (String(text || "").trim() !== "") root.errorText = String(text).trim()
    }
  }

  Process {
    id: copyProcess
    property string pendingStdin: ""
    onStarted: {
      write(pendingStdin)
      pendingStdin = ""
      stdinEnabled = false
    }
    onExited: function(exitCode, exitStatus) {
      root.copyFailed = exitCode !== 0
      root.copied = exitCode === 0
      if (root.copied) copiedTimer.restart()
    }
  }

  Process {
    id: queryProcess
    property string pendingStdin: ""
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: root.handleResult(text)
    }
    stderr: StdioCollector {
      waitForEnd: true
      onStreamFinished: if (String(text || "").trim() !== "") root.errorText = String(text).trim()
    }
    onStarted: {
      write(pendingStdin)
      pendingStdin = ""
      stdinEnabled = false
    }
  }

  Process {
    id: stopProcess
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: root.handleStop(text)
    }
    stderr: StdioCollector {
      waitForEnd: true
      onStreamFinished: if (String(text || "").trim() !== "") root.errorText = String(text).trim()
    }
  }

  Process {
    id: activityProcess
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: root.handleActivity(text)
    }
  }

  Process {
    id: confirmProcess
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: root.handleConfirm(text)
    }
    stderr: StdioCollector {
      waitForEnd: true
      onStreamFinished: if (String(text || "").trim() !== "") root.errorText = String(text).trim()
    }
  }

  Process {
    id: newConversationProcess
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: root.handleNewConversation(text)
    }
    stderr: StdioCollector {
      waitForEnd: true
      onStreamFinished: if (String(text || "").trim() !== "") root.errorText = String(text).trim()
    }
  }

  Process {
    id: voxtypeCheckProcess
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        var output = String(text || "").trim()
        root.voxtypeAvailable = output !== ""
      }
    }
    stderr: StdioCollector { waitForEnd: true }
  }

  Process {
    id: healthProcess
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: root.handleHealth(text)
    }
    stderr: StdioCollector { waitForEnd: true }
  }

  Process {
    id: modelsProcess
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: root.handleModels(text)
    }
    stderr: StdioCollector { waitForEnd: true }
  }

  Process {
    id: setAgentProcess
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: root.handleSetAgent(text)
    }
    stderr: StdioCollector { waitForEnd: true }
  }

  Process {
    id: setAccessProcess
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: root.handleSetAccess(text)
    }
    stderr: StdioCollector { waitForEnd: true }
  }

  Process { id: captureLauncher }

  Process {
    id: recordingCheckProcess
    onExited: function(exitCode, exitStatus) { root.recordingActive = exitCode === 0 }
  }

  Process { id: quitProcess }

  Process {
    id: restartProcess
    onExited: function(exitCode, exitStatus) {
      root.restarting = false
      root.healthChecked = false
      root.checkHealth()
    }
  }

  Process {
    id: serviceStartProcess
    onExited: function(exitCode, exitStatus) {
      if (!root.openPending) return
      var showSettings = root.settingsPending
      var showHistory = root.historyPending
      root.openPending = false
      root.settingsPending = false
      root.historyPending = false
      root.reveal()
      if (exitCode !== 0)
        root.errorText = root.backendInstalled
          ? "Ask Omar could not start its service. Check the installation, or run make setup from its source directory."
          : "Ask Omar backend is missing. Install Ask Omar from the marketplace, or run make setup from its source directory."
      if (showSettings) {
        root.settingsExpanded = true
        root.checkHealth()
        root.loadModels()
      }
      else if (showHistory) root.showHistory()
    }
  }

  Process {
    command: ["omarchy-voxtype-status"]
    running: true
    stdout: SplitParser {
      onRead: function(data) { root.updateMic(data) }
    }
  }

  Timer {
    id: copiedTimer
    interval: 1400
    onTriggered: root.copied = false
  }

  Timer {
    id: activityDotsTimer
    interval: 350
    repeat: true
    running: root.busy
    onTriggered: root.activityDots = (root.activityDots + 1) % 4
  }

  Timer {
    id: activityTimer
    interval: 1000
    repeat: true
    running: root.busy
    onTriggered: root.loadActivity()
  }

  Timer {
    id: screenshotDelayTimer
    repeat: false
    onTriggered: {
      captureLauncher.command = ["ask-omar-capture", "screenshot", root.screenshotMode, root.screenshotTarget]
      captureLauncher.startDetached()
    }
  }

  Timer {
    id: draftSaveTimer
    interval: 500
    onTriggered: {
      if (root.quitting) return
      if (draftSaveProcess.running) {
        draftSaveTimer.restart()
        return
      }
      root.saveDraft()
    }
  }

  Timer {
    id: scratchpadSaveTimer
    interval: 500
    onTriggered: {
      if (root.quitting) return
      if (scratchpadSaveProcess.running) {
        scratchpadSaveTimer.restart()
        return
      }
      root.saveScratchpad()
    }
  }

  Timer {
    id: slowHintTimer
    interval: 20000
    onTriggered: {
      if (root.busy && root.submittedQuery !== "") {
        root.showSlowHint = true
      }
    }
  }

  // The bar itself cannot take keyboard focus under layer-shell. This field is
  // the permanent affordance; opening it maps the focused overlay field at the
  // exact same position, so clicking and typing still feels inline.
  BorderSurface {
    id: barSurface
    anchors.fill: parent
    color: Style.normalFillFor(root.foreground, root.accent)
    borderSpec: Border.controlSpec(root.opened ? "focus" : "normal", root.foreground, root.accent)
    radius: Style.cornerRadius

    Text {
      textFormat: Text.PlainText
      anchors.left: parent.left
      anchors.leftMargin: Style.space(10)
      anchors.right: barMic.left
      anchors.rightMargin: Style.space(6)
      anchors.verticalCenter: parent.verticalCenter
      text: (!root.busy && root.queryText !== "") ? root.queryText : "Ask Omar…"
      elide: Text.ElideRight
      color: (!root.busy && root.queryText !== "") ? root.foreground : Qt.darker(root.foreground, 1.55)
      font.family: root.bar ? root.bar.fontFamily : Style.font.family
      font.pixelSize: Style.font.body
    }

    MouseArea {
      anchors.left: parent.left
      anchors.top: parent.top
      anchors.bottom: parent.bottom
      anchors.right: barMic.left
      cursorShape: Qt.IBeamCursor
      onClicked: root.open()
    }

    Rectangle {
      id: barMic
      width: root.iconWidth
      height: parent.height
      anchors.right: barScratchpad.left
      color: "transparent"

      Text {
        textFormat: Text.PlainText
        anchors.centerIn: parent
        text: root.micState === "transcribing" ? "󰔟" : "󰍬"
        color: !root.voxtypeAvailable ? Qt.darker(root.foreground, 1.8) : (root.micState === "recording" ? root.accent : root.foreground)
        font.family: root.bar ? root.bar.fontFamily : Style.font.family
        font.pixelSize: Style.font.icon
      }
      MouseArea {
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: root.voxtypeAvailable ? Qt.PointingHandCursor : Qt.ArrowCursor
        onPressed: if (root.voxtypeAvailable) root.microphonePressed()
        onReleased: root.microphoneReleased()
        onCanceled: root.microphoneReleased()
      }
    }

    Rectangle {
      id: barScratchpad
      width: root.iconWidth
      height: parent.height
      anchors.right: barCamera.left
      color: "transparent"

      Text {
        textFormat: Text.PlainText
        anchors.centerIn: parent
        text: "󰎚"
        color: root.foreground
        font.family: root.bar ? root.bar.fontFamily : Style.font.family
        font.pixelSize: Style.font.icon
      }
      MouseArea {
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: root.openScratchpad()
      }
    }

    Rectangle {
      id: barCamera
      width: root.iconWidth
      height: parent.height
      anchors.right: parent.right
      color: "transparent"

      Text {
        textFormat: Text.PlainText
        anchors.centerIn: parent
        text: root.recordingActive ? "■" : "󰄀"
        color: root.recordingActive ? root.accent : root.foreground
        font.family: root.bar ? root.bar.fontFamily : Style.font.family
        font.pixelSize: Style.font.icon
      }
      MouseArea {
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        onClicked: function(mouse) {
          if (mouse.button === Qt.RightButton) root.showScreenshotChoices()
          else root.camera()
        }
        Accessible.name: root.recordingActive ? "Stop screen recording" : "Capture screenshot"
      }
    }
  }

  PanelWindow {
    id: assistantWindow
    screen: root.QsWindow.window ? root.QsWindow.window.screen : null
    visible: root.opened || root.screenshotMenuExpanded
    color: "transparent"
    exclusionMode: ExclusionMode.Ignore

    WlrLayershell.namespace: "ask-omar"
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.keyboardFocus: visible ? WlrKeyboardFocus.Exclusive : WlrKeyboardFocus.None

    anchors {
      top: true
      bottom: true
      left: true
      right: true
    }

    Shortcut {
      sequence: "Escape"
      context: Qt.WindowShortcut
      enabled: assistantWindow.visible
      onActivated: {
        if (root.pendingConfirmation) root.respondToConfirmation("Deny")
        else if (root.historyItemOpen) root.clearHistoryPreview()
        else if (root.historyExpanded) root.backFromAnswers()
        else if (root.replyExpanded) {
          // Collapse Reply only — keep the draft for the next Reply click.
          root.replyExpanded = false
          queryField.forceActiveFocus()
        } else if (root.threadExpanded) root.threadExpanded = false
        else root.close()
      }
    }

    MouseArea {
      anchors.fill: parent
      acceptedButtons: Qt.AllButtons
      onClicked: root.close()
    }

    BorderSurface {
      id: overlayField
      visible: root.opened && !root.scratchpadMode
      x: root.fieldX
      y: root.fieldY
      width: root.width
      height: root.height
      color: Color.popups.background
      borderSpec: Border.controlSpec("focus", root.foreground, root.accent)
      radius: Style.cornerRadius

      TextField {
        id: queryField
        anchors.left: parent.left
        anchors.right: overlayMic.left
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        text: root.queryText
        placeholderText: "Ask Omar…"
        foreground: root.foreground
        accent: root.accent
        verticalPadding: 1
        enabled: !root.busy
        cursorVisible: activeFocus
        background: Item {}
        onTextChanged: root.queryText = text
        Accessible.name: "Ask Omar request"
        onTextEdited: {
          root.resultVisible = false
          root.actionsExpanded = false
          root.panelView = "chat"
          root.historyPreview = null
          root.historyItemResponse = ""
          root.errorText = ""
          root.failedQuery = ""
          root.failedActionId = ""
        }
        onAccepted: root.acceptField()
        Keys.onPressed: function(event) {
          var control = (event.modifiers & Qt.ControlModifier) !== 0
          if (control && event.key === Qt.Key_V) {
            queryField.paste()
            event.accepted = true
          } else if (control && event.key === Qt.Key_C) {
            queryField.copy()
            event.accepted = true
          } else if (control && event.key === Qt.Key_X) {
            queryField.cut()
            event.accepted = true
          } else if (control && event.key === Qt.Key_A) {
            queryField.selectAll()
            event.accepted = true
          } else if (event.key === Qt.Key_Escape) {
            root.close()
            event.accepted = true
          }
        }
      }

      MicButton {
        id: overlayMic
        anchors.right: overlayScratchpad.left
        anchors.verticalCenter: parent.verticalCenter
        size: root.iconWidth
        iconText: root.micState === "transcribing" ? "󰔟" : "󰍬"
        foreground: !root.voxtypeAvailable ? Qt.darker(root.foreground, 1.8) : (root.micState === "recording" ? root.accent : root.foreground)
        hoverColor: root.accent
        fontFamily: root.bar ? root.bar.fontFamily : Style.font.family
        tooltipText: !root.voxtypeAvailable ? "Install Voxtype for dictation"
          : (root.micState === "recording" ? "Click to stop · or release after holding"
          : "Click to start/stop · hold to talk")
        enabled: !root.busy && root.voxtypeAvailable
        focusable: true
        Accessible.name: tooltipText
        onClicked: {
          root.microphone()
          queryField.forceActiveFocus()
        }
        onPointerPressed: root.microphonePressed()
        onPointerReleased: root.microphoneReleased()
      }

      PanelActionButton {
        id: overlayScratchpad
        anchors.right: overlayCamera.left
        anchors.verticalCenter: parent.verticalCenter
        size: root.iconWidth
        iconText: "󰎚"
        foreground: root.foreground
        hoverColor: root.accent
        fontFamily: root.bar ? root.bar.fontFamily : Style.font.family
        tooltipText: "Open scratchpad"
        focusable: true
        Accessible.name: tooltipText
        onClicked: root.openScratchpad()
      }

      Button {
        id: overlayCamera
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        width: root.iconWidth
        height: root.iconWidth
        iconText: root.recordingActive ? "■" : "󰄀"
        foreground: root.recordingActive ? root.accent : root.foreground
        accent: root.accent
        horizontalPadding: 0
        verticalPadding: 0
        fontFamily: root.bar ? root.bar.fontFamily : Style.font.family
        tooltipText: root.recordingActive
          ? "Stop screen recording"
          : "Click to choose a capture · right-click for options"
        enabled: !root.busy
        focusable: true
        Accessible.name: tooltipText
        onClicked: root.camera()
        onRightClicked: root.showScreenshotChoices()
      }
    }

    BorderSurface {
      id: resultPanel
      // Yesterday's feel: focus the bar → compact panel underneath (New available before you send).
      visible: root.opened && !root.scratchpadMode
      readonly property int desiredWidth: Math.max(root.width, Style.space(460))
      readonly property int panelPad: Style.space(14)
      readonly property int replyChromeHeight: {
        if (root.showPanelComposer) return Style.space(40)
        if (root.showReplyButton || root.showChatToggle || root.showBackToChat || root.showBackToSettings || root.historyItemOpen)
          return Style.space(28)
        return 0
      }
      readonly property int headerChromeHeight: Math.max(resultHeader.implicitHeight, Style.space(28))
      readonly property int maxPanelHeight: Math.floor(assistantWindow.height * (root.showChatThread || root.historyExpanded ? 0.42 : 0.62))
      // Scroll the thread only; Reply stays in document flow under the last message.
      readonly property int maxBodyHeight: {
        var stackGaps = Style.space(4) + (replyChromeHeight > 0 ? Style.space(4) : 0)
        var chrome = panelPad * 2 + headerChromeHeight + stackGaps + replyChromeHeight
        return Math.max(Style.space(48), maxPanelHeight - chrome)
      }
      x: Math.max(Style.gapsOut, Math.min(root.fieldX + root.width - width, assistantWindow.width - width - Math.max(Style.gapsOut, Style.space(10))))
      y: root.bar && root.bar.position === "bottom"
        ? assistantWindow.height - (root.QsWindow.window ? root.QsWindow.window.height : root.height) - height - Style.gapsOut
        : (root.QsWindow.window ? root.QsWindow.window.height : root.height) + Style.gapsOut
      width: Math.min(desiredWidth, assistantWindow.width - Style.gapsOut * 2)
      height: Math.min(panelPad * 2 + panelStack.implicitHeight, maxPanelHeight)
      color: Color.popups.background
      borderSpec: Border.surfaceSpec("popups", "border", Color.popups.border, Math.max(1, Style.space(1)))
      radius: Style.cornerRadius
      padding: 0

      MouseArea {
        anchors.fill: parent
        onClicked: function(mouse) { mouse.accepted = true }
      }

      Item {
        id: resultBody
        anchors.fill: parent
        anchors.margins: resultPanel.panelPad
        clip: true

        Column {
          id: panelStack
          width: parent.width
          spacing: Style.space(4)

        Row {
          id: resultHeader
          width: parent.width
          spacing: Style.space(6)

          Text {
            textFormat: Text.PlainText
            id: headerTitle
            width: Math.max(0, parent.width - headerActions.width - parent.spacing)
            anchors.verticalCenter: parent.verticalCenter
            elide: Text.ElideRight
            text: root.settingsExpanded
              ? "Ask Omar Settings"
              : (root.historyExpanded
                ? "Past answers"
                : (root.busy ? root.busyLabel : "Ask Omar"))
            color: root.foreground
            font.family: root.bar ? root.bar.fontFamily : Style.font.family
            font.pixelSize: Style.font.heading
            font.bold: true
            Accessible.name: text
          }

          Row {
            id: headerActions
            spacing: Style.space(6)

            Button {
              id: stopButton
              visible: !root.settingsExpanded && root.busy && root.submittedQuery !== ""
              anchors.verticalCenter: parent.verticalCenter
              text: root.requestState === "stopping" ? "Stopping…" : "Stop"
              enabled: root.requestState !== "stopping" && !stopProcess.running
              focusable: true
              bordered: true
              foreground: root.foreground
              accent: root.accent
              fontFamily: root.bar ? root.bar.fontFamily : Style.font.family
              fontSize: Style.font.bodySmall
              horizontalPadding: Style.space(7)
              verticalPadding: Style.space(3)
              tooltipText: "Stop the current Ask Omar request"
              Accessible.name: tooltipText
              Keys.onEscapePressed: root.close()
              onClicked: root.stopCurrentRequest()
            }

            Button {
              id: newConversationButton
              visible: !root.settingsExpanded && !root.busy && !root.historyExpanded
              anchors.verticalCenter: parent.verticalCenter
              text: "New"
              enabled: !root.busy
              focusable: true
              bordered: root.rememberedAskCount > 0
              foreground: root.foreground
              accent: root.accent
              fontFamily: root.bar ? root.bar.fontFamily : Style.font.family
              fontSize: Style.font.bodySmall
              horizontalPadding: Style.space(7)
              verticalPadding: Style.space(3)
              tooltipText: root.rememberedAskCount > 0
                ? ("Start fresh — Omar forgets this conversation, including "
                  + root.rememberedAskCount
                  + (root.rememberedAskCount === 1 ? " earlier ask" : " earlier asks"))
                : "Start fresh — Omar forgets this conversation"
              Accessible.name: tooltipText
              Keys.onEscapePressed: {
                if (root.threadExpanded) root.threadExpanded = false
                else root.close()
              }
              onClicked: root.newConversation()
            }

            PanelActionButton {
              id: copyButton
              // Only when Omar's reply is on screen — not a reserved empty slot.
              visible: !root.settingsExpanded && !root.historyExpanded
                && root.responseText !== "" && root.showChatThread && !root.busy
              anchors.verticalCenter: parent.verticalCenter
              iconText: root.copyFailed ? "!" : (root.copied ? "✓" : "󰆏")
              tooltipText: root.copyFailed
                ? "Copy failed"
                : (root.copied
                  ? "Copied"
                  : (answerText.selectedText !== "" ? "Copy selection" : "Copy Omar's reply"))
              foreground: root.foreground
              hoverColor: root.accent
              fontFamily: root.bar ? root.bar.fontFamily : Style.font.family
              focusable: true
              Accessible.name: tooltipText
              Keys.onEscapePressed: root.close()
              onClicked: root.copyResponse()
            }

            PanelActionButton {
              id: settingsButton
              iconText: "󰒓"
              size: Style.space(28)
              focusable: true
              bordered: true
              foreground: root.foreground
              hoverColor: root.settingsExpanded ? root.accent : root.foreground
              fontFamily: root.bar ? root.bar.fontFamily : Style.font.family
              fontSize: Style.font.icon
              tooltipText: root.settingsExpanded ? "Close settings" : "Configure Ask Omar"
              Accessible.name: tooltipText
              onClicked: root.toggleSettings()
            }

            PanelActionButton {
              id: closeButton
              iconText: "󰅖"
              size: Style.space(28)
              focusable: true
              bordered: true
              foreground: root.foreground
              hoverColor: root.foreground
              fontFamily: root.bar ? root.bar.fontFamily : Style.font.family
              fontSize: Style.font.icon
              tooltipText: "Close Ask Omar"
              Accessible.name: tooltipText
              onClicked: root.close()
            }
          }
        }

        Text {
          textFormat: Text.PlainText
          visible: !root.settingsExpanded && !root.historyExpanded
            && (root.queryText !== "" || root.draftSaveState === "error" || root.quitRequested)
          width: parent.width
          text: root.quitRequested ? "Saving before quit…"
            : root.draftSaveState === "error" ? root.draftSaveError
            : root.draftSaveState === "pending" ? "Draft save pending…" : "Draft saved locally."
          wrapMode: Text.WordWrap
          color: root.draftSaveState === "error" ? root.accent : Qt.darker(root.foreground, 1.55)
          font.family: root.bar ? root.bar.fontFamily : Style.font.family
          font.pixelSize: Style.font.bodySmall
        }

        Button {
          visible: root.draftSaveState === "error" && !root.settingsExpanded && !root.historyExpanded
          text: "Retry draft save"
          focusable: true
          bordered: true
          foreground: root.foreground
          accent: root.accent
          onClicked: root.saveDraft()
        }

        Flickable {
          id: resultFlickable
          width: parent.width
          height: Math.min(Math.max(contentColumn.implicitHeight, Style.space(8)), resultPanel.maxBodyHeight)
          contentWidth: width
          contentHeight: contentColumn.implicitHeight
          clip: true
          interactive: !(panelComposerField.activeFocus || answerText.activeFocus)
          flickableDirection: Flickable.VerticalFlick
          boundsBehavior: Flickable.StopAtBounds
          ScrollBar.vertical: ScrollBar {
            policy: ScrollBar.AsNeeded
            padding: 2
          }

          Column {
            id: contentColumn
            width: resultFlickable.width
            spacing: Style.space(8)

          Row {
            id: resultActions
            visible: false
            width: parent.width
            height: 0
            spacing: Style.space(6)
          }

          Row {
            visible: root.errorText !== ""
            width: parent.width
            spacing: Style.space(8)

            Text {
              textFormat: Text.PlainText
              width: Math.max(0, parent.width - retryButton.implicitWidth - parent.spacing)
              text: root.errorText
              wrapMode: Text.WordWrap
              color: root.accent
              font.family: root.bar ? root.bar.fontFamily : Style.font.family
              font.pixelSize: Style.font.body
              Accessible.name: "Ask Omar error: " + text
            }

            Button {
              id: retryButton
              visible: root.failedReset || root.failedQuery !== "" || root.failedActionId !== ""
              anchors.verticalCenter: parent.verticalCenter
              text: "Retry"
              focusable: true
              bordered: true
              foreground: root.foreground
              accent: root.accent
              fontFamily: root.bar ? root.bar.fontFamily : Style.font.family
              fontSize: Style.font.bodySmall
              Accessible.name: "Retry the failed request"
              Keys.onEscapePressed: root.close()
              onClicked: root.retry()
            }
          }

          Text {
            textFormat: Text.PlainText
            visible: root.retryWarning !== ""
            width: parent.width
            text: root.retryWarning
            wrapMode: Text.WordWrap
            color: root.accent
            font.family: root.bar ? root.bar.fontFamily : Style.font.family
            font.pixelSize: Style.font.bodySmall
            Accessible.name: text
          }

          Column {
            visible: root.settingsExpanded
            width: parent.width
            spacing: Style.space(10)

            Button {
              id: historyButton
              text: "Past answers"
              focusable: true
              bordered: true
              foreground: root.foreground
              accent: root.accent
              tooltipText: "Questions and answers saved on this machine"
              Accessible.name: tooltipText
              enabled: !root.busy
              onClicked: root.openAnswersList(true)
            }

            Text {
              textFormat: Text.PlainText
              width: parent.width
              text: "AI connection"
              color: root.foreground
              font.family: root.bar ? root.bar.fontFamily : Style.font.family
              font.pixelSize: Style.font.body
              font.bold: true
              Accessible.name: text
            }

            Text {
              textFormat: Text.PlainText
              width: parent.width
              text: root.healthTitle()
                + (root.healthProvider !== "" ? " · " + root.healthProvider : "")
                + (root.healthModel !== "" ? " · " + root.healthModel : "")
                + (root.healthThinking !== "" ? " · reasoning " + root.healthThinking : "")
              wrapMode: Text.WordWrap
              color: root.healthStatus === "ready" ? root.foreground : root.accent
              font.family: root.bar ? root.bar.fontFamily : Style.font.family
              font.pixelSize: Style.font.bodySmall
              Accessible.name: text
            }

            Text {
              textFormat: Text.PlainText
              width: parent.width
              text: root.healthLabel()
              wrapMode: Text.WordWrap
              color: Qt.darker(root.foreground, 1.35)
              font.family: root.bar ? root.bar.fontFamily : Style.font.family
              font.pixelSize: Style.font.bodySmall
              Accessible.name: text
            }

            Button {
              text: root.aiSettingsHelpExpanded ? "Hide model and reasoning" : "Change model or reasoning…"
              focusable: true
              bordered: false
              foreground: root.foreground
              accent: root.accent
              tooltipText: "Choose Ask Omar's Pi model and reasoning level"
              enabled: !root.agentSaving
              onClicked: {
                root.aiSettingsHelpExpanded = !root.aiSettingsHelpExpanded
                if (root.aiSettingsHelpExpanded) root.loadModels()
              }
            }

            Text {
              textFormat: Text.PlainText
              visible: root.aiSettingsHelpExpanded
              width: parent.width
              text: root.modelsLoading
                ? "Loading models from Pi…"
                : (root.modelsMessage !== ""
                  ? root.modelsMessage
                  : "Pick a model and reasoning level. Changes apply to the next request.")
              wrapMode: Text.WordWrap
              color: Qt.darker(root.foreground, 1.35)
              font.family: root.bar ? root.bar.fontFamily : Style.font.family
              font.pixelSize: Style.font.bodySmall
              Accessible.name: text
            }

            Text {
              textFormat: Text.PlainText
              visible: root.aiSettingsHelpExpanded
              width: parent.width
              text: "Model"
              color: root.foreground
              font.family: root.bar ? root.bar.fontFamily : Style.font.family
              font.pixelSize: Style.font.bodySmall
              font.bold: true
              Accessible.name: text
            }

            Repeater {
              model: root.aiSettingsHelpExpanded ? root.availableModels : []
              delegate: Button {
                required property var modelData
                readonly property string optionProvider: String(modelData.provider || "")
                readonly property string optionModel: String(modelData.model || "")
                readonly property bool selected: optionProvider === root.healthProvider && optionModel === root.healthModel
                width: parent.width
                text: (selected ? "󰄬  " : "     ") + optionModel + (optionProvider !== "" ? " · " + optionProvider : "")
                focusable: true
                bordered: true
                foreground: root.foreground
                accent: root.accent
                enabled: !root.agentSaving && !root.modelsLoading
                tooltipText: selected ? "Current model" : "Use " + optionModel
                Accessible.name: (selected ? "Selected model " : "Choose model ") + optionModel
                onClicked: root.selectModel(optionProvider, optionModel)
              }
            }

            Text {
              textFormat: Text.PlainText
              visible: root.aiSettingsHelpExpanded && root.availableModels.length === 0 && !root.modelsLoading
              width: parent.width
              text: "Current model: " + (root.healthModel !== "" ? root.healthModel : "unset")
                + (root.healthProvider !== "" ? " · " + root.healthProvider : "")
              wrapMode: Text.WordWrap
              color: Qt.darker(root.foreground, 1.35)
              font.family: root.bar ? root.bar.fontFamily : Style.font.family
              font.pixelSize: Style.font.bodySmall
              Accessible.name: text
            }

            Text {
              textFormat: Text.PlainText
              visible: root.aiSettingsHelpExpanded
              width: parent.width
              text: "Reasoning"
              color: root.foreground
              font.family: root.bar ? root.bar.fontFamily : Style.font.family
              font.pixelSize: Style.font.bodySmall
              font.bold: true
              Accessible.name: text
            }

            Flow {
              visible: root.aiSettingsHelpExpanded
              width: parent.width
              spacing: Style.space(6)

              Repeater {
                model: root.thinkingLevels
                delegate: Button {
                  required property string modelData
                  readonly property bool selected: String(modelData) === root.healthThinking
                  text: (selected ? "󰄬 " : "") + modelData
                  focusable: true
                  bordered: true
                  foreground: root.foreground
                  accent: root.accent
                  enabled: !root.agentSaving
                  tooltipText: selected ? "Current reasoning" : "Use reasoning " + modelData
                  Accessible.name: (selected ? "Selected reasoning " : "Choose reasoning ") + modelData
                  onClicked: root.selectThinking(modelData)
                }
              }
            }

            Text {
              textFormat: Text.PlainText
              visible: root.aiSettingsHelpExpanded && root.agentSaveMessage !== ""
              width: parent.width
              text: root.agentSaveMessage
              wrapMode: Text.WordWrap
              color: Qt.darker(root.foreground, 1.35)
              font.family: root.bar ? root.bar.fontFamily : Style.font.family
              font.pixelSize: Style.font.bodySmall
              Accessible.name: text
            }

            Button {
              visible: root.aiSettingsHelpExpanded
              text: root.restarting ? "Restarting…" : "Restart Ask Omar"
              enabled: !root.restarting
              focusable: true
              bordered: true
              foreground: root.foreground
              accent: root.accent
              tooltipText: "Restart the AI service if a setting change did not take effect"
              onClicked: root.restartApplication()
            }

            Button {
              text: healthProcess.running ? "Checking…" : "Check again"
              enabled: !healthProcess.running
              focusable: true
              bordered: true
              foreground: root.foreground
              accent: root.accent
              onClicked: {
                root.checkHealth()
                if (root.aiSettingsHelpExpanded) root.loadModels()
              }
            }

            Text {
              textFormat: Text.PlainText
              width: parent.width
              text: "Safety"
              color: root.foreground
              font.family: root.bar ? root.bar.fontFamily : Style.font.family
              font.pixelSize: Style.font.body
              font.bold: true
              Accessible.name: text
            }

            Text {
              textFormat: Text.PlainText
              width: parent.width
              text: "Shell commands run with your permissions. They are not sandboxed. High-risk commands still need approval in every mode."
              wrapMode: Text.WordWrap
              color: Qt.darker(root.foreground, 1.35)
              font.family: root.bar ? root.bar.fontFamily : Style.font.family
              font.pixelSize: Style.font.bodySmall
              Accessible.name: text
            }

            Flow {
              width: parent.width
              spacing: Style.space(6)

              Button {
                text: (root.healthSystemAccess === "ask" ? "󰄬  " : "") + "Ask First"
                focusable: true
                bordered: true
                foreground: root.foreground
                accent: root.accent
                enabled: !root.accessSaving
                tooltipText: "Approve one shell command or allow routine commands for 15 minutes"
                Accessible.name: (root.healthSystemAccess === "ask" ? "Selected: " : "") + tooltipText
                onClicked: root.selectSystemAccess("ask")
              }

              Button {
                text: (root.healthSystemAccess === "off" ? "󰄬  " : "") + "Block Commands"
                focusable: true
                bordered: true
                foreground: root.foreground
                accent: root.accent
                enabled: !root.accessSaving
                tooltipText: "Disable Omar’s shell command tool"
                Accessible.name: (root.healthSystemAccess === "off" ? "Selected: " : "") + tooltipText
                onClicked: root.selectSystemAccess("off")
              }

              Button {
                text: (root.healthSystemAccess === "full" ? "󰄬  " : "")
                  + (root.fullAccessPending ? "Confirm Allow All" : "Allow All")
                focusable: true
                bordered: true
                foreground: root.foreground
                accent: root.accent
                enabled: !root.accessSaving
                tooltipText: "Run routine shell commands without asking"
                Accessible.name: (root.healthSystemAccess === "full" ? "Selected: " : "") + tooltipText
                onClicked: root.selectSystemAccess("full")
              }
            }

            Text {
              textFormat: Text.PlainText
              width: parent.width
              text: root.healthSystemAccess === "off"
                ? "Omar cannot run shell commands."
                : root.healthSystemAccess === "full"
                  ? "Routine commands run without asking. High-risk commands still need approval."
                  : "Approve each command, or allow routine commands for the next 15 minutes."
              wrapMode: Text.WordWrap
              color: Qt.darker(root.foreground, 1.35)
              font.family: root.bar ? root.bar.fontFamily : Style.font.family
              font.pixelSize: Style.font.bodySmall
              Accessible.name: text
            }

            Text {
              textFormat: Text.PlainText
              visible: root.accessSaveMessage !== ""
              width: parent.width
              text: root.accessSaveMessage
              wrapMode: Text.WordWrap
              color: root.fullAccessPending || root.healthSystemAccess === "full"
                ? root.accent
                : Qt.darker(root.foreground, 1.35)
              font.family: root.bar ? root.bar.fontFamily : Style.font.family
              font.pixelSize: Style.font.bodySmall
              Accessible.name: text
            }

            Button {
              text: setting("openOnStartup", false) ? "Open at login: On" : "Open at login: Off"
              focusable: true
              bordered: true
              foreground: root.foreground
              accent: root.accent
              onClicked: root.updateSetting("openOnStartup", !setting("openOnStartup", false))
            }

            Text {
              textFormat: Text.PlainText
              width: parent.width
              text: root.shownOnSummary()
              wrapMode: Text.WordWrap
              color: Qt.darker(root.foreground, 1.35)
              font.family: root.bar ? root.bar.fontFamily : Style.font.family
              font.pixelSize: Style.font.bodySmall
              Accessible.name: text
            }

            Repeater {
              model: root.availableScreens

              Button {
                required property var modelData
                readonly property bool selected: root.selectedDisplayNames.indexOf(String(modelData.name)) !== -1
                width: contentColumn.width
                text: (selected ? "󰄬  " : "     ") + root.displayLabel(modelData)
                leftAlign: true
                focusable: true
                bordered: true
                enabled: !selected || root.selectedDisplayNames.length > 1
                foreground: root.foreground
                accent: root.accent
                fontFamily: root.bar ? root.bar.fontFamily : Style.font.family
                tooltipText: selected && root.selectedDisplayNames.length === 1
                  ? "Ask Omar must remain on at least one display"
                  : (selected ? "Hide Ask Omar on this display" : "Show Ask Omar on this display")
                Accessible.name: (selected ? "Shown on " : "Not shown on ") + root.displayLabel(modelData)
                Keys.onEscapePressed: root.close()
                onClicked: root.toggleDisplay(modelData.name)
              }
            }

            Button {
              text: "Quit Ask Omar"
              focusable: true
              bordered: true
              foreground: root.foreground
              accent: root.accent
              tooltipText: "Close Ask Omar and stop its AI service until you open it again"
              onClicked: root.quitApplication()
            }

            Button {
              text: root.hideFromBarPending ? "Confirm hide from menu bar" : "Hide from menu bar"
              focusable: true
              bordered: true
              foreground: root.foreground
              accent: root.accent
              tooltipText: "Stop Ask Omar and remove it from the menu bar; reopen it later from Apps"
              onClicked: root.hideFromBar()
            }
          }

          Rectangle {
            visible: root.showIdleNotices
              && root.healthChecked
              && root.healthStatus !== "ready"
            width: parent.width
            height: visible ? connectionColumn.implicitHeight + Style.space(20) : 0
            color: "transparent"
            border.color: root.accent
            border.width: Math.max(1, Style.space(1))
            radius: Style.cornerRadius

            Column {
              id: connectionColumn
              anchors.fill: parent
              anchors.margins: Style.space(10)
              spacing: Style.space(7)

              Text {
                textFormat: Text.PlainText
                width: parent.width
                text: root.healthTitle()
                color: root.foreground
                font.family: root.bar ? root.bar.fontFamily : Style.font.family
                font.pixelSize: Style.font.body
                font.bold: true
                Accessible.name: text
              }

              Text {
                textFormat: Text.PlainText
                width: parent.width
                text: root.healthLabel()
                wrapMode: Text.WordWrap
                color: Qt.darker(root.foreground, 1.35)
                font.family: root.bar ? root.bar.fontFamily : Style.font.family
                font.pixelSize: Style.font.bodySmall
                Accessible.name: "Ask Omar status: " + text
              }

              Button {
                text: healthProcess.running ? "Checking…" : "Check again"
                enabled: !healthProcess.running
                focusable: true
                bordered: true
                foreground: root.foreground
                accent: root.accent
                Accessible.name: "Check the AI connection again"
                onClicked: root.checkHealth()
              }
            }
          }

          Rectangle {
            visible: root.showIdleNotices
              && root.healthStatus === "ready"
              && setting("safetyNoticeSeen", false) !== true
            width: parent.width
            height: visible ? safetyNoticeColumn.implicitHeight + Style.space(20) : 0
            color: "transparent"
            border.color: Color.popups.border
            border.width: Math.max(1, Style.space(1))
            radius: Style.cornerRadius

            Column {
              id: safetyNoticeColumn
              anchors.fill: parent
              anchors.margins: Style.space(10)
              spacing: Style.space(7)

              Text {
                textFormat: Text.PlainText
                width: parent.width
                text: "Omar can run commands on this computer"
                color: root.foreground
                font.family: root.bar ? root.bar.fontFamily : Style.font.family
                font.pixelSize: Style.font.body
                font.bold: true
                Accessible.name: text
              }

              Text {
                textFormat: Text.PlainText
                width: parent.width
                text: "Commands run with your permissions and are not sandboxed."
                wrapMode: Text.WordWrap
                color: Qt.darker(root.foreground, 1.35)
                font.family: root.bar ? root.bar.fontFamily : Style.font.family
                font.pixelSize: Style.font.bodySmall
                Accessible.name: text
              }

              Text {
                textFormat: Text.PlainText
                width: parent.width
                text: "Ask First is recommended"
                color: root.foreground
                font.family: root.bar ? root.bar.fontFamily : Style.font.family
                font.pixelSize: Style.font.bodySmall
                font.bold: true
                Accessible.name: text
              }

              Text {
                textFormat: Text.PlainText
                width: parent.width
                text: "Approve one command, or allow commands for the next 15 minutes."
                wrapMode: Text.WordWrap
                color: Qt.darker(root.foreground, 1.35)
                font.family: root.bar ? root.bar.fontFamily : Style.font.family
                font.pixelSize: Style.font.bodySmall
                Accessible.name: text
              }

              Text {
                textFormat: Text.PlainText
                width: parent.width
                text: "Want fewer prompts? Choose a different mode in Settings → Safety."
                wrapMode: Text.WordWrap
                color: Qt.darker(root.foreground, 1.35)
                font.family: root.bar ? root.bar.fontFamily : Style.font.family
                font.pixelSize: Style.font.bodySmall
                Accessible.name: text
              }

              Button {
                text: "Got it"
                focusable: true
                bordered: true
                foreground: root.foreground
                accent: root.accent
                Accessible.name: "Dismiss the Ask Omar safety explanation"
                onClicked: root.updateSetting("safetyNoticeSeen", true)
              }
            }
          }

          Row {
            visible: root.historyExpanded && !root.historyItemOpen
            width: parent.width
            spacing: Style.space(8)

            Button {
              id: backToSettingsListButton
              visible: root.showBackToSettings
              anchors.verticalCenter: parent.verticalCenter
              text: "Back to settings"
              focusable: true
              bordered: true
              foreground: root.foreground
              accent: root.accent
              fontFamily: root.bar ? root.bar.fontFamily : Style.font.family
              fontSize: Style.font.bodySmall
              horizontalPadding: Style.space(7)
              verticalPadding: Style.space(3)
              tooltipText: "Return to Ask Omar Settings"
              Accessible.name: tooltipText
              Keys.onEscapePressed: root.backToSettings()
              onClicked: root.backToSettings()
            }

            Text {
              textFormat: Text.PlainText
              width: Math.max(0, parent.width
                - (backToSettingsListButton.visible ? backToSettingsListButton.implicitWidth + parent.spacing : 0)
                - (clearHistoryButton.visible ? clearHistoryButton.implicitWidth + parent.spacing : 0))
              anchors.verticalCenter: parent.verticalCenter
              text: "Past answers"
              color: Qt.darker(root.foreground, 1.45)
              font.family: root.bar ? root.bar.fontFamily : Style.font.family
              font.pixelSize: Style.font.bodySmall
              Accessible.name: text
            }

            Button {
              id: clearHistoryButton
              visible: root.historyEntries.length > 0
              enabled: !root.busy && !clearHistoryProcess.running
              anchors.verticalCenter: parent.verticalCenter
              text: root.clearHistoryPending ? "Confirm clear all" : "Clear all"
              focusable: true
              bordered: true
              foreground: root.foreground
              accent: root.accent
              fontFamily: root.bar ? root.bar.fontFamily : Style.font.family
              fontSize: Style.font.bodySmall
              horizontalPadding: Style.space(7)
              verticalPadding: Style.space(3)
              tooltipText: root.clearHistoryPending
                ? "Confirm removal of all saved answers"
                : "Clear all saved answers on this machine"
              Accessible.name: tooltipText
              Keys.onEscapePressed: {
                if (root.historyItemOpen) root.clearHistoryPreview()
                else root.backFromAnswers()
              }
              onClicked: root.clearHistory()
            }
          }

          Text {
            textFormat: Text.PlainText
            visible: root.historyExpanded && !root.historyItemOpen && root.historyEntries.length === 0 && !historyProcess.running
            width: parent.width
            text: root.conversationTurns.length > 0
              ? "Nothing saved yet."
              : "Nothing saved yet.\nAsk Omar anything in the box above to start a conversation."
            color: root.foreground
            font.family: root.bar ? root.bar.fontFamily : Style.font.family
            font.pixelSize: Style.font.body
          }

          Column {
            visible: root.historyItemOpen && root.historyPreview !== null
            width: parent.width
            spacing: Style.space(8)

            Text {
              textFormat: Text.PlainText
              width: parent.width
              text: "You asked"
              color: Qt.darker(root.foreground, 1.55)
              font.family: root.bar ? root.bar.fontFamily : Style.font.family
              font.pixelSize: Style.font.bodySmall
              font.bold: true
              Accessible.name: text
            }

            Rectangle {
              width: parent.width
              height: historyAskBody.implicitHeight + Style.space(12)
              color: "transparent"
              border.width: 0

              Rectangle {
                width: Math.max(2, Style.space(2))
                anchors.left: parent.left
                anchors.top: parent.top
                anchors.bottom: parent.bottom
                color: Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.35)
              }

              Text {
                textFormat: Text.PlainText
                id: historyAskBody
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.leftMargin: Style.space(10)
                anchors.rightMargin: Style.space(4)
                text: root.historyQueryText
                wrapMode: Text.Wrap
                color: root.foreground
                font.family: root.bar ? root.bar.fontFamily : Style.font.family
                font.pixelSize: Style.font.body
              }
            }

            TextEdit {
              id: historyAnswerBody
              width: parent.width
              text: root.historyItemResponse
              textFormat: TextEdit.PlainText
              wrapMode: TextEdit.Wrap
              readOnly: true
              selectByMouse: true
              selectByKeyboard: true
              color: root.foreground
              font.family: root.bar ? root.bar.fontFamily : Style.font.family
              font.pixelSize: Style.font.body
              Accessible.name: "Saved Omar answer"
            }

            Button {
              visible: root.historyEntryKind === "stopped" && root.historyQueryText !== ""
              text: "Retry…"
              focusable: true
              bordered: true
              foreground: root.foreground
              accent: root.accent
              tooltipText: "Review the stopped request before running it again"
              Accessible.name: tooltipText
              onClicked: root.prepareStoppedRetry()
            }
          }

          Repeater {
            id: historyRepeater
            model: root.historyExpanded && !root.historyItemOpen ? root.historyEntries : []

            Row {
              required property var modelData
              width: contentColumn.width
              spacing: Style.space(8)

              Button {
                width: Math.max(Style.space(80), parent.width - timeLabel.implicitWidth - parent.spacing)
                text: {
                  var value = String(modelData.query || "").replace(/\s+/g, " ")
                  return value.length > 64 ? value.slice(0, 61) + "…" : value
                }
                tooltipText: String(modelData.query || "")
                leftAlign: true
                bordered: true
                focusable: true
                foreground: root.foreground
                accent: root.accent
                fontFamily: root.bar ? root.bar.fontFamily : Style.font.family
                Accessible.name: "Open saved answer: " + text
                Keys.onEscapePressed: root.backFromAnswers()
                onClicked: root.showHistoryEntry(modelData)
              }

              Text {
                textFormat: Text.PlainText
                id: timeLabel
                anchors.verticalCenter: parent.verticalCenter
                text: root.relativeTime(modelData.at)
                color: Qt.darker(root.foreground, 1.55)
                font.family: root.bar ? root.bar.fontFamily : Style.font.family
                font.pixelSize: Style.font.bodySmall
              }
            }
          }

          Text {
            textFormat: Text.PlainText
            visible: root.historyExpanded && !root.historyItemOpen && root.historyEntries.length > 0
            width: parent.width
            text: "Questions and answers saved on this machine. Opening one doesn't reopen the conversation."
            wrapMode: Text.WordWrap
            color: Qt.darker(root.foreground, 1.45)
            font.family: root.bar ? root.bar.fontFamily : Style.font.family
            font.pixelSize: Style.font.bodySmall
          }

          Text {
            textFormat: Text.PlainText
            visible: root.freshNotice && !root.busy && !root.historyExpanded && !root.settingsExpanded
            width: parent.width
            text: "New conversation. Omar has forgotten what came before."
            wrapMode: Text.WordWrap
            color: Qt.darker(root.foreground, 1.45)
            font.family: root.bar ? root.bar.fontFamily : Style.font.family
            font.pixelSize: Style.font.bodySmall
            Accessible.name: text
          }

          Column {
            id: chatThreadColumn
            visible: root.showChatThread
            width: parent.width
            spacing: Style.space(4)

            Repeater {
              id: chatTurnRepeater
              model: root.visibleTurns

              Column {
                id: turnRoot
                required property var modelData
                required property int index
                width: chatThreadColumn.width
                spacing: Style.space(2)

                readonly property bool fromYou: String(turnRoot.modelData.role || "") === "you"

                Text {
                  textFormat: Text.PlainText
                  visible: root.threadExpanded
                  anchors.right: turnRoot.fromYou ? parent.right : undefined
                  anchors.left: turnRoot.fromYou ? undefined : parent.left
                  text: turnRoot.fromYou ? "You" : "Omar"
                  color: Qt.darker(root.foreground, 1.5)
                  font.family: root.bar ? root.bar.fontFamily : Style.font.family
                  font.pixelSize: Style.font.bodySmall
                  font.bold: true
                  Accessible.name: text
                }

                Rectangle {
                  anchors.right: (root.threadExpanded && turnRoot.fromYou) ? parent.right : undefined
                  anchors.left: (root.threadExpanded && turnRoot.fromYou) ? undefined : parent.left
                  width: root.threadExpanded
                    ? Math.min(parent.width * 0.92, messageBody.implicitWidth + Style.space(16))
                    : parent.width
                  height: messageBody.implicitHeight + Style.space(12)
                  radius: Style.cornerRadius
                  color: turnRoot.fromYou
                    ? Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.16)
                    : (root.threadExpanded
                      ? Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.06)
                      : "transparent")
                  border.color: turnRoot.fromYou
                    ? Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.35)
                    : (root.threadExpanded ? Color.popups.border : "transparent")
                  border.width: root.threadExpanded ? Math.max(1, Style.space(1)) : 0

                  TextEdit {
                    id: messageBody
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.margins: Style.space(6)
                    text: String(turnRoot.modelData.text || "")
                    textFormat: TextEdit.PlainText
                    wrapMode: TextEdit.WordWrap
                    readOnly: true
                    selectByMouse: true
                    selectByKeyboard: true
                    activeFocusOnTab: true
                    persistentSelection: true
                    cursorVisible: false
                    color: root.foreground
                    selectionColor: Style.selectionFillFor(root.foreground, root.accent)
                    selectedTextColor: root.foreground
                    font.family: root.bar ? root.bar.fontFamily : Style.font.family
                    font.pixelSize: Style.font.body
                    Accessible.name: (turnRoot.fromYou ? "You said: " : "Omar replied: ") + text
                    Keys.onPressed: function(event) {
                      var control = (event.modifiers & Qt.ControlModifier) !== 0
                      if (control && event.key === Qt.Key_C) {
                        messageBody.copy()
                        event.accepted = true
                      } else if (control && event.key === Qt.Key_A) {
                        messageBody.selectAll()
                        event.accepted = true
                      } else if (event.key === Qt.Key_Escape) {
                        root.close()
                        event.accepted = true
                      }
                    }
                  }
                }
              }
            }

            TextEdit {
              id: answerText
              visible: false
              width: parent.width
              height: 0
              text: root.responseText
              textFormat: TextEdit.PlainText
              readOnly: true
              selectByMouse: true
              selectByKeyboard: true
              persistentSelection: true
            }

            Text {
              textFormat: Text.PlainText
              visible: root.busy && root.pendingConfirmation === null
              width: parent.width
              text: root.activityDisplay()
              color: Qt.darker(root.foreground, 1.6)
              font.family: root.bar ? root.bar.fontFamily : Style.font.family
              font.pixelSize: Style.font.bodySmall
              Accessible.name: root.busyLabel
            }
          }

          Rectangle {
            visible: root.busy && root.pendingConfirmation !== null
            width: parent.width
            color: Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.12)
            height: confirmColumn.implicitHeight + Style.space(16)
            radius: Style.cornerRadius

            Column {
              id: confirmColumn
              anchors.fill: parent
              anchors.margins: Style.space(8)
              spacing: Style.space(6)

              Text {
                textFormat: Text.PlainText
                width: parent.width
                text: "Review shell command"
                color: root.accent
                font.family: root.bar ? root.bar.fontFamily : Style.font.family
                font.pixelSize: Style.font.bodySmall
                font.bold: true
                Accessible.name: text
              }

              Text {
                textFormat: Text.PlainText
                width: parent.width
                text: {
                  var title = root.pendingConfirmation ? String(root.pendingConfirmation.title || "") : ""
                  var lines = title.split("\n")
                  return lines.length > 0 ? lines[0] : ""
                }
                wrapMode: Text.WordWrap
                color: root.foreground
                font.family: root.bar ? root.bar.fontFamily : Style.font.family
                font.pixelSize: Style.font.body
                Accessible.name: text
              }

              TextEdit {
                width: parent.width
                height: implicitHeight
                text: {
                  var title = root.pendingConfirmation ? String(root.pendingConfirmation.title || "") : ""
                  var lines = title.split("\n")
                  return lines.length > 1 ? lines.slice(1).join("\n") : ""
                }
                textFormat: TextEdit.PlainText
                wrapMode: TextEdit.WrapAnywhere
                readOnly: true
                selectByMouse: true
                selectByKeyboard: true
                persistentSelection: true
                cursorVisible: false
                color: Qt.darker(root.foreground, 1.5)
                selectionColor: Style.selectionFillFor(root.foreground, root.accent)
                selectedTextColor: root.foreground
                font.family: root.bar ? root.bar.fontFamily : Style.font.family
                font.pixelSize: Style.font.bodySmall
                Accessible.name: "Command to approve: " + text
              }

              Text {
                textFormat: Text.PlainText
                width: parent.width
                text: "Allow once runs only this command. Allow for 15 minutes covers routine commands in your next requests; high-risk commands still ask."
                wrapMode: Text.WordWrap
                color: Qt.darker(root.foreground, 1.5)
                font.family: root.bar ? root.bar.fontFamily : Style.font.family
                font.pixelSize: Style.font.bodySmall
                Accessible.name: text
              }

              Row {
                spacing: Style.space(8)

                Button {
                  text: "Deny"
                  focusable: true
                  bordered: true
                  foreground: root.foreground
                  accent: root.accent
                  fontFamily: root.bar ? root.bar.fontFamily : Style.font.family
                  fontSize: Style.font.bodySmall
                  Accessible.name: "Deny the command"
                  Keys.onEscapePressed: root.respondToConfirmation("Deny")
                  onClicked: root.respondToConfirmation("Deny")
                }

                Button {
                  text: "Allow once"
                  focusable: true
                  bordered: true
                  foreground: root.foreground
                  accent: root.accent
                  fontFamily: root.bar ? root.bar.fontFamily : Style.font.family
                  fontSize: Style.font.bodySmall
                  Accessible.name: "Allow the command once"
                  Keys.onEscapePressed: root.respondToConfirmation("Deny")
                  onClicked: root.respondToConfirmation("Allow once")
                }
              }

              Button {
                text: "Allow for 15 minutes"
                focusable: true
                bordered: true
                foreground: root.foreground
                accent: root.accent
                fontFamily: root.bar ? root.bar.fontFamily : Style.font.family
                fontSize: Style.font.bodySmall
                Accessible.name: "Allow shell commands for 15 minutes"
                Keys.onEscapePressed: root.respondToConfirmation("Deny")
                onClicked: root.respondToConfirmation("Allow for 15 minutes")
              }
            }
          }

          // Slow hint is folded into activityDisplay() so Working has one status line.
        }
      }

        Item {
          id: replyFooter
          width: parent.width
          height: resultPanel.replyChromeHeight
          visible: height > 0

          Rectangle {
            anchors.fill: parent
            color: resultPanel.color
          }

          Button {
            id: showChatButton
            visible: root.showChatToggle && !root.showPanelComposer
            anchors.left: parent.left
            anchors.verticalCenter: parent.verticalCenter
            text: root.threadExpanded ? "Hide chat" : "Show chat"
            focusable: true
            bordered: true
            foreground: root.foreground
            accent: root.accent
            fontFamily: root.bar ? root.bar.fontFamily : Style.font.family
            fontSize: Style.font.bodySmall
            horizontalPadding: Style.space(10)
            verticalPadding: Style.space(3)
            tooltipText: root.threadExpanded
              ? "Hide the conversation and show Omar's latest reply only"
              : "Show the full conversation Omar still remembers"
            Accessible.name: tooltipText
            Keys.onEscapePressed: {
              if (root.threadExpanded) root.threadExpanded = false
              else root.close()
            }
            onClicked: root.toggleThread()
          }

          Text {
            textFormat: Text.PlainText
            visible: root.showReplyButton && root.recapText !== "" && !root.busy && !root.showChatToggle
            anchors.left: parent.left
            anchors.right: replyButton.left
            anchors.rightMargin: Style.space(8)
            anchors.verticalCenter: parent.verticalCenter
            text: root.recapText
            elide: Text.ElideRight
            color: Qt.darker(root.foreground, 1.6)
            font.family: root.bar ? root.bar.fontFamily : Style.font.family
            font.pixelSize: Style.font.bodySmall
            Accessible.name: "Omar recap: " + text
          }

          Text {
            textFormat: Text.PlainText
            visible: root.showReplyButton && root.recapText !== "" && !root.busy && root.showChatToggle
            anchors.left: showChatButton.right
            anchors.leftMargin: Style.space(8)
            anchors.right: replyButton.left
            anchors.rightMargin: Style.space(8)
            anchors.verticalCenter: parent.verticalCenter
            text: root.recapText
            elide: Text.ElideRight
            color: Qt.darker(root.foreground, 1.6)
            font.family: root.bar ? root.bar.fontFamily : Style.font.family
            font.pixelSize: Style.font.bodySmall
            Accessible.name: "Omar recap: " + text
          }

          Row {
            id: answersFooterRow
            visible: root.historyExpanded && !root.showPanelComposer
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            spacing: Style.space(6)

            Button {
              visible: root.historyItemOpen
              text: "All answers"
              focusable: true
              bordered: true
              foreground: root.foreground
              accent: root.accent
              fontFamily: root.bar ? root.bar.fontFamily : Style.font.family
              fontSize: Style.font.bodySmall
              horizontalPadding: Style.space(10)
              verticalPadding: Style.space(3)
              tooltipText: "Back to the list of saved answers"
              Accessible.name: tooltipText
              Keys.onEscapePressed: root.clearHistoryPreview()
              onClicked: root.clearHistoryPreview()
            }

            Button {
              visible: root.showBackToSettings && root.historyItemOpen
              text: "Back to settings"
              focusable: true
              bordered: true
              foreground: root.foreground
              accent: root.accent
              fontFamily: root.bar ? root.bar.fontFamily : Style.font.family
              fontSize: Style.font.bodySmall
              horizontalPadding: Style.space(10)
              verticalPadding: Style.space(3)
              tooltipText: "Return to Ask Omar Settings"
              Accessible.name: tooltipText
              Keys.onEscapePressed: root.backToSettings()
              onClicked: root.backToSettings()
            }

            Button {
              visible: root.showBackToChat
              text: "Back to chat"
              focusable: true
              bordered: true
              foreground: root.foreground
              accent: root.accent
              fontFamily: root.bar ? root.bar.fontFamily : Style.font.family
              fontSize: Style.font.bodySmall
              horizontalPadding: Style.space(10)
              verticalPadding: Style.space(3)
              tooltipText: "Return to your current conversation"
              Accessible.name: tooltipText
              Keys.onEscapePressed: root.backToChat()
              onClicked: root.backToChat()
            }
          }

          Button {
            id: replyButton
            visible: root.showReplyButton
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            text: "Reply"
            enabled: !root.busy
            focusable: true
            bordered: true
            foreground: root.foreground
            accent: root.accent
            fontFamily: root.bar ? root.bar.fontFamily : Style.font.family
            fontSize: Style.font.bodySmall
            horizontalPadding: Style.space(10)
            verticalPadding: Style.space(3)
            tooltipText: "Reply to Omar in this conversation"
            Accessible.name: tooltipText
            Keys.onEscapePressed: {
              if (root.threadExpanded) root.threadExpanded = false
              else root.close()
            }
            onClicked: root.openReply()
          }

          // Whole strip under the reply opens Reply when the composer is collapsed.
          MouseArea {
            anchors.fill: parent
            z: -1
            enabled: root.showReplyButton && !root.busy
            hoverEnabled: enabled
            cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
            onClicked: root.openReply()
          }

          BorderSurface {
            id: panelComposer
            visible: root.showPanelComposer
            anchors.fill: parent
            color: Color.popups.background
            borderSpec: Border.controlSpec(panelComposerField.activeFocus ? "focus" : "normal", root.foreground, root.accent)
            radius: Style.cornerRadius

            TextField {
              id: panelComposerField
              anchors.fill: parent
              anchors.leftMargin: Style.space(8)
              anchors.rightMargin: Style.space(8)
              text: root.replyText
              placeholderText: "Reply to Omar…"
              foreground: root.foreground
              accent: root.accent
              enabled: !root.busy
              background: Item {}
              onTextChanged: root.replyText = text
              Accessible.name: "Reply to Omar"
              onAccepted: root.acceptField()
              Keys.onPressed: function(event) {
                if (event.key === Qt.Key_Escape) {
                  // Collapse Reply without wiping the draft or dismissing the panel.
                  root.replyExpanded = false
                  queryField.forceActiveFocus()
                  event.accepted = true
                }
              }
            }
          }
        }
        } // panelStack
      }
    }

    BorderSurface {
      id: scratchpadToolbar
      visible: root.opened && root.scratchpadMode
      x: root.fieldX
      y: root.fieldY
      width: root.width
      height: root.height
      color: Color.popups.background
      borderSpec: Border.controlSpec("focus", root.foreground, root.accent)
      radius: Style.cornerRadius

      Text {
        textFormat: Text.PlainText
        anchors.left: parent.left
        anchors.leftMargin: Style.space(10)
        anchors.right: scratchpadToolbarMic.left
        anchors.rightMargin: Style.space(6)
        anchors.verticalCenter: parent.verticalCenter
        text: "Ask Omar…"
        color: Qt.darker(root.foreground, 1.55)
        font.family: root.bar ? root.bar.fontFamily : Style.font.family
        font.pixelSize: Style.font.body
        Accessible.name: "Return to Ask Omar"
      }

      MicButton {
        id: scratchpadToolbarMic
        anchors.right: scratchpadToolbarMode.left
        anchors.verticalCenter: parent.verticalCenter
        size: root.iconWidth
        iconText: root.micState === "transcribing" ? "󰔟" : "󰍬"
        foreground: !root.voxtypeAvailable ? Qt.darker(root.foreground, 1.8)
          : (root.micState === "recording" ? root.accent : root.foreground)
        hoverColor: root.accent
        fontFamily: root.bar ? root.bar.fontFamily : Style.font.family
        tooltipText: !root.voxtypeAvailable ? "Install Voxtype for dictation"
          : (root.micState === "recording" ? "Click to stop · or release after holding"
          : "Dictate into scratchpad · click to start/stop · hold to talk")
        enabled: root.voxtypeAvailable
        focusable: true
        Accessible.name: tooltipText
        onClicked: root.microphone()
        onPointerPressed: root.microphonePressed()
        onPointerReleased: root.microphoneReleased()
      }

      PanelActionButton {
        id: scratchpadToolbarMode
        anchors.right: scratchpadToolbarCamera.left
        anchors.verticalCenter: parent.verticalCenter
        size: root.iconWidth
        iconText: "󰎚"
        foreground: root.accent
        hoverColor: root.accent
        fontFamily: root.bar ? root.bar.fontFamily : Style.font.family
        tooltipText: "Scratchpad is open"
        focusable: true
        Accessible.name: tooltipText
        onClicked: scratchpadField.forceActiveFocus()
      }

      Button {
        id: scratchpadToolbarCamera
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        width: root.iconWidth
        height: root.iconWidth
        iconText: root.recordingActive ? "■" : "󰄀"
        foreground: root.recordingActive ? root.accent : root.foreground
        accent: root.accent
        horizontalPadding: 0
        verticalPadding: 0
        fontFamily: root.bar ? root.bar.fontFamily : Style.font.family
        tooltipText: root.recordingActive
          ? "Stop screen recording"
          : "Click to choose a capture and attach it · right-click for options"
        focusable: true
        Accessible.name: tooltipText
        onClicked: root.camera()
        onRightClicked: root.showScreenshotChoices()
      }

      MouseArea {
        anchors.fill: parent
        anchors.rightMargin: root.iconWidth * 3
        cursorShape: Qt.IBeamCursor
        onClicked: root.showAssistant()
      }
    }

    BorderSurface {
      id: scratchpadPanel
      readonly property int desiredWidth: Math.max(root.width, Style.space(460))
      visible: root.opened && root.scratchpadMode
      x: Math.max(Style.gapsOut, Math.min(root.fieldX + root.width - width, assistantWindow.width - width - Style.gapsOut))
      y: root.bar && root.bar.position === "bottom"
        ? assistantWindow.height - (root.QsWindow.window ? root.QsWindow.window.height : root.height) - height - Style.gapsOut
        : (root.QsWindow.window ? root.QsWindow.window.height : root.height) + Style.gapsOut
      width: Math.min(desiredWidth, assistantWindow.width - Style.gapsOut * 2)
      height: Math.min(scratchpadColumn.implicitHeight + Style.space(28), assistantWindow.height * 0.8)
      color: Color.popups.background
      borderSpec: Border.surfaceSpec("popups", "border", Color.popups.border, Math.max(1, Style.space(1)))
      radius: Style.cornerRadius

      MouseArea {
        anchors.fill: parent
        onClicked: function(mouse) { mouse.accepted = true }
      }

      Column {
        id: scratchpadColumn
        anchors.fill: parent
        anchors.margins: Style.space(14)
        spacing: Style.space(8)

        Row {
          id: scratchpadHeader
          width: parent.width
          spacing: Style.space(6)

          Text {
            textFormat: Text.PlainText
            width: Math.max(0, parent.width - scratchpadDeleteButton.implicitWidth
              - scratchpadCopyButton.width - parent.spacing * 2)
            anchors.verticalCenter: parent.verticalCenter
            text: "Scratchpad"
            color: root.foreground
            font.family: root.bar ? root.bar.fontFamily : Style.font.family
            font.pixelSize: Style.font.heading
            font.bold: true
            Accessible.name: text
          }

          Button {
            id: scratchpadDeleteButton
            text: root.scratchpadDeletePending ? "Confirm delete" : "Delete note"
            focusable: true
            bordered: true
            foreground: root.foreground
            accent: root.accent
            fontFamily: root.bar ? root.bar.fontFamily : Style.font.family
            fontSize: Style.font.bodySmall
            tooltipText: root.scratchpadDeletePending ? "Confirm deleting this note" : "Delete this note"
            Accessible.name: tooltipText
            Keys.onEscapePressed: root.close()
            onClicked: root.deleteScratchpadNote()
          }

          PanelActionButton {
            id: scratchpadCopyButton
            iconText: root.copyFailed ? "!" : (root.copied ? "✓" : "󰆏")
            tooltipText: root.copyFailed ? "Copy failed"
              : (root.copied ? "Copied" : (scratchpadField.selectedText !== "" ? "Copy selection" : "Copy scratchpad"))
            foreground: root.foreground
            hoverColor: root.accent
            fontFamily: root.bar ? root.bar.fontFamily : Style.font.family
            focusable: true
            Accessible.name: tooltipText
            Keys.onEscapePressed: root.close()
            onClicked: root.copyScratchpad()
          }
        }

        Row {
          width: parent.width
          spacing: Style.space(5)

          PanelActionButton {
            iconText: "‹"
            size: Style.space(26)
            fontSize: Style.font.body
            enabled: root.scratchpadNoteIndex > 0
            foreground: root.foreground
            hoverColor: root.accent
            focusable: true
            tooltipText: "Previous note"
            Accessible.name: tooltipText
            onClicked: root.selectScratchpadNote(root.scratchpadNoteIndex - 1)
          }

          Text {
            textFormat: Text.PlainText
            anchors.verticalCenter: parent.verticalCenter
            text: "Note " + (root.scratchpadNoteIndex + 1) + " of " + root.scratchpadNotes.length
            color: root.foreground
            font.family: root.bar ? root.bar.fontFamily : Style.font.family
            font.pixelSize: Style.font.bodySmall
          }

          PanelActionButton {
            iconText: "›"
            size: Style.space(26)
            fontSize: Style.font.body
            enabled: root.scratchpadNoteIndex < root.scratchpadNotes.length - 1
            foreground: root.foreground
            hoverColor: root.accent
            focusable: true
            tooltipText: "Next note"
            Accessible.name: tooltipText
            onClicked: root.selectScratchpadNote(root.scratchpadNoteIndex + 1)
          }

          Button {
            text: "New note"
            enabled: root.scratchpadNotes.length < 20
            bordered: true
            focusable: true
            foreground: root.foreground
            accent: root.accent
            fontFamily: root.bar ? root.bar.fontFamily : Style.font.family
            fontSize: Style.font.bodySmall
            tooltipText: "Add a new scratchpad note"
            Accessible.name: tooltipText
            onClicked: root.addScratchpadNote()
          }
        }

        Text {
          textFormat: Text.PlainText
          width: parent.width
          text: "Use Markdown, bullets, file paths, or rough notes."
          wrapMode: Text.WordWrap
          color: Qt.darker(root.foreground, 1.45)
          font.family: root.bar ? root.bar.fontFamily : Style.font.family
          font.pixelSize: Style.font.bodySmall
        }

        Rectangle {
          id: scratchpadEditor
          width: parent.width
          height: Math.max(Style.space(140), Math.min(
            scratchpadField.contentHeight + Style.space(16),
            assistantWindow.height * 0.55))
          color: "transparent"
          border.color: Color.popups.border
          border.width: Math.max(1, Style.space(1))
          radius: Style.cornerRadius

          Flickable {
            id: scratchpadEditorFlickable
            anchors.fill: parent
            anchors.margins: Style.space(8)
            contentWidth: width
            contentHeight: scratchpadField.height
            clip: true
            boundsBehavior: Flickable.StopAtBounds

            TextEdit {
              id: scratchpadField
              width: scratchpadEditorFlickable.width
              height: Math.max(implicitHeight, scratchpadEditorFlickable.height)
              text: root.scratchpadText
              textFormat: TextEdit.PlainText
              wrapMode: TextEdit.WordWrap
              selectByMouse: true
              selectByKeyboard: true
              activeFocusOnTab: true
              persistentSelection: true
              color: root.foreground
              selectionColor: Style.selectionFillFor(root.foreground, root.accent)
              selectedTextColor: root.foreground
              font.family: root.bar ? root.bar.fontFamily : Style.font.family
              font.pixelSize: Style.font.body
              Accessible.name: "Scratchpad text"
              onTextChanged: root.scratchpadText = text
              onCursorRectangleChanged: {
                if (cursorRectangle.y < scratchpadEditorFlickable.contentY)
                  scratchpadEditorFlickable.contentY = cursorRectangle.y
                else if (cursorRectangle.y + cursorRectangle.height
                    > scratchpadEditorFlickable.contentY + scratchpadEditorFlickable.height)
                  scratchpadEditorFlickable.contentY = cursorRectangle.y + cursorRectangle.height
                    - scratchpadEditorFlickable.height
              }
              Keys.onPressed: function(event) {
                var control = (event.modifiers & Qt.ControlModifier) !== 0
                if (control && event.key === Qt.Key_C) {
                  scratchpadField.copy()
                  event.accepted = true
                } else if (control && event.key === Qt.Key_A) {
                  scratchpadField.selectAll()
                  event.accepted = true
                } else if (event.key === Qt.Key_Escape) {
                  root.close()
                  event.accepted = true
                }
              }
            }
          }
        }

        Flickable {
          id: scratchpadPreviews
          visible: root.scratchpadImages().length > 0
          width: parent.width
          height: visible ? Style.space(88) : 0
          contentWidth: previewRow.implicitWidth
          contentHeight: height
          clip: true

          Row {
            id: previewRow
            spacing: Style.space(8)

            Repeater {
              model: root.scratchpadImages()

              Rectangle {
                required property string modelData
                width: Style.space(120)
                height: scratchpadPreviews.height
                color: "transparent"
                border.color: Color.popups.border
                border.width: Math.max(1, Style.space(1))
                radius: Style.cornerRadius

                Image {
                  anchors.fill: parent
                  anchors.margins: Style.space(3)
                  source: parent.modelData
                  fillMode: Image.PreserveAspectCrop
                  asynchronous: true
                }
              }
            }
          }
        }

        Text {
          textFormat: Text.PlainText
          id: scratchpadHelp
          width: parent.width
          text: !root.backendInstalled
            ? "Ask Omar backend is missing. Install Ask Omar from the marketplace, or run make setup from its source directory."
            : root.scratchpadSaveState === "error" ? root.scratchpadSaveError
            : root.quitRequested ? "Saving before quit…"
            : root.scratchpadSaveState === "pending" ? "Scratchpad save pending…"
            : root.copied ? "Copied." : "Scratchpad saved locally."
          wrapMode: Text.WordWrap
          color: root.scratchpadSaveState === "error" || !root.backendInstalled
            ? root.accent : Qt.darker(root.foreground, 1.6)
          font.family: root.bar ? root.bar.fontFamily : Style.font.family
          font.pixelSize: Style.font.bodySmall
        }
        Button {
          visible: root.scratchpadSaveState === "error" && root.backendInstalled
          text: "Retry scratchpad save"
          focusable: true
          bordered: true
          foreground: root.foreground
          accent: root.accent
          onClicked: root.saveScratchpad()
        }
      }
    }

    BorderSurface {
      id: captureMenuPanel
      visible: root.screenshotMenuExpanded
      width: Math.min(Style.space(280), assistantWindow.width - Style.gapsOut * 2)
      height: captureMenuColumn.implicitHeight + Style.space(24)
      x: Math.max(Style.gapsOut, Math.min(
        root.fieldX + root.width - width,
        assistantWindow.width - width - Style.gapsOut))
      y: {
        var preferred = root.bar && root.bar.position === "bottom"
          ? root.fieldY - height - Style.gapsOut
          : root.fieldY + root.height + Style.gapsOut
        return Math.max(Style.gapsOut, Math.min(
          preferred,
          assistantWindow.height - height - Style.gapsOut))
      }
      color: Color.popups.background
      borderSpec: Border.surfaceSpec("popups", "border", Color.popups.border, Math.max(1, Style.space(1)))
      radius: Style.cornerRadius

      MouseArea {
        anchors.fill: parent
        onClicked: function(mouse) { mouse.accepted = true }
      }

      Column {
        id: captureMenuColumn
        anchors.fill: parent
        anchors.margins: Style.space(12)
        spacing: Style.space(4)

        Text {
          textFormat: Text.PlainText
          anchors.right: parent.right
          anchors.rightMargin: Style.space(10)
          text: "Screenshot"
          color: Qt.darker(root.foreground, 1.35)
          font.family: root.bar ? root.bar.fontFamily : Style.font.family
          font.pixelSize: Style.font.bodySmall
          font.bold: true
          Accessible.name: text
        }

        CaptureMenuButton {
          width: parent.width
          text: "Capture region"
          foreground: root.foreground
          accent: root.accent
          onClicked: root.startScreenshot("region")
        }

        CaptureMenuButton {
          width: parent.width
          text: "Capture window"
          foreground: root.foreground
          accent: root.accent
          onClicked: root.startScreenshot("windows")
        }

        CaptureMenuButton {
          width: parent.width
          text: "Capture current screen"
          foreground: root.foreground
          accent: root.accent
          onClicked: root.startScreenshot("fullscreen")
        }

        CaptureMenuButton {
          width: parent.width
          text: "Select now · capture in 5 seconds"
          foreground: root.foreground
          accent: root.accent
          onClicked: root.startScreenshot("delayed")
        }

        Text {
          textFormat: Text.PlainText
          anchors.right: parent.right
          anchors.rightMargin: Style.space(10)
          topPadding: Style.space(6)
          text: "Video · no audio"
          color: Qt.darker(root.foreground, 1.35)
          font.family: root.bar ? root.bar.fontFamily : Style.font.family
          font.pixelSize: Style.font.bodySmall
          font.bold: true
          Accessible.name: text
        }

        CaptureMenuButton {
          visible: !root.recordingActive
          width: parent.width
          text: "Record region"
          enabled: !recordingCheckProcess.running
          foreground: root.foreground
          accent: root.accent
          onClicked: root.startRecording(false)
        }

        CaptureMenuButton {
          visible: !root.recordingActive
          width: parent.width
          text: "Record current screen"
          enabled: !recordingCheckProcess.running
          foreground: root.foreground
          accent: root.accent
          onClicked: root.startRecording(true)
        }

        CaptureMenuButton {
          visible: root.recordingActive
          width: parent.width
          text: "Stop recording"
          enabled: !recordingCheckProcess.running
          foreground: root.foreground
          accent: root.accent
          onClicked: root.stopRecording()
        }
      }
    }
  }
}
