"""Listen for the global shortcut and open the notes app on demand."""
import subprocess
import sys
from pathlib import Path

import AppKit as A
from Foundation import NSDistributedNotificationCenter, NSObject

from hotkey import Hotkey
from objc import python_method

OPEN_NOTIFICATION = "local.personalnotes.open"


class Launcher(NSObject):
    def applicationDidFinishLaunching_(self, notification):
        self.child = None
        self.hotkey = Hotkey(self.open_notes)

    @python_method
    def open_notes(self):
        if self.child is None or self.child.poll() is not None:
            self.child = subprocess.Popen([
                sys.executable, str(Path(__file__).with_name("app.py")), "--opened-by-launcher"
            ])
        else:
            NSDistributedNotificationCenter.defaultCenter().postNotificationName_object_userInfo_deliverImmediately_(
                OPEN_NOTIFICATION, None, None, True
            )


if __name__ == "__main__":
    app = A.NSApplication.sharedApplication()
    app.setActivationPolicy_(A.NSApplicationActivationPolicyProhibited)
    delegate = Launcher.alloc().init()
    app.setDelegate_(delegate)
    app.run()
