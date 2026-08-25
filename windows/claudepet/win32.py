"""
Enlaces con Win32 por `ctypes`. Solo declaraciones: aquí no hay lógica.

Está aparte para que el resto de módulos se lean como código de la aplicación y
no como una traducción de la documentación de Microsoft, y para tener un único
sitio donde vigilar tres cosas que se rompen en silencio:

1. **Todas** las funciones llevan `argtypes` y `restype`. Sin `restype`, ctypes
   asume `int` y trunca los handles de 64 bits a 32: el fallo aparece más tarde,
   en otro sitio, y parece aleatorio.
2. Las estructuras van **sin `_pack_`**. El shell valida `cbSize` contra el
   tamaño con la alineación natural; empaquetadas salen unos bytes más cortas y
   `Shell_NotifyIconW` devuelve FALSE sin más explicación.
3. Los tipos que `ctypes.wintypes` no trae (`LRESULT`, `LONG_PTR`, `UINT_PTR`)
   se definen aquí una vez, en vez de improvisarlos en cada módulo.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
shell32 = ctypes.WinDLL("shell32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

# ─────────────────────────────────────────────────────────────
# Tipos que no están en ctypes.wintypes
# ─────────────────────────────────────────────────────────────
LRESULT = ctypes.c_ssize_t
LONG_PTR = ctypes.c_ssize_t
UINT_PTR = ctypes.c_size_t

WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT,
                             wintypes.WPARAM, wintypes.LPARAM)

# ─────────────────────────────────────────────────────────────
# Constantes
# ─────────────────────────────────────────────────────────────
# Ventanas
WS_POPUP = 0x80000000
WS_EX_TOOLWINDOW = 0x00000080          # fuera de la barra de tareas y del Alt+Tab
WS_EX_LAYERED = 0x00080000
WS_EX_TOPMOST = 0x00000008
WS_EX_NOACTIVATE = 0x08000000          # clicarla no le roba el foco al editor
SW_HIDE, SW_SHOWNOACTIVATE = 0, 4
HWND_TOPMOST = -1
HWND_BROADCAST = 0xFFFF
SWP_NOSIZE, SWP_NOMOVE, SWP_NOZORDER, SWP_NOACTIVATE = 0x1, 0x2, 0x4, 0x10
GWL_EXSTYLE = -20
CS_DBLCLKS = 0x0008
IDC_ARROW = 32512

# Mensajes
WM_DESTROY = 0x0002
WM_CLOSE = 0x0010
WM_QUERYENDSESSION = 0x0011
WM_ENDSESSION = 0x0016
WM_QUIT = 0x0012
WM_NULL = 0x0000
WM_TIMER = 0x0113
WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN, WM_LBUTTONUP = 0x0201, 0x0202
WM_RBUTTONDOWN, WM_RBUTTONUP = 0x0204, 0x0205
WM_MOUSEACTIVATE = 0x0021
WM_MOUSELEAVE, WM_MOUSEHOVER = 0x02A3, 0x02A1
WM_DPICHANGED = 0x02E0
WM_DISPLAYCHANGE = 0x007E
WM_CONTEXTMENU = 0x007B
WM_APP = 0x8000
WM_USER = 0x0400
MA_NOACTIVATE = 3

# Bandeja
NIM_ADD, NIM_MODIFY, NIM_DELETE, NIM_SETFOCUS, NIM_SETVERSION = 0, 1, 2, 3, 4
NIF_MESSAGE, NIF_ICON, NIF_TIP, NIF_STATE, NIF_INFO = 0x01, 0x02, 0x04, 0x08, 0x10
NIF_SHOWTIP = 0x80                     # con la versión 4, sin esto no sale el tooltip
NIIF_NONE, NIIF_INFO, NIIF_WARNING, NIIF_ERROR = 0x0, 0x1, 0x2, 0x3
NIIF_NOSOUND = 0x10
NIIF_RESPECT_QUIET_TIME = 0x80
NOTIFYICON_VERSION_4 = 4
# Avisos que llegan por el mensaje de la bandeja (con la versión 4).
NIN_SELECT = WM_USER + 0
NIN_KEYSELECT = WM_USER + 1
NIN_BALLOONSHOW = WM_USER + 2
NIN_BALLOONHIDE = WM_USER + 3
NIN_BALLOONTIMEOUT = WM_USER + 4
NIN_BALLOONUSERCLICK = WM_USER + 5

# Menús
MF_STRING, MF_GRAYED, MF_DISABLED, MF_CHECKED = 0x0000, 0x0001, 0x0002, 0x0008
MF_POPUP, MF_SEPARATOR = 0x0010, 0x0800
MF_BYCOMMAND, MF_BYPOSITION = 0x0000, 0x0400
TPM_LEFTALIGN, TPM_RIGHTALIGN = 0x0000, 0x0008
TPM_LEFTBUTTON, TPM_RIGHTBUTTON = 0x0000, 0x0002
TPM_RETURNCMD, TPM_NONOTIFY = 0x0100, 0x0080
TPM_BOTTOMALIGN = 0x0020

# Dibujo
BI_RGB = 0
DIB_RGB_COLORS = 0
ULW_ALPHA = 0x00000002
AC_SRC_OVER, AC_SRC_ALPHA = 0x00, 0x01
TRANSPARENT, OPAQUE = 1, 2
DT_SINGLELINE, DT_NOPREFIX, DT_CALCRECT = 0x20, 0x800, 0x400
DT_LEFT, DT_TOP = 0x0, 0x0
FW_NORMAL, FW_BOLD = 400, 700
DEFAULT_CHARSET = 1
OUT_TT_PRECIS = 4
CLIP_DEFAULT_PRECIS = 0
# ANTIALIASED_QUALITY y NO CLEARTYPE_QUALITY: ClearType da cobertura por
# subpíxel (una por canal), y leída como un único alfa produce flecos de color
# en el texto del badge.
ANTIALIASED_QUALITY = 4
DEFAULT_PITCH = 0
IMAGE_ICON = 1
LR_LOADFROMFILE, LR_DEFAULTSIZE = 0x0010, 0x0040

# Ratón, monitores, DPI
TME_LEAVE, TME_HOVER = 0x00000002, 0x00000001
HOVER_DEFAULT = 0xFFFFFFFF
MONITOR_DEFAULTTONULL, MONITOR_DEFAULTTONEAREST = 0x0, 0x2
SM_CXSMICON, SM_CYSMICON = 49, 50
DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = ctypes.c_void_p(-4)

# Diálogos y errores
MB_OK, MB_ICONINFORMATION, MB_ICONWARNING = 0x0, 0x40, 0x30
MB_SETFOREGROUND, MB_TOPMOST = 0x00010000, 0x00040000
ERROR_ALREADY_EXISTS = 183
ERROR_CLASS_ALREADY_EXISTS = 1410


# ─────────────────────────────────────────────────────────────
# Estructuras
# ─────────────────────────────────────────────────────────────
class GUID(ctypes.Structure):
    _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
                ("Data3", wintypes.WORD), ("Data4", wintypes.BYTE * 8)]


class NOTIFYICONDATAW(ctypes.Structure):
    """El icono de la bandeja.

    Sin `_pack_`: ver la nota 2 de la cabecera del módulo. El `assert` de abajo
    es el canario — si algún día cambia el tamaño esperado, mejor que reviente
    al importar que que `Shell_NotifyIconW` devuelva FALSE sin decir nada.

    Los campos de texto son de tamaño fijo y ctypes NO recorta: pasarle una
    cadena más larga lanza `ValueError`. Recortar es cosa de quien llama
    (`szTip` admite 127 caracteres útiles, `szInfo` 255 y `szInfoTitle` 63).
    """
    _fields_ = [("cbSize", wintypes.DWORD),
                ("hWnd", wintypes.HWND),
                ("uID", wintypes.UINT),
                ("uFlags", wintypes.UINT),
                ("uCallbackMessage", wintypes.UINT),
                ("hIcon", wintypes.HICON),
                ("szTip", wintypes.WCHAR * 128),
                ("dwState", wintypes.DWORD),
                ("dwStateMask", wintypes.DWORD),
                ("szInfo", wintypes.WCHAR * 256),
                ("uVersion", wintypes.UINT),        # unión con uTimeout
                ("szInfoTitle", wintypes.WCHAR * 64),
                ("dwInfoFlags", wintypes.DWORD),
                ("guidItem", GUID),
                ("hBalloonIcon", wintypes.HICON)]


assert ctypes.sizeof(NOTIFYICONDATAW) in (956, 976), ctypes.sizeof(NOTIFYICONDATAW)


class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT),
                ("style", wintypes.UINT),
                ("lpfnWndProc", WNDPROC),
                ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int),
                ("hInstance", wintypes.HINSTANCE),
                ("hIcon", wintypes.HICON),
                ("hCursor", wintypes.HANDLE),
                ("hbrBackground", wintypes.HBRUSH),
                ("lpszMenuName", wintypes.LPCWSTR),
                ("lpszClassName", wintypes.LPCWSTR),
                ("hIconSm", wintypes.HICON)]


class BLENDFUNCTION(ctypes.Structure):
    """Cuatro BYTE, no cuatro DWORD. Es un error clásico y da halos raros."""
    _fields_ = [("BlendOp", wintypes.BYTE), ("BlendFlags", wintypes.BYTE),
                ("SourceConstantAlpha", wintypes.BYTE), ("AlphaFormat", wintypes.BYTE)]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG),
                ("biHeight", wintypes.LONG), ("biPlanes", wintypes.WORD),
                ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD),
                ("biXPelsPerMeter", wintypes.LONG), ("biYPelsPerMeter", wintypes.LONG),
                ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 3)]


class ICONINFO(ctypes.Structure):
    _fields_ = [("fIcon", wintypes.BOOL),        # BOOL (4 bytes), no BYTE
                ("xHotspot", wintypes.DWORD), ("yHotspot", wintypes.DWORD),
                ("hbmMask", wintypes.HBITMAP), ("hbmColor", wintypes.HBITMAP)]


class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]


class TRACKMOUSEEVENT(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                ("hwndTrack", wintypes.HWND), ("dwHoverTime", wintypes.DWORD)]


def dib_header(width: int, height: int) -> BITMAPINFO:
    """Cabecera de un DIB de 32 bits **de arriba abajo**.

    `biHeight` negativo no es un detalle: con el signo positivo Windows entiende
    la clásica orientación de abajo arriba y todo sale del revés.
    """
    info = BITMAPINFO()
    info.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    info.bmiHeader.biWidth = width
    info.bmiHeader.biHeight = -height
    info.bmiHeader.biPlanes = 1
    info.bmiHeader.biBitCount = 32
    info.bmiHeader.biCompression = BI_RGB
    return info


# Alfa por píxel, con el búfer ya premultiplicado.
BLEND_ALPHA = BLENDFUNCTION(AC_SRC_OVER, 0, 255, AC_SRC_ALPHA)


# ─────────────────────────────────────────────────────────────
# Prototipos
# ─────────────────────────────────────────────────────────────
def _p(dll, name, restype, *argtypes):
    fn = getattr(dll, name)
    fn.restype = restype
    fn.argtypes = list(argtypes)
    return fn


HWND, UINT, DWORD, BOOL, INT = (wintypes.HWND, wintypes.UINT, wintypes.DWORD,
                                wintypes.BOOL, ctypes.c_int)
LPCWSTR, LPVOID, HANDLE = wintypes.LPCWSTR, wintypes.LPVOID, wintypes.HANDLE

RegisterClassExW = _p(user32, "RegisterClassExW", wintypes.ATOM,
                      ctypes.POINTER(WNDCLASSEXW))
UnregisterClassW = _p(user32, "UnregisterClassW", BOOL, LPCWSTR, wintypes.HINSTANCE)
CreateWindowExW = _p(user32, "CreateWindowExW", HWND, DWORD, LPCWSTR, LPCWSTR, DWORD,
                     INT, INT, INT, INT, HWND, wintypes.HMENU,
                     wintypes.HINSTANCE, LPVOID)
DestroyWindow = _p(user32, "DestroyWindow", BOOL, HWND)
DefWindowProcW = _p(user32, "DefWindowProcW", LRESULT, HWND, UINT,
                    wintypes.WPARAM, wintypes.LPARAM)
GetMessageW = _p(user32, "GetMessageW", INT, ctypes.POINTER(wintypes.MSG),
                 HWND, UINT, UINT)
TranslateMessage = _p(user32, "TranslateMessage", BOOL, ctypes.POINTER(wintypes.MSG))
DispatchMessageW = _p(user32, "DispatchMessageW", LRESULT, ctypes.POINTER(wintypes.MSG))
PostQuitMessage = _p(user32, "PostQuitMessage", None, INT)
PostMessageW = _p(user32, "PostMessageW", BOOL, HWND, UINT,
                  wintypes.WPARAM, wintypes.LPARAM)
RegisterWindowMessageW = _p(user32, "RegisterWindowMessageW", UINT, LPCWSTR)
SetTimer = _p(user32, "SetTimer", UINT_PTR, HWND, UINT_PTR, UINT, LPVOID)
KillTimer = _p(user32, "KillTimer", BOOL, HWND, UINT_PTR)
LoadCursorW = _p(user32, "LoadCursorW", HANDLE, wintypes.HINSTANCE, LPCWSTR)
SetForegroundWindow = _p(user32, "SetForegroundWindow", BOOL, HWND)
MessageBoxW = _p(user32, "MessageBoxW", INT, HWND, LPCWSTR, LPCWSTR, UINT)

CreatePopupMenu = _p(user32, "CreatePopupMenu", wintypes.HMENU)
AppendMenuW = _p(user32, "AppendMenuW", BOOL, wintypes.HMENU, UINT, UINT_PTR, LPCWSTR)
DestroyMenu = _p(user32, "DestroyMenu", BOOL, wintypes.HMENU)
TrackPopupMenu = _p(user32, "TrackPopupMenu", INT, wintypes.HMENU, UINT,
                    INT, INT, INT, HWND, LPVOID)
CheckMenuRadioItem = _p(user32, "CheckMenuRadioItem", BOOL, wintypes.HMENU,
                        UINT, UINT, UINT, UINT)

GetCursorPos = _p(user32, "GetCursorPos", BOOL, ctypes.POINTER(wintypes.POINT))
MonitorFromPoint = _p(user32, "MonitorFromPoint", HANDLE, wintypes.POINT, DWORD)
MonitorFromWindow = _p(user32, "MonitorFromWindow", HANDLE, HWND, DWORD)
GetMonitorInfoW = _p(user32, "GetMonitorInfoW", BOOL, HANDLE,
                     ctypes.POINTER(MONITORINFO))
SetWindowPos = _p(user32, "SetWindowPos", BOOL, HWND, HWND, INT, INT, INT, INT, UINT)
GetWindowRect = _p(user32, "GetWindowRect", BOOL, HWND, ctypes.POINTER(wintypes.RECT))
ShowWindow = _p(user32, "ShowWindow", BOOL, HWND, INT)
GetDC = _p(user32, "GetDC", wintypes.HDC, HWND)
ReleaseDC = _p(user32, "ReleaseDC", INT, HWND, wintypes.HDC)
UpdateLayeredWindow = _p(user32, "UpdateLayeredWindow", BOOL, HWND, wintypes.HDC,
                         ctypes.POINTER(wintypes.POINT), ctypes.POINTER(wintypes.SIZE),
                         wintypes.HDC, ctypes.POINTER(wintypes.POINT), DWORD,
                         ctypes.POINTER(BLENDFUNCTION), DWORD)
SetCapture = _p(user32, "SetCapture", HWND, HWND)
ReleaseCapture = _p(user32, "ReleaseCapture", BOOL)
TrackMouseEvent = _p(user32, "TrackMouseEvent", BOOL, ctypes.POINTER(TRACKMOUSEEVENT))
GetSystemMetrics = _p(user32, "GetSystemMetrics", INT, INT)
DestroyIcon = _p(user32, "DestroyIcon", BOOL, wintypes.HICON)
LoadImageW = _p(user32, "LoadImageW", HANDLE, wintypes.HINSTANCE, LPCWSTR,
                UINT, INT, INT, UINT)
DrawTextW = _p(user32, "DrawTextW", INT, wintypes.HDC, LPCWSTR, INT,
               ctypes.POINTER(wintypes.RECT), UINT)
CreateIconIndirect = _p(user32, "CreateIconIndirect", wintypes.HICON,
                        ctypes.POINTER(ICONINFO))

CreateCompatibleDC = _p(gdi32, "CreateCompatibleDC", wintypes.HDC, wintypes.HDC)
DeleteDC = _p(gdi32, "DeleteDC", BOOL, wintypes.HDC)
CreateDIBSection = _p(gdi32, "CreateDIBSection", wintypes.HBITMAP, wintypes.HDC,
                      ctypes.POINTER(BITMAPINFO), UINT,
                      ctypes.POINTER(LPVOID), HANDLE, DWORD)
CreateBitmap = _p(gdi32, "CreateBitmap", wintypes.HBITMAP, INT, INT, UINT, UINT, LPVOID)
SelectObject = _p(gdi32, "SelectObject", HANDLE, wintypes.HDC, HANDLE)
DeleteObject = _p(gdi32, "DeleteObject", BOOL, HANDLE)
# 14 argumentos: alto, ancho, escape, orientación, grosor, cursiva, subrayado,
# tachado, juego de caracteres, precisión de contorno, de recorte, calidad,
# paso y familia, y por último el nombre de la fuente.
CreateFontW = _p(gdi32, "CreateFontW", HANDLE, INT, INT, INT, INT, INT,
                 DWORD, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD, LPCWSTR)
SetBkColor = _p(gdi32, "SetBkColor", DWORD, wintypes.HDC, DWORD)
SetTextColor = _p(gdi32, "SetTextColor", DWORD, wintypes.HDC, DWORD)
SetBkMode = _p(gdi32, "SetBkMode", INT, wintypes.HDC, INT)

Shell_NotifyIconW = _p(shell32, "Shell_NotifyIconW", BOOL, DWORD,
                       ctypes.POINTER(NOTIFYICONDATAW))

GetModuleHandleW = _p(kernel32, "GetModuleHandleW", wintypes.HMODULE, LPCWSTR)
CreateMutexW = _p(kernel32, "CreateMutexW", HANDLE, LPVOID, BOOL, LPCWSTR)
CloseHandle = _p(kernel32, "CloseHandle", BOOL, HANDLE)
ReplaceFileW = _p(kernel32, "ReplaceFileW", BOOL, LPCWSTR, LPCWSTR, LPCWSTR,
                  DWORD, LPVOID, LPVOID)

# Estas dos no existen antes de Windows 10 (1607 y 1703): se piden con cuidado y,
# si faltan, quien llama se queda con el camino de respaldo.
try:
    GetDpiForWindow = _p(user32, "GetDpiForWindow", UINT, HWND)
except AttributeError:                                        # pragma: no cover
    GetDpiForWindow = None
try:
    GetSystemMetricsForDpi = _p(user32, "GetSystemMetricsForDpi", INT, INT, UINT)
except AttributeError:                                        # pragma: no cover
    GetSystemMetricsForDpi = None

if ctypes.sizeof(ctypes.c_void_p) == 8:
    GetWindowLongPtrW = _p(user32, "GetWindowLongPtrW", LONG_PTR, HWND, INT)
    SetWindowLongPtrW = _p(user32, "SetWindowLongPtrW", LONG_PTR, HWND, INT, LONG_PTR)
else:                                                         # pragma: no cover
    # En 32 bits las variantes ...Ptr no existen: son las de siempre.
    GetWindowLongPtrW = _p(user32, "GetWindowLongW", LONG_PTR, HWND, INT)
    SetWindowLongPtrW = _p(user32, "SetWindowLongW", LONG_PTR, HWND, INT, LONG_PTR)


# ─────────────────────────────────────────────────────────────
# Ayudas
# ─────────────────────────────────────────────────────────────
def loword(value: int) -> int:
    return value & 0xFFFF


def hiword(value: int) -> int:
    return (value >> 16) & 0xFFFF


def get_x(lparam: int) -> int:
    """Coordenada X de un LPARAM de ratón, **con extensión de signo**.

    Un monitor colocado a la izquierda del principal tiene coordenadas de
    pantalla negativas. Sacadas sin signo, el menú aparecería en x = 65000.
    """
    return ctypes.c_short(loword(lparam)).value


def get_y(lparam: int) -> int:
    return ctypes.c_short(hiword(lparam)).value


def set_dpi_aware() -> None:
    """Consciente del DPI por monitor, **antes de crear ninguna ventana**.

    Con la cadena de respaldo entera: el contexto por monitor v2 es de Windows 10
    1703, `SetProcessDpiAwareness` de 8.1 y `SetProcessDPIAware` de Vista. Sin
    esto, en un monitor al 150 % Windows escala la ventana a lo bruto y la
    mascota sale borrosa.
    """
    try:
        fn = user32.SetProcessDpiAwarenessContext
        fn.restype = wintypes.BOOL
        fn.argtypes = [ctypes.c_void_p]
        if fn(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2):
            return
    except (AttributeError, OSError):
        pass
    try:
        shcore = ctypes.WinDLL("shcore", use_last_error=True)
        if shcore.SetProcessDpiAwareness(2) == 0:      # PROCESS_PER_MONITOR_DPI_AWARE
            return
    except (AttributeError, OSError):
        pass
    try:
        user32.SetProcessDPIAware()
    except (AttributeError, OSError):
        pass


def dpi_for(hwnd: int) -> int:
    if GetDpiForWindow is not None and hwnd:
        got = GetDpiForWindow(hwnd)
        if got:
            return int(got)
    return 96


def small_icon_size(hwnd: int = 0) -> int:
    """Cuánto mide el icono de la bandeja aquí: 16 px al 100 %, 24 al 150 %."""
    dpi = dpi_for(hwnd)
    if GetSystemMetricsForDpi is not None:
        got = GetSystemMetricsForDpi(SM_CXSMICON, dpi)
        if got:
            return int(got)
    return int(GetSystemMetrics(SM_CXSMICON)) or 16


def set_app_id(app_id: str) -> None:
    """Agrupa la app bajo su propio nombre en la barra de tareas y mejora a quién
    se le atribuye la notificación. Falla sin ruido en Windows viejos."""
    try:
        shell32.SetCurrentProcessExplicitAppUserModelID(ctypes.c_wchar_p(app_id))
    except (AttributeError, OSError):
        pass
