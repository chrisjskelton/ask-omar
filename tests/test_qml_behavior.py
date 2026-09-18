"""Exercise the release-critical QML JavaScript without a running desktop shell."""

import shutil
import subprocess
import unittest
import json
from pathlib import Path


QML = (Path(__file__).parents[1] / "plugin" / "AskOmar.qml").read_text(encoding="utf-8")


def qml_function(name):
    marker = f"  function {name}("
    start = QML.index(marker)
    next_function = QML.find("\n  function ", start + len(marker))
    return QML[start:next_function if next_function >= 0 else len(QML)]


def functions(*names):
    return "vm.runInContext(" + json.dumps("\n".join(qml_function(name) for name in names)) + ", context);"


def run_node(script):
    result = subprocess.run(["node", "-e", script], capture_output=True, text=True)
    if result.returncode:
        raise AssertionError(result.stderr)


@unittest.skipUnless(shutil.which("node"), "Node.js is needed to exercise QML JavaScript")
class QmlBehaviorTests(unittest.TestCase):
    def test_copy_answer_uses_stdin_for_selection_or_full_body(self):
        script = "\n".join((
            'const vm = require("node:vm"); const assert = require("node:assert/strict");',
            'const calls = []; const full = "--private-answer\\nline two 😀";',
            'const context = {responseText:full, copyProcess:{running:false},',
            '  answerText:{selectedText:"--selected\\n😀"}, copied:true, copyFailed:true,',
            '  startStdinCommand:(proc,argv,body)=>calls.push({proc,argv,body})};',
            'vm.createContext(context);', functions("copyResponse"),
            'vm.runInContext(`copyResponse()`, context);',
            'assert.equal(calls.length, 1);',
            'assert.deepEqual(Array.from(calls[0].argv), ["wl-copy"]);',
            'assert.equal(calls[0].body, "--selected\\n😀");',
            'assert.equal(calls[0].argv.includes(full), false);',
            'assert.equal(context.copied, false); assert.equal(context.copyFailed, false);',
            'context.answerText.selectedText = "";',
            'vm.runInContext(`copyResponse()`, context);',
            'assert.equal(calls.length, 2); assert.equal(calls[1].body, full);',
            'assert.deepEqual(Array.from(calls[1].argv), ["wl-copy"]);',
            'context.copyProcess.running = true;',
            'vm.runInContext(`copyResponse()`, context);',
            'assert.equal(calls.length, 2);',
            'context.copyProcess.running = false; context.responseText = "";',
            'vm.runInContext(`copyResponse()`, context);',
            'assert.equal(calls.length, 2);',
        ))
        run_node(script)

    def test_copy_scratchpad_uses_stdin_for_selection_or_full_body(self):
        script = "\n".join((
            'const vm = require("node:vm"); const assert = require("node:assert/strict");',
            'const calls = []; const full = "-private note\\nsecond line 😀";',
            'const context = {scratchpadText:full, copyProcess:{running:false},',
            '  scratchpadField:{selectedText:"-selected\\n😀"}, copied:true, copyFailed:true,',
            '  startStdinCommand:(proc,argv,body)=>calls.push({proc,argv,body})};',
            'vm.createContext(context);', functions("copyScratchpad"),
            'vm.runInContext(`copyScratchpad()`, context);',
            'assert.equal(calls.length, 1);',
            'assert.deepEqual(Array.from(calls[0].argv), ["wl-copy"]);',
            'assert.equal(calls[0].body, "-selected\\n😀");',
            'assert.equal(calls[0].argv.includes(full), false);',
            'assert.equal(context.copied, false); assert.equal(context.copyFailed, false);',
            'context.scratchpadField.selectedText = "";',
            'vm.runInContext(`copyScratchpad()`, context);',
            'assert.equal(calls.length, 2); assert.equal(calls[1].body, full);',
            'assert.deepEqual(Array.from(calls[1].argv), ["wl-copy"]);',
            'context.copyProcess.running = true;',
            'vm.runInContext(`copyScratchpad()`, context);',
            'assert.equal(calls.length, 2);',
            'context.copyProcess.running = false; context.scratchpadText = "";',
            'vm.runInContext(`copyScratchpad()`, context);',
            'assert.equal(calls.length, 2);',
        ))
        run_node(script)

    def test_backend_guidance_and_plain_answer_rendering(self):
        self.assertIn("Install Ask Omar from the marketplace, or run make setup", QML)
        self.assertNotIn("TextEdit.MarkdownText", QML)
        self.assertIn("textFormat: TextEdit.PlainText", QML)

    def test_oversized_question_keeps_both_composers(self):
        script = "\n".join((
            'const vm = require("node:vm"); const assert = require("node:assert/strict");',
            'const context = { queryText: "menubar draft", replyText: "panel draft", busy: false,',
            '  queryProcess: { running: false }, resultVisible: false, errorText: "" };',
            'vm.createContext(context);',
            functions("characterCount", "submit"),
            'vm.runInContext(`submit("x".repeat(2001))`, context);',
            'assert.equal(context.queryText, "menubar draft");',
            'assert.equal(context.replyText, "panel draft");',
            'assert.equal(context.resultVisible, true);',
            'assert.match(context.errorText, /2,000 characters/);',
            'assert.equal(context.busy, false);',
        ))
        run_node(script)

    def test_astral_characters_match_backend_length_limits(self):
        script = "\n".join((
            'const vm = require("node:vm"); const assert = require("node:assert/strict");',
            'const commands = [];',
            'const context = {queryText:"", replyText:"", busy:false, queryProcess:{running:false},',
            '  conversationTurns:[], resultVisible:false, errorText:"",',
            '  aiUnavailable:()=>true, checkHealth:()=>{}, draftSaveProcess:{running:false},',
            '  scratchpadSaveProcess:{running:false}, draftVersion:1, scratchpadVersion:1,',
            '  scratchpadNotes:[""], draftSaveState:"pending", draftSaveError:"",',
            '  scratchpadSaveState:"pending", scratchpadSaveError:"",',
            '  flushPendingSaves:()=>{},',
            '  startStdinCommand:(proc,argv,body)=>{commands.push(body);proc.running=true} };',
            'vm.createContext(context);',
            functions("characterCount", "submit", "saveDraft", "saveScratchpad"),
            'const emoji = "😀";',
            'assert.equal(vm.runInContext(`characterCount("😀")`, context), 1);',
            'vm.runInContext(`submit("😀".repeat(2000))`, context);',
            'assert.equal(context.errorText, "");',
            'vm.runInContext(`submit("😀".repeat(2001))`, context);',
            'assert.match(context.errorText, /2,000 characters/);',
            'context.queryText = emoji.repeat(2000); context.draftSaveProcess.running = false;',
            'vm.runInContext(`saveDraft()`, context);',
            'assert.equal(context.draftSaveState, "pending");',
            'assert.equal(commands.at(-1), emoji.repeat(2000));',
            'context.queryText = emoji.repeat(2001); context.draftSaveProcess.running = false;',
            'vm.runInContext(`saveDraft()`, context);',
            'assert.equal(context.draftSaveState, "error");',
            'context.scratchpadNotes = [emoji.repeat(20000)];',
            'vm.runInContext(`saveScratchpad()`, context);',
            'assert.equal(context.scratchpadSaveState, "pending");',
            'context.scratchpadNotes = [emoji.repeat(20001)]; context.scratchpadSaveProcess.running = false;',
            'vm.runInContext(`saveScratchpad()`, context);',
            'assert.equal(context.scratchpadSaveState, "error");',
        ))
        run_node(script)

    def test_save_ack_failure_and_stale_ack_keep_latest_text(self):
        script = "\n".join((
            'const vm = require("node:vm"); const assert = require("node:assert/strict");',
            'const later = []; const commands = [];',
            'const context = { queryText: "unsaved", draftVersion: 1, savedDraftVersion: 0,',
            '  draftSaveState: "pending", draftSaveError: "", scratchpadNotes: ["note"],',
            '  scratchpadVersion: 1, savedScratchpadVersion: 0, scratchpadSaveState: "pending",',
            '  scratchpadSaveError: "", quitRequested: false,',
            '  draftSaveProcess: { running: false }, scratchpadSaveProcess: { running: false },',
            '  Qt: { callLater: fn => later.push(fn) },',
            '  startStdinCommand: (proc, argv, body) => { commands.push([argv, body]); proc.running = true; },',
            '  flushPendingSaves: () => {} }; context.root = context;',
            'vm.createContext(context);',
            functions("characterCount", "saveDraft", "saveScratchpad", "handleSave"),
            'vm.runInContext(`handleSave(JSON.stringify({ok:false,error:"disk full",error_code:"draft_too_long"}),"draft",1)`, context);',
            'assert.equal(context.draftSaveState, "error"); assert.equal(context.draftSaveError, "disk full");',
            'assert.equal(context.queryText, "unsaved");',
            'vm.runInContext(`handleSave(JSON.stringify({ok:false,error:"note too long"}),"scratchpad",1)`, context);',
            'assert.equal(context.scratchpadSaveState, "error");',
            'assert.equal(context.scratchpadNotes[0], "note");',
            'context.queryText = "newer text"; context.draftVersion = 2;',
            'vm.runInContext(`handleSave(JSON.stringify({ok:true}),"draft",1)`, context);',
            'assert.equal(context.draftSaveState, "pending");',
            'while (later.length) later.shift()();',
            'assert.equal(commands.at(-1)[1], "newer text");',
            'assert.equal(context.draftSaveProcess.saveVersion, 2);',
        ))
        run_node(script)

    def test_late_load_does_not_replace_an_edited_note(self):
        script = "\n".join((
            'const vm = require("node:vm"); const assert = require("node:assert/strict");',
            'const context = {scratchpadVersion: 1, scratchpadText: "new local text",',
            '  scratchpadNotes: ["new local text"], scratchpadNoteIndex: 0, restoringScratchpad: false};',
            'vm.createContext(context);', functions("handleScratchpad"),
            'vm.runInContext(`handleScratchpad(JSON.stringify({ok:true,notes:["old disk text"]}))`, context);',
            'assert.equal(context.scratchpadText, "new local text");',
            'assert.equal(context.scratchpadNotes[0], "new local text");',
        ))
        run_node(script)

    def test_quit_waits_for_latest_save_ack(self):
        script = "\n".join((
            'const vm = require("node:vm"); const assert = require("node:assert/strict");',
            'const later = []; let stopped = false;',
            'const context = { quitRequested: true, queryText: "unsaved", draftVersion: 1, savedDraftVersion: 0,',
            '  draftSaveState: "pending", draftSaveError: "", scratchpadNotes: ["saved"],',
            '  scratchpadVersion: 0, savedScratchpadVersion: 0, scratchpadSaveState: "saved",',
            '  scratchpadSaveError: "", draftSaveProcess: {running:false},',
            '  scratchpadSaveProcess: {running:false},',
            '  Qt: {callLater: fn => later.push(fn)},',
            '  startStdinCommand: proc => {proc.running = true},',
            '  finishQuit: () => {stopped = true} }; context.root = context;',
            'vm.createContext(context);',
            functions("characterCount", "flushPendingSaves", "saveDraft", "saveScratchpad", "handleSave", "saveProcessExited"),
            'vm.runInContext(`flushPendingSaves()`, context);',
            'assert.equal(stopped, false); assert.equal(context.draftSaveProcess.running, true);',
            'context.draftSaveProcess.ackReceived = true;',
            'vm.runInContext(`handleSave(JSON.stringify({ok:true}),"draft",1)`, context);',
            'while (later.length) later.shift()();',
            'assert.equal(stopped, false);',
            'context.draftSaveProcess.running = false;',
            'vm.runInContext(`saveProcessExited("draft",1)`, context);',
            'assert.equal(stopped, true);',
        ))
        run_node(script)

    def test_exit_retries_latest_version_after_early_ack(self):
        script = "\n".join((
            'const vm = require("node:vm"); const assert = require("node:assert/strict");',
            'const later = []; const sent = [];',
            'const context = {queryText:"newest", draftVersion:2, savedDraftVersion:0,',
            '  draftSaveState:"pending", draftSaveError:"", scratchpadNotes:[""],',
            '  scratchpadVersion:0, savedScratchpadVersion:0, scratchpadSaveState:"saved",',
            '  scratchpadSaveError:"", quitRequested:false,',
            '  draftSaveProcess:{running:true,saveVersion:1,ackReceived:true},',
            '  scratchpadSaveProcess:{running:false},',
            '  Qt:{callLater:fn=>later.push(fn)},',
            '  startStdinCommand:(proc,argv,body)=>{sent.push(body);proc.running=true}};',
            'context.root = context; vm.createContext(context);',
            functions("characterCount", "flushPendingSaves", "saveDraft", "saveScratchpad", "handleSave", "saveProcessExited"),
            'vm.runInContext(`handleSave(JSON.stringify({ok:true}),"draft",1)`, context);',
            'while (later.length) later.shift()();',
            'assert.equal(sent.length, 0);',
            'context.draftSaveProcess.running = false;',
            'vm.runInContext(`saveProcessExited("draft",1)`, context);',
            'assert.deepEqual(sent, ["newest"]);',
            'assert.equal(context.draftSaveProcess.saveVersion, 2);',
        ))
        run_node(script)


if __name__ == "__main__":
    unittest.main()
