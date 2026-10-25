"""TRCC display bridge for the legacy 9.4 and current command-based APIs."""
from __future__ import annotations

import atexit
import importlib
from importlib.metadata import PackageNotFoundError, version
import os
import tempfile
from pathlib import Path

if __package__:
    from .display_preferences import DisplayRotation
else:
    from display_preferences import DisplayRotation


def _jpeg_settings() -> tuple[int, int]:
    try:
        quality = int(os.environ.get("OPEN_TROFEO_JPEG_QUALITY", "80"))
    except ValueError:
        quality = 80
    try:
        maximum = int(os.environ.get("OPEN_TROFEO_JPEG_MAX_BYTES", "350000"))
    except ValueError:
        maximum = 350000
    return quality if 5 <= quality <= 100 else 95, maximum if maximum > 0 else 650000


def load_api() -> tuple[str, dict]:
    """Import the API without scanning, connecting to USB, or starting a daemon."""
    try:
        cli = importlib.import_module("trcc.cli")
    except ModuleNotFoundError as exc:
        if exc.name != "trcc.cli":
            raise
        boot = importlib.import_module("trcc._boot")
        commands = importlib.import_module("trcc.core.commands")
        qt = importlib.import_module("trcc.adapters.render.qt")
        protocol = importlib.import_module("trcc.core.protocol")
        return "commands", dict(boot=boot, commands=commands, qt=qt, protocol=protocol)
    return "legacy", dict(
        cli=cli,
        connect=importlib.import_module("trcc.cli._connect").connect_device,
        app=importlib.import_module("trcc.core.app").TrccApp,
        logging=importlib.import_module("trcc.adapters.infra.diagnostics").StandardLoggingConfigurator,
        images=importlib.import_module("trcc.services").ImageService,
    )


def _rotate_image(renderer, image, degrees):
    """TRCC 9.4 calls this apply_rotation; 9.11 calls it rotate."""
    rotation = getattr(renderer, "apply_rotation", None) or getattr(renderer, "rotate", None)
    if not callable(rotation):
        raise RuntimeError(f"{type(renderer).__name__} does not support image rotation")
    return rotation(image, degrees)


class _Renderer:
    """Names used by Open Trofeo's compositing loops, backed by current Qt."""
    def __init__(self, renderer):
        self.renderer = renderer

    def open_image(self, path):
        return self.renderer.open_image(Path(path))

    def copy_surface(self, image):
        return image.copy()

    def convert_to_rgb(self, image):
        return image.convertToFormat(type(image).Format.Format_RGB888)

    def convert_to_rgba(self, image):
        return image.convertToFormat(type(image).Format.Format_RGBA8888)

    def composite(self, base, overlay, position):
        return self.renderer.composite(base, overlay, position)

    def rotate(self, image, degrees):
        return _rotate_image(self.renderer, image, degrees)


class _CommandDisplay:
    def __init__(self, app, commands, key, renderer, wire_rotation=0):
        self.app, self.commands, self.key, self.renderer = app, commands, key, renderer
        # Theme frames already carry Open Trofeo's canvas rotation. Undo the
        # rotation SendImage will add so the USB frame matches legacy output.
        self.input_rotation = (-int(wire_rotation)) % 360
        self.directory = tempfile.TemporaryDirectory(prefix="open-trofeo-trcc-frame-")
        self.frame_path = Path(self.directory.name) / "frame.png"
        atexit.register(self.directory.cleanup)

    def load_image(self, path):
        try:
            return {"success": True, "image": self.renderer.open_image(path)}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def enable_overlay(self, enabled):
        # Open Trofeo has already composed the full frame. SendImage takes
        # ownership of that frame and suppresses TRCC's separate theme overlay.
        if enabled:
            raise ValueError("TRCC overlays are composed by Open Trofeo")

    def set_background(self, image):
        pass  # Background lifetime is owned by the worker's compositing loop.

    def send_frame(self, image):
        if self.input_rotation:
            image = self.renderer.rotate(image, self.input_rotation)
        if not image.save(str(self.frame_path), "PNG"):
            raise RuntimeError("Failed to stage TRCC frame")
        # Use the supported command, preserving device profile, orientation,
        # brightness and synchronous USB acknowledgement. Do not start TRCC's
        # independent daemon or persist a temporary image as a TRCC theme.
        result = self.app.dispatch(self.commands.SendImage(key=self.key, path=self.frame_path))
        if not result.ok:
            raise RuntimeError(f"TRCC frame transfer failed: {result.message}")
        return True

    def send(self, image):
        return self.send_frame(image)


