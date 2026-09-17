import unittest
import json
from pathlib import Path


QML = (Path(__file__).parents[1] / "plugin" / "AskOmar.qml").read_text(encoding="utf-8")
CAPTURE_HELPER = (Path(__file__).parents[1] / "scripts" / "capture.sh").read_text(encoding="utf-8")


class QmlInteractionContractTests(unittest.TestCase):
    def test_toolbar_brand_never_changes_to_reply(self):
        # Menubar / overlay field stay branded Ask Omar; Reply lives only in the panel.
        self.assertGreaterEqual(QML.count('"Ask Omar…"'), 2)
        self.assertIn('placeholderText: "Ask Omar…"', QML)
        self.assertIn('placeholderText: "Reply to Omar…"', QML)
        bar_placeholders = [
            line for line in QML.splitlines()
            if "placeholderText:" in line and "Ask Omar" in line
        ]
        self.assertTrue(any('"Ask Omar…"' in line for line in bar_placeholders))
        self.assertNotIn('placeholderText: "Reply to Omar…"', QML[QML.index("id: queryField"):QML.index("id: overlayMic")])

    def test_quick_actions_removed_from_panel(self):
        self.assertNotIn('text: "Quick actions"', QML)
        self.assertNotIn("showSuggestionList", QML)
        self.assertNotIn("loadSuggestions", QML)
        self.assertNotIn("suggestionsProcess", QML)
        self.assertNotIn('text: root.actionsExpanded ? "Hide actions" : "Actions"', QML)
        self.assertNotIn("(showFrequentlyUsed || actionsExpanded)", QML)

    def test_chat_thread_spike_controls_exist(self):
        self.assertIn("property var conversationTurns:", QML)
        self.assertIn("function appendConversationTurn(role, text)", QML)
        self.assertIn("id: chatThreadColumn", QML)
        self.assertIn("id: panelComposerField", QML)
        self.assertIn('placeholderText: "Reply to Omar…"', QML)
        self.assertIn('text: "Reply"', QML)
        self.assertIn("function openReply()", QML)
        self.assertIn("id: replyFooter", QML)
        self.assertIn("id: panelStack", QML)
        self.assertIn("maxBodyHeight", QML)
        self.assertIn("replyChromeHeight", QML)
        self.assertIn("scrollChatToEnd", QML)
        self.assertIn("Whole strip under the reply opens Reply", QML)
        self.assertIn("property bool threadExpanded", QML)
        self.assertIn("visibleTurns", QML)
        self.assertIn('text: root.threadExpanded ? "Hide chat" : "Show chat"', QML)
        self.assertIn("showChatToggle", QML)
        self.assertIn("compact panel underneath", QML)
        self.assertIn("showResultPanel", QML)
        self.assertIn("function toggleThread()", QML)
        self.assertIn("Brief grace: keep the last reply visible", QML)
        self.assertIn("function backToSettings()", QML)
        self.assertIn('text: "Back to settings"', QML)
        self.assertIn("openAnswersList(true)", QML)
        self.assertIn("showReplyChrome: showChatThread && !busy", QML)
        self.assertNotIn("id: memoryLineFootnote", QML)
        self.assertNotIn("id: memoryLineQuiet", QML)
        # Show chat / Hide chat toggle under Omar.s reply.
        self.assertIn('text: root.threadExpanded ? "Hide chat" : "Show chat"', QML)

    def test_result_lifecycle_controls_exist(self):
        self.assertIn('text: "Retry"', QML)
        self.assertIn('text: "Retry…"', QML)
        self.assertNotIn('text: "Last answer"', QML)
        self.assertIn("Past answers", QML)
        self.assertIn("failedQuery = submittedQuery", QML)
        self.assertIn("id: newConversationProcess", QML)
        self.assertIn("onStreamFinished: root.handleNewConversation(text)", QML)
        self.assertIn("enabled: !root.busy", QML)
        self.assertNotIn('bar.run("ask-omar new-conversation")', QML)

        open_function = QML[QML.index("  function open() {"):QML.index("  function close(cancelVoice)")]
        self.assertNotIn('errorText = ""', open_function)

    def test_dictation_fills_a_draft_without_auto_submitting(self):
        self.assertIn('tooltipText: !root.voxtypeAvailable ? "Install Voxtype for dictation"', QML)
        self.assertIn('"Click to start/stop · hold to talk"', QML)
        self.assertNotIn("voiceSubmitTimer", QML)
        self.assertNotIn("voicePending", QML)

    def test_dictation_supports_toggle_and_push_to_talk(self):
        self.assertIn("function microphonePressed()", QML)
        self.assertIn("function microphoneReleased()", QML)
        self.assertIn('bar.run("voxtype record start")', QML)
        self.assertIn('bar.run("voxtype record stop")', QML)
        self.assertIn("heldMilliseconds >= 350", QML)
        self.assertGreaterEqual(QML.count("onPointerPressed: root.microphonePressed()"), 2)
        self.assertGreaterEqual(QML.count("onPointerReleased: root.microphoneReleased()"), 2)
        self.assertIn("onPressed: if (root.voxtypeAvailable) root.microphonePressed()", QML)

    def test_busy_states_distinguish_queries_and_direct_actions(self):
        self.assertIn('busyLabel = "Working…"', QML)
        self.assertIn('busyLabel = "Running action…"', QML)
        self.assertIn('requestState = "stopping"', QML)
        self.assertIn('requestState = "stopped"', QML)
        self.assertIn('responseText = String(result.message || "Stopped.")', QML)

    def test_stop_control_is_accessible_and_close_does_not_stop(self):
        self.assertIn('stopProcess.command = ["ask-omar", "stop"]', QML)
        self.assertIn('tooltipText: "Stop the current Ask Omar request"', QML)
        self.assertIn("Accessible.name: tooltipText", QML)
        self.assertIn("function handleStop(raw)", QML)
        close_function = QML[QML.index("  function close(cancelVoice)"):QML.index("  function toggle()")]
        self.assertNotIn("stopCurrentRequest", close_function)
        self.assertNotIn('["ask-omar", "stop"]', close_function)

    def test_preserved_non_agentic_controls_remain(self):
        self.assertIn("function microphone()", QML)
        self.assertIn('text: "New"', QML)
        self.assertIn('text: "Past answers"', QML)
        self.assertNotIn('text: "Answers"', QML)
        self.assertNotIn('text: root.historyExpanded ? "Hide history" : "History"', QML)
        self.assertNotIn('text: "Hide history"', QML)
        self.assertIn('text: root.clearHistoryPending ? "Confirm clear all" : "Clear all"', QML)
        self.assertIn('clearHistoryProcess.command = ["ask-omar", "clear-history"]', QML)
        self.assertIn('"Clear all saved answers on this machine"', QML)

    def test_header_has_session_controls_then_settings_and_close(self):
        header = QML[QML.index("id: resultHeader"):QML.index("id: resultActions")]
        self.assertNotIn("id: historyButton", header)
        self.assertIn("id: newConversationButton", header)
        self.assertNotIn("id: threadPeekButton", header)
        self.assertNotIn("id: clearHistoryButton", header)
        self.assertLess(header.index("id: newConversationButton"), header.index("id: settingsButton"))
        self.assertLess(header.index("id: settingsButton"), header.index("id: closeButton"))
        self.assertIn('iconText: "󰒓"', header)
        self.assertIn('iconText: "󰅖"', header)
        self.assertNotIn('text: "Answers"', header)
        self.assertNotIn('text: "Hide history"', header)

    def test_copy_uses_argv_and_answers_support_partial_selection(self):
        self.assertIn('copyProcess.command = ["wl-copy", "--", value]', QML)
        self.assertNotIn('bar.run("printf %s "', QML)
        self.assertIn("id: answerText", QML)
        self.assertIn("selectByMouse: true", QML)
        self.assertIn("selectByKeyboard: true", QML)
        self.assertIn("persistentSelection: true", QML)
        self.assertIn("messageBody.copy()", QML)
        self.assertIn("onResponseTextChanged", QML)
        self.assertIn("copyFailed = false", QML)
        self.assertIn("answerText.deselect()", QML)
        self.assertIn("function focusAnswer(): string", QML)

    def test_compact_local_history_view_exists(self):
        self.assertIn('text: "Past answers"', QML)
        self.assertIn('historyProcess.command = ["ask-omar", "history"]', QML)
        self.assertIn("function showHistory()", QML)
        self.assertIn("else if (showHistory) root.showHistory()", QML)
        self.assertIn("root.showHistoryEntry(modelData)", QML)
        self.assertIn("Opening one doesn't reopen the conversation", QML)
        self.assertIn("id: clearHistoryButton", QML)
        self.assertIn("property var historyPreview", QML)
        self.assertIn("property string panelView", QML)
        self.assertIn("function backToChat()", QML)
        self.assertIn('text: "Back to chat"', QML)
        self.assertIn('text: "All answers"', QML)
        self.assertIn("historyItemResponse", QML)
        self.assertIn('text: "You asked"', QML)
        self.assertNotIn("stashedConversationTurns", QML)
        self.assertNotIn('text: "Back to list"', QML)
        self.assertNotIn('text: "History"', QML)

    def test_keyboard_and_accessibility_hooks_exist(self):
        self.assertIn('Accessible.name: "Ask Omar request"', QML)
        self.assertIn("focusable: true", QML)
        self.assertIn('sequence: "Escape"', QML)
        self.assertIn("context: Qt.WindowShortcut", QML)

    def test_visible_close_control_exists(self):
        self.assertIn("id: closeButton", QML)
        self.assertIn('iconText: "󰅖"', QML)
        self.assertIn('tooltipText: "Close Ask Omar"', QML)
        self.assertIn("onClicked: root.close()", QML)

    def test_display_selector_uses_connected_display_names(self):
        self.assertIn("if (screen.width > 0 && screen.height > 0) screens.push(screen)", QML)
        self.assertIn('model + " (" + connector + ")"', QML)
        self.assertIn('return "Shown on: "', QML)
        self.assertIn('updateSetting("displays", next)', QML)
        self.assertIn("return all", QML)
        self.assertNotIn('text: root.allMonitors ? "All monitors: On"', QML)
        manifest = json.loads((Path(__file__).parents[1] / "plugin" / "manifest.json").read_text())
        self.assertEqual(manifest["barWidget"]["defaults"]["displays"], [])

    def test_open_starts_service_before_revealing_panel(self):
        open_block = QML[QML.index("  function open() {"):QML.index("  function showSettings()")]
        self.assertIn('["systemctl", "--user", "start", "ask-omar.service"]', open_block)
        self.assertNotIn("reveal()", open_block)
        service_block = QML[QML.index("id: serviceStartProcess"):QML.index('command: ["omarchy-voxtype-status"]')]
        self.assertIn("root.reveal()", service_block)

    def test_screenshot_uses_process_and_captures_path(self):
        self.assertIn('captureLauncher.command = ["ask-omar-capture", "screenshot", root.screenshotMode, root.screenshotTarget]', QML)
        self.assertIn("captureLauncher.startDetached()", QML)
        self.assertIn('startScreenshot("smart")', QML)
        self.assertIn('path=$(omarchy capture screenshot "$mode" save)', CAPTURE_HELPER)
        self.assertIn('wl-copy -- "$path"', CAPTURE_HELPER)
        self.assertIn('notify_screenshot "$path" "File path copied · $path"', CAPTURE_HELPER)
        self.assertIn('text: "Select now · capture in 5 seconds"', QML)
        self.assertIn("id: screenshotDelayTimer", QML)
        self.assertIn('startScreenshot("region")', QML)
        self.assertIn('startScreenshot("windows")', QML)
        self.assertIn('startScreenshot("fullscreen")', QML)
        self.assertIn('startScreenshot("delayed")', QML)
        self.assertIn("omarchy-capture-region smart --keep-freeze", CAPTURE_HELPER)
        self.assertLess(CAPTURE_HELPER.index('kill "$freeze_pid"'),
                        CAPTURE_HELPER.index("for remaining in 5 4 3 2 1"))
        self.assertLess(CAPTURE_HELPER.index("for remaining in 5 4 3 2 1"),
                        CAPTURE_HELPER.index('grim -g "$selection" "$path"'))
        self.assertLess(CAPTURE_HELPER.index('notifications dismiss "Capturing in"'),
                        CAPTURE_HELPER.index('grim -g "$selection" "$path"'))
        self.assertIn("screenshotDelayTimer.interval = 200", QML)
        self.assertLess(QML.index("close(false)", QML.index("function startScreenshot")),
                        QML.index("screenshotDelayTimer.restart()", QML.index("function startScreenshot")))
        self.assertIn("onRightClicked: root.showScreenshotChoices()", QML)
        self.assertIn("mouse.button === Qt.RightButton", QML)

    def test_capture_menu_supports_silent_video_recording(self):
        self.assertIn('text: "Video · no audio"', QML)
        self.assertIn('text: "Record region"', QML)
        self.assertIn('text: "Record current screen"', QML)
        self.assertIn('text: "Stop recording"', QML)
        self.assertIn('"record-start"', QML)
        self.assertIn('["ask-omar-capture", "record-stop", recordingTarget]', QML)
        self.assertIn("omarchy capture screenrecording --fullscreen", CAPTURE_HELPER)
        self.assertIn("omarchy capture screenrecording --stop-recording", CAPTURE_HELPER)
        self.assertIn('recordingCheckProcess.command = ["pgrep", "-f", "^gpu-screen-recorder"]', QML)
        self.assertIn('root.recordingActive ? "■"', QML)
        self.assertIn('"Stop screen recording"', QML)

    def test_right_click_capture_menu_is_contextual_not_panel_content(self):
        self.assertIn("id: captureMenuPanel", QML)
        self.assertIn("visible: root.opened || root.screenshotMenuExpanded", QML)
        show_choices = QML[QML.index("function showScreenshotChoices()"):QML.index("function startScreenshot(")]
        self.assertNotIn("root.open()", show_choices)
        self.assertGreater(QML.index("id: captureMenuPanel"), QML.index("id: scratchpadPanel"))
        result_panel = QML[QML.index("id: resultPanel"):QML.index("id: scratchpadToolbar")]
        scratchpad_panel = QML[QML.index("id: scratchpadPanel"):QML.index("id: captureMenuPanel")]
        self.assertNotIn("screenshotMenuExpanded", result_panel)
        self.assertNotIn("screenshotMenuExpanded", scratchpad_panel)
        self.assertIn("root.fieldX + root.width - width", QML)
        self.assertGreaterEqual(QML.count("anchors.rightMargin: Style.space(10)"), 3)
        self.assertIn("component CaptureMenuButton", QML)

    def test_health_check_and_readiness_chip_exist(self):
        self.assertIn("function checkHealth()", QML)
        self.assertIn("function handleHealth(raw)", QML)
        self.assertIn("function healthLabel()", QML)
        self.assertIn('healthProcess.command = ["ask-omar", "health"]', QML)
        self.assertIn("healthStatus", QML)
        self.assertIn('text: healthProcess.running ? "Checking…" : "Check again"', QML)
        self.assertIn("Pi is needed for AI requests", QML)
        self.assertIn("Choose a model in Settings", QML)
        self.assertIn("Don't paste passwords, tokens, or sign-in codes into Ask Omar", QML)
        self.assertIn("function aiUnavailable()", QML)

    def test_idle_notices_remain_visible_during_ai_errors(self):
        line = [row for row in QML.splitlines() if "readonly property bool showIdleNotices" in row][0]
        self.assertNotIn("errorText", line)

    def test_settings_exposes_model_and_reasoning_controls(self):
        self.assertIn('text: "AI connection"', QML)
        self.assertIn('text: "Safety"', QML)
        self.assertIn("There is no sandbox", QML)
        self.assertIn("cannot recognise every dangerous command", QML)
        self.assertIn('"Change model or reasoning…"', QML)
        self.assertIn('ask-omar", "models"', QML)
        self.assertIn('ask-omar", "set-agent"', QML)
        self.assertIn("function loadModels()", QML)
        self.assertIn("function selectThinking(level)", QML)
        self.assertIn('setting("safetyNoticeSeen", false)', QML)
        self.assertIn('updateSetting("safetyNoticeSeen", true)', QML)

    def test_dictation_availability_detection(self):
        self.assertIn("voxtypeAvailable", QML)
        self.assertIn("voxtypeCheckProcess", QML)
        self.assertIn("Install Voxtype for dictation", QML)

    def test_slow_hint_timer_exists(self):
        self.assertIn("id: slowHintTimer", QML)
        self.assertIn("interval: 20000", QML)
        self.assertIn("showSlowHint", QML)
        self.assertIn("Still working… You can wait or press Stop.", QML)

    def test_recap_line_exists(self):
        self.assertIn("recapText", QML)
        self.assertIn("Omar recap:", QML)

    def test_clear_history_auto_collapses(self):
        clear_block = QML[QML.index("function handleClearHistory(raw)"):QML.index("  function camera()")]
        self.assertIn('panelView = "chat"', clear_block)

    def test_guard_extension_confirmation_ui_exists(self):
        self.assertIn("pendingConfirmation", QML)
        self.assertIn("function respondToConfirmation(response)", QML)
        self.assertIn('confirmProcess.command = ["ask-omar", "confirm", requestId, response]', QML)
        self.assertIn("Allow this command?", QML)
        self.assertIn('"Allow the command once"', QML)
        self.assertIn('"Deny the command"', QML)
        self.assertIn('text: "On this computer · Allow once"', QML)
        self.assertNotIn("opacity: 0.12", QML)

    def test_activity_is_discreet_and_inline(self):
        self.assertIn("root.activityDisplay()", QML)
        self.assertNotIn('text: root.activityExpanded ? "Hide details" : "Details"', QML)
        self.assertNotIn("latest progress message", QML)

    def test_confirmation_polling_via_activity(self):
        self.assertIn("result.confirmation", QML)
        self.assertIn("pendingConfirmation = result.confirmation", QML)
        timer = QML[QML.index("id: activityTimer"):QML.index("id: draftSaveTimer")]
        self.assertIn("interval: 1000", timer)
        self.assertIn("root.loadActivity()", timer)
        self.assertNotIn("activityExpanded", timer)

    def test_close_auto_denies_pending_confirmation(self):
        close_block = QML[QML.index("  function close(cancelVoice)"):QML.index("  function toggle()")]
        self.assertIn("respondToConfirmation", close_block)

    def test_guard_config_is_installable(self):
        from pathlib import Path
        guard_example = Path(__file__).parents[1] / "config" / "guard.example.json"
        self.assertTrue(guard_example.exists())
        import json
        config = json.loads(guard_example.read_text())
        self.assertIn("hardBlocked", config)
        self.assertIn("confirmRequired", config)
        self.assertIn("safeExceptions", config)
        self.assertTrue(len(config["confirmRequired"]) > 0)

    def test_hard_block_explains_terminal_fallback(self):
        guard = (Path(__file__).parents[1] / "service" / "ask_omar" / "extensions" / "ask-omar-guard.ts").read_text()
        self.assertIn("open a terminal and run it yourself", guard)
        self.assertIn("no confirmation panel available", guard)

    def test_scratchpad_has_a_bar_entry_and_autosaves(self):
        self.assertIn('id: barScratchpad', QML)
        self.assertIn('text: "󰎚"', QML)
        self.assertIn("function openScratchpad()", QML)
        self.assertIn('scratchpadSaveProcess.command = ["ask-omar", "scratchpad-notes-save", JSON.stringify(root.scratchpadNotes)]', QML)
        self.assertIn('scratchpadLoadProcess.command = ["ask-omar", "scratchpad-notes"]', QML)
        self.assertIn("id: scratchpadToolbar", QML)
        self.assertIn("onClicked: root.showAssistant()", QML)

    def test_scratchpad_supports_copy_delete_and_markdown_notes(self):
        self.assertIn("function copyScratchpad()", QML)
        self.assertIn("function deleteScratchpadNote()", QML)
        self.assertIn('text: root.scratchpadDeletePending ? "Confirm delete" : "Delete note"', QML)
        self.assertIn('text: "New note"', QML)
        self.assertIn('text: "Note " + (root.scratchpadNoteIndex + 1)', QML)
        self.assertIn("Saved locally. Use Markdown, bullets, file paths, or rough notes.", QML)
        self.assertIn('Accessible.name: "Scratchpad text"', QML)

    def test_scratchpad_routes_dictation_and_screenshots_into_notes(self):
        self.assertIn("if (root.scratchpadMode) root.appendScratchpadText(text)", QML)
        self.assertIn("Dictate into scratchpad", QML)
        self.assertIn("function appendScratchpad(text: string)", QML)
        self.assertIn('response=$(ask-omar scratchpad-attach "$path")', CAPTURE_HELPER)
        self.assertIn('notify_shell appendScratchpad "$markdown"', CAPTURE_HELPER)
        self.assertIn("choose a capture and attach", QML)

    def test_overlay_keeps_all_three_tools_visible(self):
        self.assertIn("id: overlayScratchpad", QML)
        self.assertIn("id: scratchpadToolbarMic", QML)
        self.assertIn("id: scratchpadToolbarMode", QML)
        self.assertIn("id: scratchpadToolbarCamera", QML)

    def test_scratchpad_toolbar_field_returns_to_ask_omar(self):
        toolbar = QML[QML.index("id: scratchpadToolbar"):QML.index("id: scratchpadPanel")]
        self.assertIn('text: "Ask Omar…"', toolbar)
        self.assertIn("onClicked: root.showAssistant()", toolbar)
        self.assertNotIn("id: scratchpadToolbarNote", toolbar)
        self.assertNotIn("id: scratchpadBackButton", QML)

    def test_scratchpad_grows_then_scrolls_for_long_notes(self):
        self.assertIn("scratchpadColumn.implicitHeight", QML)
        self.assertIn("assistantWindow.height * 0.8", QML)
        self.assertIn("scratchpadField.contentHeight", QML)
        self.assertIn("id: scratchpadEditorFlickable", QML)
        self.assertIn("contentHeight: scratchpadField.height", QML)

    def test_settings_quit_stops_background_service_without_restart_timers(self):
        self.assertIn('text: "Quit Ask Omar"', QML)
        self.assertIn("function quitApplication()", QML)
        self.assertIn("draftSaveTimer.stop()", QML)
        self.assertIn("scratchpadSaveTimer.stop()", QML)
        self.assertIn('["systemctl", "--user", "stop", "ask-omar.service"]', QML)
        self.assertNotIn('"Confirm stop service"', QML)
        self.assertNotIn('text: "Terminate Ask Omar"', QML)
        self.assertIn('text: root.restarting ? "Restarting…" : "Restart Ask Omar"', QML)
        self.assertIn("function restartApplication()", QML)

    def test_settings_can_hide_bar_widget_until_reopened_from_apps(self):
        self.assertIn("visible: shownOnOwnDisplay && !hiddenFromBar", QML)
        self.assertIn('text: root.hideFromBarPending ? "Confirm hide from menu bar" : "Hide from menu bar"', QML)
        self.assertIn('updateSetting("hiddenFromBar", true)', QML)
        self.assertGreaterEqual(QML.count('if (hiddenFromBar) updateSetting("hiddenFromBar", false)'), 3)
        self.assertIn("setting(\"openOnStartup\", false) === true && !hiddenFromBar", QML)
        manifest = json.loads((Path(__file__).parents[1] / "plugin" / "manifest.json").read_text())
        self.assertFalse(manifest["barWidget"]["defaults"]["hiddenFromBar"])

    def test_history_separates_question_and_response(self):
        self.assertIn('text: turnRoot.fromYou ? "You" : "Omar"', QML)
        self.assertIn("property var conversationTurns:", QML)

    def test_scratchpad_note_navigation_is_subtle(self):
        self.assertNotIn('text: "‹ Previous"', QML)
        self.assertNotIn('text: "Next ›"', QML)
        self.assertIn('tooltipText: "Previous note"', QML)
        self.assertIn('tooltipText: "Next note"', QML)

    def test_scratchpad_renders_local_screenshot_previews(self):
        self.assertIn("function scratchpadImages()", QML)
        self.assertIn("id: scratchpadPreviews", QML)
        self.assertIn("source: parent.modelData", QML)
        self.assertIn("Image.PreserveAspectCrop", QML)


if __name__ == "__main__":
    unittest.main()
