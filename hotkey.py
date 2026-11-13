"""Register a system hotkey without monitoring other keyboard input."""
import ctypes as c

carbon = c.CDLL("/System/Library/Frameworks/Carbon.framework/Carbon")


class EventType(c.Structure):
    _fields_ = [("event_class", c.c_uint32), ("kind", c.c_uint32)]


class HotKeyID(c.Structure):
    _fields_ = [("signature", c.c_uint32), ("id", c.c_uint32)]


Handler = c.CFUNCTYPE(c.c_int32, c.c_void_p, c.c_void_p, c.c_void_p)
carbon.GetApplicationEventTarget.restype = c.c_void_p
carbon.InstallEventHandler.argtypes = [
    c.c_void_p, Handler, c.c_uint32, c.POINTER(EventType), c.c_void_p,
    c.POINTER(c.c_void_p),
]
carbon.RegisterEventHotKey.argtypes = [
    c.c_uint32, c.c_uint32, HotKeyID, c.c_void_p, c.c_uint32,
    c.POINTER(c.c_void_p),
]
carbon.RemoveEventHandler.argtypes = [c.c_void_p]
carbon.UnregisterEventHotKey.argtypes = [c.c_void_p]


class Hotkey:
    def __init__(self, action):
        def handle(_next, _event, _context):
            try:
                action()
            except Exception:
                import traceback
                traceback.print_exc()
            return 0

        self.callback = Handler(handle)
        self.handler = c.c_void_p()
        self.key = c.c_void_p()
        target = carbon.GetApplicationEventTarget()
        event = EventType(int.from_bytes(b"keyb", "big"), 6)
        status = carbon.InstallEventHandler(
            target, self.callback, 1, c.byref(event), None, c.byref(self.handler)
        )
        if status:
            raise RuntimeError(f"无法安装快捷键处理器（{status}）")
        # ANSI Y, Command + Shift.
        status = carbon.RegisterEventHotKey(
            16, (1 << 8) | (1 << 9), HotKeyID(int.from_bytes(b"note", "big"), 1),
            target, 0, c.byref(self.key)
        )
        if status:
            self.close()
            raise RuntimeError(f"无法注册 ⌘⇧Y（{status}），可能已被其他应用占用。")

    def close(self):
        if self.key:
            carbon.UnregisterEventHotKey(self.key)
            self.key = c.c_void_p()
        if self.handler:
            carbon.RemoveEventHandler(self.handler)
            self.handler = c.c_void_p()
