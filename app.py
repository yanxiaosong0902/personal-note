"""Personal notes menu bar application for macOS."""
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import AppKit as A
from Foundation import NSDistributedNotificationCenter, NSObject
from objc import python_method, super

from hotkey import Hotkey
from launcher import OPEN_NOTIFICATION
from notes import Notes


class CenteredTextCell(A.NSTextFieldCell):
    def drawInteriorWithFrame_inView_(self, frame, view):
        height = min(frame.size.height, self.cellSize().height)
        offset = round((frame.size.height - height) / 2)
        centered = A.NSMakeRect(frame.origin.x, frame.origin.y + offset,
                                frame.size.width, height)
        super().drawInteriorWithFrame_inView_(centered, view)


class App(NSObject):
    def applicationDidFinishLaunching_(self, _notification):
        self.notes = Notes(self.storage_path)
        self.previous = None
        self.pending = None
        self.rows = []
        self.build_window()
        self.build_menu()
        self.monitor = A.NSEvent.addLocalMonitorForEventsMatchingMask_handler_(
            A.NSEventMaskKeyDown, self.handle_key
        )
        if "--opened-by-launcher" in sys.argv:
            self.hotkey = None
            NSDistributedNotificationCenter.defaultCenter().addObserver_selector_name_object_(
                self, "open:", OPEN_NOTIFICATION, None
            )
            self.open_(None)
            return
        try:
            self.hotkey = Hotkey(self.open_)
        except RuntimeError as error:
            self.hotkey = None
            self.alert(str(error))
        if "--smoke-test" in sys.argv:
            assert self.hotkey is not None
            self.open_(None)
            assert self.window.isVisible()
            first = self.notes.add("git status")
            second = self.notes.add("git status")
            self.notes.rename(first, "工作项目")
            self.refresh("")
            assert [note.id for note in self.rows] == [second, first]
            assert self.table.selectedRow() == 0
            self.window.displayIfNeeded()
            self.refresh("项目")
            assert [note.id for note in self.rows] == [first]
            self.notes.delete(first)
            self.refresh("项目")
            assert self.table.selectedRow() == -1
            self.hide()
            assert not self.window.isVisible()
            print("macOS window, hotkey registration and list smoke test passed", flush=True)
            A.NSApp.terminate_(None)

    @python_method
    def build_window(self):
        rect = A.NSMakeRect
        self.window = A.NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            rect(0, 0, 560, 372), A.NSWindowStyleMaskTitled | A.NSWindowStyleMaskClosable,
            A.NSBackingStoreBuffered, False,
        )
        self.window.setTitle_("个人便签")
        self.window.setReleasedWhenClosed_(False)
        self.window.setDelegate_(self)
        self.window.setCollectionBehavior_(
            A.NSWindowCollectionBehaviorMoveToActiveSpace
            | A.NSWindowCollectionBehaviorFullScreenAuxiliary
        )
        self.window.center()
        self.form_window = None
        content = self.window.contentView()

        self.field = A.NSTextField.alloc().initWithFrame_(rect(16, 327, 488, 28))
        self.field.setDelegate_(self)
        self.field.setEditable_(True)
        self.field.setBezeled_(True)
        self.field.setDrawsBackground_(True)
        self.field.cell().setUsesSingleLineMode_(True)
        # Use the native single-line height so AppKit aligns the placeholder
        # and the field editor on the same baseline.
        field_height = self.field.fittingSize().height
        self.field.setFrame_(rect(16, 327 + round((28 - field_height) / 2),
                                  488, field_height))
        content.addSubview_(self.field)
        self.add_button = A.NSButton.buttonWithTitle_target_action_("+", self, "newNote:")
        self.add_button.setFrame_(rect(512, 327, 32, 28))
        self.add_button.setToolTip_("新增便签")
        self.add_button.setAccessibilityLabel_("新增便签")
        content.addSubview_(self.add_button)

        scroll = A.NSScrollView.alloc().initWithFrame_(rect(16, 44, 528, 271))
        scroll.setHasVerticalScroller_(True)
        self.table = A.NSTableView.alloc().initWithFrame_(rect(0, 0, 528, 271))
        self.table.setHeaderView_(None)
        self.table.setRowHeight_(27)
        for key, width in (("body", 336), ("remark", 165)):
            column = A.NSTableColumn.alloc().initWithIdentifier_(key)
            column.setWidth_(width)
            cell = CenteredTextCell.alloc().initTextCell_("")
            cell.setEditable_(False)
            cell.setLineBreakMode_(A.NSLineBreakByTruncatingTail)
            column.setDataCell_(cell)
            self.table.addTableColumn_(column)
        self.table.setDataSource_(self)
        menu = A.NSMenu.alloc().init()
        self.menu_item(menu, "编辑便签…", "editNote:")
        self.menu_item(menu, "删除记录…", "deleteNote:")
        self.table.setMenu_(menu)
        scroll.setDocumentView_(self.table)
        content.addSubview_(scroll)

        self.hint = A.NSTextField.labelWithString_("")
        self.hint.setFrame_(rect(16, 13, 528, 20))
        self.hint.setTextColor_(A.NSColor.secondaryLabelColor())
        content.addSubview_(self.hint)

    def newNote_(self, _sender):
        self.show_note_form()

    @python_method
    def show_note_form(self, note=None):
        if self.pending is not None or self.form_window is not None:
            return

        rect = A.NSMakeRect
        dialog = A.NSAlert.alloc().init()
        dialog.setMessageText_("新增便签" if note is None else "编辑便签")
        save = dialog.addButtonWithTitle_("保存")
        save.setKeyEquivalent_("\r")
        cancel = dialog.addButtonWithTitle_("取消")
        cancel.setKeyEquivalent_("\x1b")

        form = A.NSView.alloc().initWithFrame_(rect(0, 0, 360, 180))
        label = A.NSTextField.labelWithString_("原文")
        label.setFrame_(rect(0, 158, 360, 18))
        form.addSubview_(label)

        scroll = A.NSScrollView.alloc().initWithFrame_(rect(0, 42, 360, 110))
        scroll.setBorderType_(A.NSBezelBorder)
        scroll.setHasVerticalScroller_(True)
        body = A.NSTextView.alloc().initWithFrame_(scroll.contentView().bounds())
        body.setRichText_(False)
        body.setAllowsUndo_(True)
        body.setAutomaticQuoteSubstitutionEnabled_(False)
        body.setAutomaticDashSubstitutionEnabled_(False)
        body.setAccessibilityLabel_("原文")
        scroll.setDocumentView_(body)
        form.addSubview_(scroll)

        remark = A.NSTextField.alloc().initWithFrame_(rect(0, 5, 360, 24))
        remark.setPlaceholderString_("备注（可选）")
        remark.setAccessibilityLabel_("备注")
        form.addSubview_(remark)
        if note is not None:
            body.setString_(note.body)
            remark.setStringValue_(note.remark)
        body.setNextKeyView_(remark)
        dialog.setAccessoryView_(form)
        dialog.window().setInitialFirstResponder_(body)
        dialog.window().setAnimationBehavior_(A.NSWindowAnimationBehaviorNone)
        dialog.setInformativeText_("请输入要保存的文字。")

        def complete(response):
            if response != A.NSAlertFirstButtonReturn:
                self.close_form()
                return
            original = str(body.string())
            if not original.strip():
                dialog.setInformativeText_("原文不能为空。")
                dialog.layout()
                return
            try:
                comment = str(remark.stringValue())
                if note is None:
                    self.notes.add(original, comment)
                else:
                    self.notes.update(note.id, original, comment)
            except Exception as error:
                dialog.setInformativeText_(f"保存失败：{error}")
                dialog.layout()
                return
            if note is None:
                self.field.setStringValue_("")
            self.refresh(self.field.stringValue())
            self.close_form()

        self.show_dialog(dialog, save, cancel, complete)

    @python_method
    def show_dialog(self, dialog, save, cancel, complete):
        dialog.layout()
        panel = dialog.window()
        panel.setAnimationBehavior_(A.NSWindowAnimationBehaviorNone)
        self.form_window = panel
        self.form_complete = complete
        for button, action in ((save, "saveForm:"), (cancel, "cancelForm:")):
            button.setTarget_(self)
            button.setAction_(action)
        self.window.addChildWindow_ordered_(panel, A.NSWindowAbove)
        parent = self.window.frame()
        size = panel.frame().size
        panel.setFrameOrigin_(A.NSMakePoint(
            A.NSMidX(parent) - size.width / 2,
            A.NSMidY(parent) - size.height / 2,
        ))
        panel.makeKeyAndOrderFront_(None)

    @python_method
    def close_form(self):
        panel = self.form_window
        self.window.removeChildWindow_(panel)
        panel.orderOut_(None)
        self.form_window = None
        self.form_complete = None
        self.window.makeKeyAndOrderFront_(None)
        self.window.makeFirstResponder_(self.field)

    def saveForm_(self, _sender):
        if self.form_window is not None:
            self.form_complete(A.NSAlertFirstButtonReturn)

    def cancelForm_(self, _sender):
        if self.form_window is not None:
            self.form_complete(A.NSAlertSecondButtonReturn)

    @python_method
    def menu_item(self, menu, title, action):
        item = menu.addItemWithTitle_action_keyEquivalent_(title, action, "")
        item.setTarget_(self)

    @python_method
    def build_menu(self):
        self.status = A.NSStatusBar.systemStatusBar().statusItemWithLength_(A.NSVariableStatusItemLength)
        self.status.button().setTitle_("便签")
        menu = A.NSMenu.alloc().init()
        self.menu_item(menu, "打开个人便签（⌘⇧Y）", "open:")
        self.menu_item(menu, "退出", "quit:")
        self.status.setMenu_(menu)

    def open_(self, _sender=None):
        if not self.window.isVisible():
            self.previous = A.NSWorkspace.sharedWorkspace().frontmostApplication()
            self.pending = None
            self.field.setStringValue_("")
            self.field.setPlaceholderString_("搜索原文或备注")
            self.refresh("")
        A.NSApp.activateIgnoringOtherApps_(True)
        sheet = self.form_window
        if sheet is not None:
            sheet.makeKeyAndOrderFront_(None)
            return
        self.window.makeKeyAndOrderFront_(None)
        self.window.makeFirstResponder_(self.field)

    @python_method
    def hide(self):
        self.window.orderOut_(None)
        self.pending = None
        self.add_button.setEnabled_(True)
        if self.previous and self.previous.processIdentifier() != A.NSRunningApplication.currentApplication().processIdentifier():
            self.previous.activateWithOptions_(A.NSApplicationActivateIgnoringOtherApps)
        self.previous = None

    def windowShouldClose_(self, _window):
        if self.form_window is None:
            self.hide()
        return False

    @python_method
    def refresh(self, query):
        self.rows = self.notes.search(query)
        self.table.reloadData()
        if not self.rows:
            self.table.deselectAll_(None)
        self.select(0)
        hint = "↑↓ 选择    ↩ 复制原文    Esc 关闭"
        if not query:
            hint = "⌘V 保存剪贴板    " + hint
        elif not self.rows:
            hint = "没有匹配的记录    Esc 关闭"
        self.hint.setStringValue_(hint)

    @python_method
    def select(self, index):
        if self.rows:
            self.table.selectRowIndexes_byExtendingSelection_(A.NSIndexSet.indexSetWithIndex_(index), False)
            self.table.scrollRowToVisible_(index)

    def numberOfRowsInTableView_(self, _table):
        return len(self.rows)

    def tableView_objectValueForTableColumn_row_(self, _table, column, row):
        note = self.rows[row]
        value = note.body if column.identifier() == "body" else note.remark
        return value.replace("\r\n", " ↵ ").replace("\n", " ↵ ").replace("\r", " ↵ ")

    def controlTextDidChange_(self, _notification):
        if self.pending is None:
            self.refresh(self.field.stringValue())

    @python_method
    def handle_key(self, event):
        sheet = self.form_window
        if sheet is not None:
            if event.window() == sheet:
                return self.handle_form_shortcut(event, sheet)
            if event.window() == self.window:
                return None
        if event.window() != self.window or not self.window.isKeyWindow():
            return event
        editor = self.field.currentEditor()
        if editor is not None and editor.hasMarkedText():
            return event
        modifiers = event.modifierFlags()
        command = modifiers & A.NSEventModifierFlagCommand
        other = modifiers & (A.NSEventModifierFlagShift | A.NSEventModifierFlagOption
                             | A.NSEventModifierFlagControl)
        if command and not other and event.charactersIgnoringModifiers().lower() == "v":
            if self.pending is None and not self.field.stringValue():
                self.capture()
                return None
            if editor is None:
                self.window.makeFirstResponder_(self.field)
                editor = self.field.currentEditor()
            if editor is not None:
                editor.paste_(None)
                return None
            return event
        if command or other:
            return event
        key = event.keyCode()
        if key == 53:
            self.hide()
        elif key in (36, 76):
            self.confirm()
        elif key in (125, 126) and self.pending is None and self.rows:
            current = self.table.selectedRow()
            target = 0 if current < 0 else current + (1 if key == 125 else -1)
            self.select(min(max(target, 0), len(self.rows) - 1))
        else:
            return event
        return None

    @python_method
    def handle_form_shortcut(self, event, sheet):
        modifiers = event.modifierFlags()
        if not modifiers & A.NSEventModifierFlagCommand:
            return event
        if modifiers & (A.NSEventModifierFlagOption | A.NSEventModifierFlagControl):
            return event
        editor = sheet.firstResponder()
        if not isinstance(editor, A.NSTextView) or editor.hasMarkedText():
            return event
        key = (event.charactersIgnoringModifiers() or "").lower()
        shifted = bool(modifiers & A.NSEventModifierFlagShift)
        if key == "z":
            manager = editor.undoManager()
            if manager is not None:
                if shifted and manager.canRedo():
                    manager.redo()
                elif not shifted and manager.canUndo():
                    manager.undo()
            return None
        actions = {"a": editor.selectAll_, "x": editor.cut_,
                   "c": editor.copy_, "v": editor.paste_}
        if not shifted and key in actions:
            actions[key](None)
            return None
        return event

    @python_method
    def capture(self):
        body = A.NSPasteboard.generalPasteboard().stringForType_(A.NSPasteboardTypeString)
        if not body:
            self.hint.setStringValue_("剪贴板里没有可保存的文本")
            return
        try:
            note_id = self.notes.add(body)
        except Exception as error:
            self.alert(f"保存失败：{error}")
            return
        self.refresh("")
        self.edit(note_id, "")

    @python_method
    def edit(self, note_id, remark):
        self.pending = note_id
        self.add_button.setEnabled_(False)
        self.field.setStringValue_(remark)
        self.field.setPlaceholderString_("输入备注（可选）")
        self.window.makeFirstResponder_(self.field)
        self.field.selectText_(None)
        self.hint.setStringValue_("↩ 保存备注并关闭    Esc 关闭")

    @python_method
    def confirm(self):
        if self.pending is not None:
            try:
                self.notes.rename(self.pending, self.field.stringValue())
            except Exception as error:
                self.alert(f"备注保存失败：{error}")
                return
            self.hide()
            return
        row = self.table.selectedRow()
        if 0 <= row < len(self.rows):
            pasteboard = A.NSPasteboard.generalPasteboard()
            pasteboard.clearContents()
            if pasteboard.setString_forType_(self.rows[row].body, A.NSPasteboardTypeString):
                self.hide()
            else:
                self.alert("无法写入剪贴板")

    @python_method
    def clicked_note(self):
        row = self.table.clickedRow()
        if row < 0:
            row = self.table.selectedRow()
        return self.rows[row] if self.pending is None and self.form_window is None and 0 <= row < len(self.rows) else None

    def editNote_(self, _sender):
        note = self.clicked_note()
        if note:
            self.show_note_form(note)

    def deleteNote_(self, _sender):
        note = self.clicked_note()
        if note is None:
            return

        dialog = A.NSAlert.alloc().init()
        dialog.setMessageText_("删除这条记录？")
        cancel = dialog.addButtonWithTitle_("取消")
        cancel.setKeyEquivalent_("\x1b")
        delete = dialog.addButtonWithTitle_("删除")
        delete.setKeyEquivalent_("")
        dialog.window().setDefaultButtonCell_(cancel.cell())

        def complete(response):
            if response == A.NSAlertFirstButtonReturn:
                try:
                    self.notes.delete(note.id)
                except Exception as error:
                    dialog.setInformativeText_(f"删除失败：{error}")
                    dialog.layout()
                    return
                self.refresh(self.field.stringValue())
            self.close_form()

        self.show_dialog(dialog, delete, cancel, complete)

    @python_method
    def alert(self, message):
        alert = A.NSAlert.alloc().init()
        alert.setMessageText_(message)
        alert.runModal()

    def quit_(self, _sender):
        A.NSApp.terminate_(None)

    def applicationWillTerminate_(self, _notification):
        if self.hotkey:
            self.hotkey.close()
        A.NSEvent.removeMonitor_(self.monitor)
        self.notes.close()


def main():
    app = A.NSApplication.sharedApplication()
    app.setActivationPolicy_(A.NSApplicationActivationPolicyAccessory)
    delegate = App.alloc().init()
    app.setDelegate_(delegate)
    if "--smoke-test" in sys.argv:
        with TemporaryDirectory() as directory:
            delegate.storage_path = Path(directory) / "notes.sqlite3"
            app.run()
        return
    delegate.storage_path = Path.home() / "Library/Application Support/PersonalNotes/notes.sqlite3"
    app.run()


if __name__ == "__main__":
    main()