class _RotatedDisplay:
    """Apply the user's physical LCD setting after all theme compositing."""
    def __init__(self, display, renderer, rotation=None):
        self.display, self.renderer = display, renderer
        self.rotation = rotation or DisplayRotation()
        self._last_frame = None

    def __getattr__(self, name):
        return getattr(self.display, name)

    def _image(self, image):
        frame = _rotate_image(self.renderer, image, 180) if self.rotation.value == 180 else image
        # Legacy TRCC caches JPEGs by id(image), without retaining the image.
        # Keep the previous surface alive until its replacement is allocated,
        # so a fresh frame cannot reuse the old id and send a stale JPEG.
        self._last_frame = frame
        return frame

    def send(self, image):
        return self.display.send(self._image(image))

    def send_frame(self, image):
        return self.display.send_frame(self._image(image))


def open_display(device=None):
    api, modules = load_api()
    try:
        installed = version("trcc-linux")
    except PackageNotFoundError:
        installed = "unknown version"
    print(f"TRCC display API: {api} ({installed})", flush=True)
    quality, maximum = _jpeg_settings()
    if api == "legacy":
        try:
            setup = importlib.import_module("trcc.adapters.system.linux.setup").LinuxSetup
            setup.needs_setup = lambda self: False
            setup.auto_setup = lambda self: None
        except ImportError:
            pass
        modules["logging"]().configure(verbosity=0)
        app = modules["app"].init()
        app.init_platform(verbosity=0, renderer_factory=modules["cli"]._make_cli_renderer)
        images = modules["images"]
        images.to_jpeg = staticmethod(lambda image, quality=quality, max_size=maximum: images._r().encode_jpeg(image, quality, max_size))
        if modules["connect"](device) != 0:
            raise RuntimeError("TRCC could not connect to the LCD")
        lcd = modules["app"].get().device(0)
        if lcd is None:
            raise RuntimeError("TRCC found no LCD device")
        return _RotatedDisplay(lcd, images._r()), images._r()

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    renderer = modules["qt"].QtRenderer()
    encode_jpeg = renderer.encode_jpeg
    renderer.encode_jpeg = lambda image, quality=quality, max_size=maximum: encode_jpeg(image, quality, max_size)
    app = modules["boot"]._build_local_app(renderer=renderer)
    atexit.register(app.close)
    commands = modules["commands"]
    scan = app.dispatch(commands.DiscoverDevices())
    if not scan.ok:
        raise RuntimeError(f"TRCC discovery failed: {scan.message}")
    candidates = [d for d in scan.devices if (d.vid, d.pid) == (0x0416, 0x5408)]
    if device is not None:
        candidates = [d for d in candidates if d.key == device]
    if len(candidates) != 1:
        raise RuntimeError("TRCC requires one Trofeo LCD (0416:5408); specify its device key if several are connected")
    key = candidates[0].key
    connected = app.dispatch(commands.ConnectDevice(key=key))
    if not connected.ok:
        raise RuntimeError(f"TRCC connection failed: {connected.message}")
    profile = app.devices[key].profile
    if profile is None:
        raise RuntimeError("TRCC connection did not provide an LCD profile")
    orientation = app.settings.for_device(key).orientation
    wire_rotation = modules["protocol"].wire_angle(profile, orientation, False)
    print(
        f"TRCC frame rotation: orientation={orientation} wire={wire_rotation} "
        f"compensation={(-wire_rotation) % 360} (canvas rotation already rendered)",
        flush=True,
    )
    facade = _Renderer(renderer)
    return _RotatedDisplay(_CommandDisplay(app, commands, key, facade, wire_rotation), facade), facade
