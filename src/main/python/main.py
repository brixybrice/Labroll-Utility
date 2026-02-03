from fbs_runtime.application_context.PySide6 import ApplicationContext, cached_property
from package.main_window import MainWindow
from PySide6 import QtGui
from tkinter import Tcl
import os
import sys


#os.environ['QT_MAC_WANTS_LAYER'] = '1'


class AppContext(ApplicationContext):
    def run(self):
        main_window = MainWindow(ctx=self)
        self.window = main_window  # assign to self (ctx), not appctxt
        main_window.resize(1920/4, 1200/2)
        main_window.show()
        return self.app.exec()

    @cached_property   # pour placer les images dans le cache
    def img_checked(self):
        return QtGui.QIcon(self.get_resource("images/checked.png"))

    @cached_property  # pour placer les images dans le cache
    def img_unchecked(self):
        return QtGui.QIcon(self.get_resource("images/unchecked.png"))

    @cached_property  # pour placer les images dans le cache
    def img_logo(self):
        return QtGui.QPixmap(self.get_resource("images/mono-white_b.png"))

    @cached_property  # pour placer les images dans le cache
    def img_error(self):
        return QtGui.QPixmap(self.get_resource("images/error.png"))

if __name__ == '__main__':
    appctxt = AppContext()
    sys.exit(appctxt.run())
