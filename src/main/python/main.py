import sys
from PySide6.QtWidgets import QApplication
from package.main_window import MainWindow
from package import __version__

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("Labroll Utility")
    app.setApplicationVersion(__version__)
    main_window = MainWindow()
    main_window.resize(1920 // 4, 1200 // 2)
    main_window.show()
    sys.exit(app.exec())
