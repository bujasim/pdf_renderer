import sys
import os
from pathlib import Path

from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine


def main():
    import PySide6
    pyside_dir = Path(PySide6.__path__[0])

    if hasattr(os, "add_dll_directory"):
        os.add_dll_directory(str(pyside_dir))
        plugins_dir = pyside_dir / "plugins"
        if plugins_dir.exists():
            os.environ["QT_PLUGIN_PATH"] = str(plugins_dir)

    app = QGuiApplication(sys.argv)
    engine = QQmlApplicationEngine()

    qml_path = pyside_dir / "qml"
    if qml_path.exists():
        engine.addImportPath(str(qml_path))

    qml_file = Path(__file__).parent / "main.qml"
    engine.load(qml_file)

    if not engine.rootObjects():
        sys.exit(-1)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
