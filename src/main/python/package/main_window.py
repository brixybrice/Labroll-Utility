from PySide6 import QtWidgets, QtCore, QtGui
import os
import shutil
from collections import deque
import xxhash
import datetime
import subprocess
from hachoir.parser import createParser
from hachoir.metadata import extractMetadata
import re

def get_video_datetime(path):
    # Lecture metadata via hachoir
    parser = createParser(path)
    creation_date = datetime.datetime.max

    if parser:
        try:
            metadata = extractMetadata(parser)
            if metadata and metadata.has("creation_date"):
                creation_date = metadata.get("creation_date").value
        except Exception:
            pass
        finally:
            parser.close()

    # Chapter GoPro (GX01, GX02, etc.)
    name = os.path.basename(path)
    m = re.match(r"G[HSPX](\d{2})(\d{4})", name)
    if m:
        chapter = int(m.group(1))
        clip_id = int(m.group(2))
    else:
        chapter = 0
        clip_id = 0

    print(f"[HACHOIR] {path} | creation_date={creation_date} | clip_id={clip_id} | chapter={chapter}")

    # Fallback sécurisé si pas de date lisible
    safe_date = creation_date if creation_date else datetime.datetime(1970, 1, 1)

    return (safe_date, clip_id, chapter)

from package.utils.params import resource_path, load_params, ensure_params_file, save_params, show


MAX_CONCURRENT_THREADS = 5

class CopyRenameWorker(QtCore.QObject):
    finished = QtCore.Signal(str, bool, str)
    # Correction Overflow Qt: utiliser object pour supporter >2Go
    progress = QtCore.Signal(object, object)  # bytes_chunk, total_file_size

    def __init__(self, file_path, labroll, destination, camid="", labroll_index=None, original_name=None):
        super().__init__()
        self.file_path = file_path
        self.labroll = labroll
        self.destination = destination
        self.camid = camid
        self.labroll_index = labroll_index
        self.original_name = original_name
        self._is_interrupted = False

    def interrupt(self):
        self._is_interrupted = True

    def run(self):
        print(f"Lancement worker pour : {self.file_path}")
        if self._is_interrupted:
            self.finished.emit(self.file_path, False, "")
            return
        try:
            index = self.labroll_index if self.labroll_index is not None else 1
            ext = os.path.splitext(self.file_path)[1]
            date_suffix = datetime.datetime.now().strftime("%Y%m%d")
            if self.camid:
                new_name = f"{self.labroll}C{index:03d}_{date_suffix}_{self.camid}{ext}"
            else:
                new_name = f"{self.labroll}C{index:03d}_{date_suffix}{ext}"

            if getattr(self, "rename_only", False):
                new_path = os.path.join(os.path.dirname(self.file_path), new_name)
                try:
                    os.rename(self.file_path, new_path)
                    QtCore.QThread.msleep(50)
                    self.finished.emit(self.file_path, True, "")
                except Exception as e:
                    print(f"Erreur lors du renommage : {e}")
                    self.finished.emit(self.file_path, False, "")
                return
            else:
                new_path = os.path.join(self.destination, new_name)
                buffer_size = 1024 * 1024  # 1 MB
                copied = 0
                total = os.path.getsize(self.file_path)
                self.progress.emit(0, total)
                with open(self.file_path, "rb") as src, open(new_path, "wb") as dst:
                    # PATCH: interruption propre dans la boucle (test interne ET Qt)
                    while not self._is_interrupted and not QtCore.QThread.currentThread().isInterruptionRequested():
                        buf = src.read(buffer_size)
                        if not buf:
                            break
                        dst.write(buf)
                        copied += len(buf)
                        self.progress.emit(len(buf), total)
                # Après la boucle, si interruption (interne ou Qt), supprimer le fichier partiel et sortir immédiatement
                if self._is_interrupted or QtCore.QThread.currentThread().isInterruptionRequested():
                    try:
                        if os.path.exists(new_path):
                            os.remove(new_path)
                    except Exception:
                        pass
                    self.finished.emit(self.file_path, False, "")
                    return

                def file_hash(path):
                    h = xxhash.xxh64()
                    with open(path, 'rb') as f:
                        while True:
                            chunk = f.read(8192)
                            if not chunk:
                                break
                            h.update(chunk)
                    return h.hexdigest()

                if file_hash(self.file_path) != file_hash(new_path):
                    raise ValueError("Checksum mismatch after copy")

                checksum = file_hash(new_path)
                self.finished.emit(self.file_path, True, checksum)
        except Exception as e:
            print(f"Erreur sur {self.file_path} : {e}")
            self.finished.emit(self.file_path, False, "")


class DropListWidget(QtWidgets.QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setDragEnabled(False)
        self.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.setDragDropMode(QtWidgets.QAbstractItemView.InternalMove)

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_Backspace:
            for item in self.selectedItems():
                self.takeItem(self.row(item))
        elif event.matches(QtGui.QKeySequence.Delete):
            self.clear()

        elif event.modifiers() & QtCore.Qt.ControlModifier and event.key() in (QtCore.Qt.Key_Up, QtCore.Qt.Key_Down):
            selected_items = self.selectedItems()
            if not selected_items:
                return

            moved = []
            rows = [self.row(item) for item in selected_items]
            direction = -1 if event.key() == QtCore.Qt.Key_Up else 1
            new_rows = []

            for row in (rows if direction == 1 else reversed(rows)):
                new_row = row + direction
                if 0 <= new_row < self.count():
                    item = self.takeItem(row)
                    self.insertItem(new_row, item)
                    widget = self.itemWidget(item)
                    self.setItemWidget(item, widget)
                    moved.append(item)
                    new_rows.append(new_row)

            for item in moved:
                item.setSelected(True)
                file_path = item.data(QtCore.Qt.UserRole)
                basename = os.path.basename(file_path)
                rename_only = getattr(self.parent(), "rename_only", False)
                size_mb = os.path.getsize(file_path) / (1024 * 1024) if not rename_only else 0

                widget = QtWidgets.QWidget()
                widget.setStyleSheet("background-color: transparent;")
                widget.setAttribute(QtCore.Qt.WA_StyledBackground, False)
                layout = QtWidgets.QHBoxLayout(widget)
                layout.setContentsMargins(8, 2, 8, 2)

                name_label = QtWidgets.QLabel(basename)
                name_label.setStyleSheet("color: #fafafa; background-color: transparent;")
                layout.addWidget(name_label)

                if not rename_only:
                    size_label = QtWidgets.QLabel(f"{size_mb:.1f} MB")
                    size_label.setStyleSheet("color: #888888; padding-left: 5px; background-color: transparent;")
                    layout.addWidget(size_label)

                layout.addStretch()
                widget.setMinimumHeight(28)
                item.setSizeHint(QtCore.QSize(0, 28))
                self.setItemWidget(item, widget)
        else:
            super().keyPressEvent(event)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        event.acceptProposedAction()

    def dropEvent(self, event):
        from PySide6.QtWidgets import QLabel, QWidget, QHBoxLayout
        import re
        rename_only = getattr(self.parent(), "rename_only", False)
        ignore_mxf = load_params().get("ignore_mxf", True)

        def natural_sort_key(s):
            return [int(text) if text.isdigit() else text.lower() for text in re.split('([0-9]+)', os.path.basename(s))]

        def add_video_files_from_directory(directory):
            for root, dirs, files in os.walk(directory):
                # Exclure les dossiers indésirables
                dirs[:] = [d for d in dirs if not d.startswith('.') and d not in {"__MACOSX", ".trash", "Trash",
                                                                                  "System Volume Information"}]
                video_files = []
                for file in files:
                    if file.startswith("."):
                        continue
                    if file.lower().endswith((".mp4", ".mov", ".mxf")) and (not ignore_mxf or not file.lower().endswith(".mxf")):
                        full_path = os.path.join(root, file)
                        if os.path.getsize(full_path) == 0:
                            continue
                        video_files.append(full_path)
                for full_path in sorted(video_files, key=get_video_datetime):
                    basename = os.path.basename(full_path)
                    if not rename_only:
                        size_mb = os.path.getsize(full_path) / (1024 * 1024)
                    # Create a widget for each item with separate styling for filename and size
                    widget = QWidget()
                    widget.setStyleSheet("background-color: transparent;")
                    widget.setAttribute(QtCore.Qt.WA_StyledBackground, False)
                    layout = QHBoxLayout(widget)
                    layout.setContentsMargins(8, 2, 8, 2)
                    name_label = QLabel(basename)
                    name_label.setStyleSheet("color: #fafafa; background-color: transparent;")
                    layout.addWidget(name_label)
                    if not rename_only:
                        size_label = QLabel(f"{size_mb:.1f} MB")
                        size_label.setStyleSheet(
                            "color: #888888; padding-left: 5px; background-color: transparent;")
                        layout.addWidget(size_label)
                    layout.addStretch()
                    widget.setMinimumHeight(28)
                    item = QtWidgets.QListWidgetItem()
                    item.setSizeHint(QtCore.QSize(0, 28))
                    item.setData(QtCore.Qt.UserRole, full_path)
                    item.setData(QtCore.Qt.UserRole + 1, basename)
                    item.setIcon(self.parent().img_unchecked)
                    self.addItem(item)
                    self.setItemWidget(item, widget)

        file_paths = []
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if os.path.isdir(file_path):
                add_video_files_from_directory(file_path)
            elif file_path.lower().endswith((".mp4", ".mov", ".mxf")) and (not ignore_mxf or not file_path.lower().endswith(".mxf")):
                if os.path.getsize(file_path) == 0:
                    continue
                file_paths.append(file_path)
        for file_path in sorted(file_paths, key=get_video_datetime):
            basename = os.path.basename(file_path)
            if not rename_only:
                size_mb = os.path.getsize(file_path) / (1024 * 1024)
            # Create a widget for each item with separate styling for filename and size
            widget = QWidget()
            widget.setStyleSheet("background-color: transparent;")
            widget.setAttribute(QtCore.Qt.WA_StyledBackground, False)
            layout = QHBoxLayout(widget)
            layout.setContentsMargins(8, 2, 8, 2)
            name_label = QLabel(basename)
            name_label.setStyleSheet("color: #fafafa; background-color: transparent;")
            layout.addWidget(name_label)
            if not rename_only:
                size_label = QLabel(f"{size_mb:.1f} MB")
                size_label.setStyleSheet("color: #888888; padding-left: 5px; background-color: transparent;")
                layout.addWidget(size_label)
            layout.addStretch()
            widget.setMinimumHeight(28)
            item = QtWidgets.QListWidgetItem()
            item.setSizeHint(QtCore.QSize(0, 28))
            item.setData(QtCore.Qt.UserRole, file_path)
            item.setData(QtCore.Qt.UserRole + 1, basename)
            item.setIcon(self.parent().img_unchecked)
            self.addItem(item)
            self.setItemWidget(item, widget)


    def mouseDoubleClickEvent(self, event):
        item = self.itemAt(event.pos())
        if item:
            original_path = item.data(QtCore.Qt.UserRole)
            new_name = item.data(QtCore.Qt.UserRole + 1)
            main_window = self.parent()
            if not original_path or not main_window:
                return

            if main_window.rename_only:
                # Recomposer le nom du fichier renommé à partir des infos stockées
                index = item.data(QtCore.Qt.UserRole + 2) or 1
                ext = os.path.splitext(original_path)[1]
                date_suffix = datetime.datetime.now().strftime("%Y%m%d")
                camid = main_window.camid_input.text().strip()
                if camid:
                    new_name = f"{main_window.labroll_input.text()}C{index:03d}_{date_suffix}_{camid}{ext}"
                else:
                    new_name = f"{main_window.labroll_input.text()}C{index:03d}_{date_suffix}{ext}"
                dest_path = os.path.join(os.path.dirname(original_path), new_name)
            else:
                dest_path = os.path.join(main_window.destination_input.text(), new_name)

            if dest_path:
                print(dest_path)
                subprocess.call(["open", os.path.dirname(dest_path)])

        super().mouseDoubleClickEvent(event)

class MainWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.img_checked = QtGui.QIcon(str(resource_path("assets/images/checked.png")))
        self.img_unchecked = QtGui.QIcon(str(resource_path("assets/images/unchecked.png")))
        self.img_error = QtGui.QIcon(str(resource_path("assets/images/error.png")))
        self.img_processing = QtGui.QIcon(str(resource_path("assets/images/processing.png")))

        ensure_params_file()
        self.max_threads = load_params().get("max_concurrent_threads", 5)
        # Load rename_only setting
        self.rename_only = load_params().get("rename_only", False)
        # Set labroll input from last_labroll value at startup
        import re

        last_labroll = load_params().get("last_labroll", "A001")
        match = re.match(r"([A-Za-z]*)(\d+)", last_labroll)
        if match:
            prefix, number = match.groups()
            new_number = int(number) + 1
            labroll_value = f"{prefix}{new_number:03d}"
        else:
            labroll_value = last_labroll

        self.labroll_input = QtWidgets.QLineEdit()
        self.labroll_input.setPlaceholderText("Labroll")
        self.labroll_input.setText(labroll_value)
        self.camid_input = QtWidgets.QLineEdit()
        self.camid_input.setPlaceholderText("Cam ID")
        last_camid = load_params().get("last_camid", "")
        self.camid_input.setText(last_camid)

        self.destination_input = QtWidgets.QLineEdit()
        self.destination_input.setPlaceholderText("Destination folder")
        last_dest = load_params().get("last_destination", "")
        if last_dest:
            self.destination_input.setText(last_dest)
        # Disable destination_input if rename_only
        self.destination_input.setEnabled(not self.rename_only)

        self.setup_ui()
        # After UI setup, update file weights for rename_only items already loaded
        for i in range(self.drop_list.count()):
            item = self.drop_list.item(i)
            custom_widget = self.drop_list.itemWidget(item)
            if custom_widget:
                layout = custom_widget.layout()
                if layout and layout.count() >= 2:
                    size_label = layout.itemAt(1).widget()
                    if isinstance(size_label, QtWidgets.QLabel):
                        base_style = "padding-left: 5px; background-color: transparent;"
                        if self.rename_only:
                            size_label.setStyleSheet(f"color: rgba(0, 0, 0, 0); {base_style}")
                        else:
                            size_label.setStyleSheet(f"color: #888888; {base_style}")
        self.threads = []
        self.active_threads = []
        self.queue = deque()
        self.current_file_size = 0
        self.current_file_copied = 0
        self.current_file_start_time = None
        css_file = resource_path("assets/style.css")
        with open(css_file, 'r') as f:
            self.setStyleSheet(f.read())

    def setup_ui(self):
        self.setWindowTitle("Labroll Utility v2.0.0")



        # self.labroll_input is now initialized in __init__ with value from last_labroll

        # self.destination_input is now initialized in __init__ with value from last_destination
        browse_button = QtWidgets.QPushButton("Browse")
        browse_button.clicked.connect(self.browse_destination)
        # Disable browse_button if rename_only
        browse_button.setEnabled(not self.rename_only)

        self.destination_layout = QtWidgets.QHBoxLayout()
        self.destination_layout.addWidget(self.destination_input)
        self.destination_layout.addWidget(browse_button)

        self.rename_button = QtWidgets.QPushButton("Rename")
        self.rename_button.clicked.connect(self.process_labroll)

        self.cancel_button = QtWidgets.QPushButton("Cancel")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self.cancel_all)

        self.resume_button = QtWidgets.QPushButton("Restart")
        self.resume_button.setEnabled(False)
        self.resume_button.clicked.connect(self.resume_copy)

        self.clear_button = QtWidgets.QPushButton("Empty list")
        self.clear_button.clicked.connect(self.drop_list_clear)

        self.drop_list = DropListWidget(self)

        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)

        # Counter label, percent label, and status icon row
        self.counter_label = QtWidgets.QLabel("0 / 0")
        self.percent_label = QtWidgets.QLabel("0.0 %")
        self.status_icon_label = QtWidgets.QLabel()
        counter_row = QtWidgets.QHBoxLayout()
        counter_row.addWidget(self.counter_label)
        counter_row.addStretch()
        counter_row.addWidget(self.percent_label)
        counter_row.addWidget(self.status_icon_label)

        layout = QtWidgets.QVBoxLayout()
        # Replace Labroll label/input with a horizontal row including Cam ID
        labroll_row = QtWidgets.QHBoxLayout()
        labroll_label = QtWidgets.QLabel("Labroll :")
        labroll_row.addWidget(labroll_label)
        labroll_row.addWidget(self.labroll_input)
        labroll_row.addWidget(self.camid_input)
        layout.addLayout(labroll_row)
        layout.addLayout(self.destination_layout)
        # Replace drop label and list block with row including clear button and icon
        drop_label = QtWidgets.QLabel("Drop video folder or files :")
        clear_icon = QtGui.QIcon(str(resource_path("assets/images/refresh.png")))

        self.clear_button.setIcon(clear_icon)
        self.clear_button.setIconSize(QtCore.QSize(24, 24))
        self.clear_button.setFixedSize(32, 32)
        self.clear_button.setText("")
        self.clear_button.setStyleSheet("QPushButton { border: none; background-color: transparent; }")
        drop_row = QtWidgets.QHBoxLayout()
        drop_row.addWidget(drop_label)
        drop_row.addStretch()
        drop_row.addWidget(self.clear_button)
        layout.addLayout(drop_row)
        layout.addWidget(self.drop_list)
        layout.addWidget(self.rename_button)
        # Replace cancel and resume button widgets with horizontal layout
        action_row = QtWidgets.QHBoxLayout()
        action_row.addWidget(self.cancel_button)
        action_row.addWidget(self.resume_button)
        layout.addLayout(action_row)
        layout.addWidget(self.progress_bar)
        layout.addLayout(counter_row)

        settings_button = QtWidgets.QPushButton()
        settings_icon = QtGui.QIcon(str(resource_path("assets/images/params.png")))
        settings_button.setIcon(settings_icon)
        settings_button.setIconSize(QtCore.QSize(24, 24))
        settings_button.setFixedSize(36, 36)
        settings_button.setToolTip("Paramètres")
        settings_button.setStyleSheet("QPushButton { border: none; background-color: transparent; }")
        settings_button.clicked.connect(lambda: show(None))

        settings_layout = QtWidgets.QHBoxLayout()
        settings_layout.addStretch()
        settings_layout.addWidget(settings_button)
        layout.addLayout(settings_layout)

        self.setLayout(layout)
        self.build_menu_bar()

    def build_menu_bar(self):
        menu_bar = QtWidgets.QMenuBar(self)
        file_menu = menu_bar.addMenu("Fichier")

        import_action = QtGui.QAction("Reverse from JSON", self)
        import_action.triggered.connect(self.reverse_from_json)
        file_menu.addAction(import_action)

        # Add "Afficher les paramètres" action to open preferences dialog
        show_params_action = QtGui.QAction("Parameters", self)
        show_params_action.triggered.connect(lambda: show(None))
        file_menu.addAction(show_params_action)

        layout = self.layout()
        layout.setMenuBar(menu_bar)

    def reverse_from_json(self):
        from PySide6.QtWidgets import QFileDialog
        import json

        file_path, _ = QFileDialog.getOpenFileName(self, "Sélectionner un fichier JSON", "", "Fichiers JSON (*.json)")
        if not file_path:
            return

        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            self.drop_list.clear()

            for entry in data.get("hashes", []):
                original_name = entry["file"]
                full_path = os.path.join(self.destination_input.text(), original_name)
                if not os.path.exists(full_path):
                    continue

                basename = os.path.basename(full_path)
                widget = QtWidgets.QWidget()
                widget.setStyleSheet("background-color: transparent;")
                widget.setAttribute(QtCore.Qt.WA_StyledBackground, False)
                layout = QtWidgets.QHBoxLayout(widget)
                layout.setContentsMargins(8, 2, 8, 2)
                name_label = QtWidgets.QLabel(basename)
                name_label.setStyleSheet("color: #fafafa; background-color: transparent;")
                layout.addWidget(name_label)
                layout.addStretch()
                widget.setMinimumHeight(28)
                item = QtWidgets.QListWidgetItem()
                item.setSizeHint(QtCore.QSize(0, 28))
                item.setData(QtCore.Qt.UserRole, full_path)
                item.setData(QtCore.Qt.UserRole + 1, basename)
                item.setIcon(self.img_checked)
                self.drop_list.addItem(item)
                self.drop_list.setItemWidget(item, widget)

        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Erreur", f"Impossible de charger le fichier JSON : {e}")

    def browse_destination(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Choisir le dossier destination")
        if folder:
            self.destination_input.setText(folder)
            save_params({"last_destination": folder})

    def drop_list_clear(self):
        self.drop_list.clear()
        self.drop_list.setStyleSheet("background-color: transparent; margin: 4px; background-color: #303030;")
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        self.counter_label.setText("0 / 0")
        self.percent_label.setText("0.0 %")
        self.status_icon_label.clear()
        self.resume_button.setEnabled(False)

    def process_labroll(self):
        # Inserted block: load settings and update labroll input
        settings = load_params()
        # Copie toujours séquentielle pour garantir l’ordre
        self.max_threads = 1
        export_mhl = settings.get("export_mhl", True)
        export_json = settings.get("export_json", True)
        rename_only = settings.get("rename_only", False)

        self.rename_only = rename_only

        import getpass
        import socket
        self.start_time = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        self.files_to_process = []
        for i in range(self.drop_list.count()):
            item = self.drop_list.item(i)
            file_path = item.data(QtCore.Qt.UserRole)
            self.files_to_process.append(file_path)
            item.setData(QtCore.Qt.UserRole + 2, i + 1)  # Stocker l'ordre visuel (1-based index)
        self.total_bytes = sum(os.path.getsize(path) for path in self.files_to_process if os.path.exists(path))
        self.copied_bytes = 0

        if self.rename_only:
            self.destination_folder = ""
        else:
            destination_folder = self.destination_input.text().strip()
            if not destination_folder:
                QtWidgets.QMessageBox.warning(self, "Erreur", "Veuillez sélectionner un dossier de destination.")
                return
            try:
                os.makedirs(destination_folder, exist_ok=True)
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Erreur", f"Impossible de créer le dossier :\n{e}")
                return
            self.destination_folder = destination_folder
            save_params({"last_destination": destination_folder})

        labroll_name = self.labroll_input.text().strip()
        # Save last labroll name
        save_params({"last_labroll": labroll_name})
        camid = self.camid_input.text().strip()
        save_params({"last_camid": camid})
        if not labroll_name:
            QtWidgets.QMessageBox.warning(self, "Erreur", "Please type in the labroll name.")
            return

        if not self.files_to_process:
            QtWidgets.QMessageBox.warning(self, "Aucun fichier", "No video file in the list.")
            return

        # Réinitialiser les icônes dans la liste
        for i in range(self.drop_list.count()):
            item = self.drop_list.item(i)
            item.setIcon(self.img_unchecked)

        self.completed_count = 0
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.counter_label.setText(f"0 / {len(self.files_to_process)}")

        self.cancel_button.setEnabled(True)
        self.rename_button.setEnabled(False)
        self.queue = deque(self.files_to_process)
        self.active_threads = []
        self.hash_log = {}
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
        self.mhl_file_path = os.path.join(self.destination_folder, f"{labroll_name}_{timestamp}.mhl")
        self.start_next_threads(labroll_name, self.destination_folder)
        self.resume_button.setEnabled(False)

    def start_next_threads(self, labroll_name, destination_folder):
        # Prepare camid and assign index for each file
        camid = self.camid_input.text().strip()
        # Launch threads in the order of files_to_process
        while self.queue and len(self.active_threads) < self.max_threads:
            file_path = self.queue.popleft()
            try:
                for i in range(self.drop_list.count()):
                    item = self.drop_list.item(i)
                    if item.data(QtCore.Qt.UserRole) == file_path:
                        # --- Ajout : marquer l’icône en cours de traitement ---
                        item.setIcon(self.img_processing)
                        index = item.data(QtCore.Qt.UserRole + 2)
                        original_name = item.data(QtCore.Qt.UserRole + 1)
                        break
                else:
                    index = 1  # valeur de secours
            except ValueError:
                continue  # skip if file_path not found
            thread = QtCore.QThread()
            worker = CopyRenameWorker(file_path, labroll_name, destination_folder, camid=camid, labroll_index=index, original_name=original_name)
            worker.rename_only = self.rename_only
            worker.moveToThread(thread)

            thread.started.connect(worker.run)
            worker.finished.connect(self.on_file_processed, QtCore.Qt.QueuedConnection)
            worker.finished.connect(thread.quit)
            worker.finished.connect(worker.deleteLater)
            thread.finished.connect(thread.deleteLater)
            thread.finished.connect(lambda t=thread: self.thread_finished(t))
            # Connect progress signal for copy mode only
            if not self.rename_only:
                worker.progress.connect(self.on_copy_progress, QtCore.Qt.QueuedConnection)

            def thread_finished(self, thread):
                if thread in self.active_threads:
                    self.active_threads.remove(thread)

                if self.queue:
                    QtCore.QTimer.singleShot(
                        0,
                        lambda: self.start_next_threads(self.labroll_input.text(), self.destination_folder)
                    )

            thread.start()
            self.active_threads.append(thread)
            self.threads.append((thread, worker))
    def on_copy_progress(self, bytes_chunk, total_file_size):
        now = QtCore.QTime.currentTime()

        if self.current_file_start_time is None:
            self.current_file_start_time = QtCore.QTime.currentTime()
            self.current_file_size = total_file_size
            self.current_file_copied = 0

        self.current_file_copied += bytes_chunk
        self.copied_bytes += bytes_chunk

        # Clamp global_percent
        if self.total_bytes > 0:
            global_percent = min(
                100.0,
                (self.copied_bytes / self.total_bytes) * 100
            )
        else:
            global_percent = 0.0

        copied_gb = self.copied_bytes / (1024 ** 3)
        total_gb = self.total_bytes / (1024 ** 3)

        self.progress_bar.setValue(int(global_percent))
        self.percent_label.setText(
            f"{global_percent:.1f} % ({copied_gb:.2f} / {total_gb:.2f} GB)"
        )

    def thread_finished(self, thread):
        if thread in self.active_threads:
            self.active_threads.remove(thread)
        if self.queue:  # uniquement si la queue n’a pas été vidée
            self.start_next_threads(self.labroll_input.text(), self.destination_folder)
    def cancel_all(self):
        reply = QtWidgets.QMessageBox.question(self, "Confirmation", "Êtes-vous sûr de vouloir annuler la copie en cours ?",
                                               QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        if reply == QtWidgets.QMessageBox.Yes:
            # PATCH: interruption immédiate sans thread.quit/wait, seulement interrupt + requestInterruption
            for thread, worker in list(self.threads):
                try:
                    if thread is not None and thread.isRunning():
                        worker.interrupt()
                        thread.requestInterruption()
                except RuntimeError:
                    continue
            # Après l'annulation, ne pas bloquer, juste nettoyer
            self.threads = []
            self.active_threads = []
            # The following block for deleting unprocessed files is intentionally removed to allow resuming without loss.
            # Only keep files in the queue that are not already marked as checked (successfully processed)
            remaining = []
            for i in range(self.drop_list.count()):
                item = self.drop_list.item(i)
                path = item.data(QtCore.Qt.UserRole)
                if item.icon().cacheKey() != self.img_checked.cacheKey():
                    remaining.append(path)
            self.queue = deque(remaining)
            self.cancel_button.setEnabled(False)
            self.rename_button.setEnabled(True)
            self.resume_button.setEnabled(True)
            # PATCH: Forcer un rafraîchissement UI non bloquant après interruption
            QtCore.QCoreApplication.processEvents(QtCore.QEventLoop.AllEvents, 100)

    def resume_copy(self):
        self.resume_button.setEnabled(False)
        self.rename_button.setEnabled(False)
        self.cancel_button.setEnabled(True)

        remaining = []
        for i in range(self.drop_list.count()):
            item = self.drop_list.item(i)
            file_path = item.data(QtCore.Qt.UserRole)
            dest_name = f"{self.labroll_input.text()}_{os.path.basename(file_path)}"
            dest_path = os.path.join(self.destination_folder, dest_name)

            if not os.path.exists(dest_path):
                remaining.append(file_path)
            else:
                # Vérifier si le fichier a été traité correctement (icone checked)
                for j in range(self.drop_list.count()):
                    check_item = self.drop_list.item(j)
                    if check_item.data(QtCore.Qt.UserRole) == file_path:
                        if check_item.icon().cacheKey() != self.img_checked.cacheKey():
                            remaining.append(file_path)
                        break

        self.queue = deque(remaining)
        self.start_next_threads(self.labroll_input.text(), self.destination_folder)

    def on_file_processed(self, file_path, success, checksum):
        import json
        import getpass
        import socket
        import os

        # --- PATCH 4: Protection contre double mise à jour ---
        for i in range(self.drop_list.count()):
            it = self.drop_list.item(i)
            if it.data(QtCore.Qt.UserRole) == file_path and it.data(QtCore.Qt.UserRole + 4):
                return

        # Réinitialiser les compteurs de progression du fichier courant
        self.current_file_start_time = None
        self.current_file_copied = 0
        self.current_file_size = 0

        # (SUPPRIMÉ) Phase de finalisation visuelle pour éviter l’impression de freeze
        # (Ce bloc a été supprimé pour laisser place à la progression indéterminée)

        self.completed_count += 1
        copied_size = 0
        # Determine destination/renamed file and copied_size appropriately
        if self.rename_only:
            copied_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
            self.copied_bytes += copied_size
        # For copy mode, copied_bytes is updated in on_copy_progress, do not increment here
        # Update progress bar value as percentage (0-100)
        if self.rename_only:
            percent = (self.completed_count / len(self.files_to_process)) * 100
            self.progress_bar.setValue(min(round(percent), 100))
        else:
            percent = (self.copied_bytes / self.total_bytes) * 100 if self.total_bytes else 0
            self.progress_bar.setValue(min(round(percent), 100))
        self.counter_label.setText(f"{self.completed_count} / {len(self.files_to_process)}")
        # Update percent label to include GB values (always show for both copy and rename)
        copied_gb = self.copied_bytes / (1024 ** 3)
        total_gb = self.total_bytes / (1024 ** 3)
        if self.rename_only:
            self.percent_label.setText(f"{percent:.1f} %")
        else:
            self.percent_label.setText(f"{percent:.1f} % ({copied_gb:.1f} / {total_gb:.1f} GB)")

        # Force UI update after each file processed
        QtCore.QCoreApplication.processEvents()

        import os
        for i in range(self.drop_list.count()):
            item = self.drop_list.item(i)

            original_path = item.data(QtCore.Qt.UserRole)
            if os.path.normpath(original_path) == os.path.normpath(file_path):
                widget = self.drop_list.itemWidget(item)
                if widget:
                    layout = widget.layout()
                    if layout and layout.count() >= 1:
                        name_label = layout.itemAt(0).widget()
                        if isinstance(name_label, QtWidgets.QLabel):
                            # --- PATCH 2: Corriger le renommage visuel en mode copie ---
                            index = item.data(QtCore.Qt.UserRole + 2)
                            ext = os.path.splitext(file_path)[1]
                            date_suffix = datetime.datetime.now().strftime("%Y%m%d")
                            camid = self.camid_input.text().strip()
                            if camid:
                                renamed = f"{self.labroll_input.text()}C{index:03d}_{date_suffix}_{camid}{ext}"
                            else:
                                renamed = f"{self.labroll_input.text()}C{index:03d}_{date_suffix}{ext}"
                            name_label.setText(renamed)
                item.setIcon(self.img_checked if success else self.img_error)
                # --- PATCH 3: Marquer l’item comme traité dès la fin de son worker ---
                item.setData(QtCore.Qt.UserRole + 4, True)  # marqué comme traité
                break

        # Insert new logic for hash_log with renamed file as key
        if success and checksum:
            import os
            # Compose the new (renamed) filename as key
            new_basename = os.path.basename(file_path) if self.rename_only else os.path.basename(os.path.join(self.destination_folder, f"{self.labroll_input.text()}C{self.completed_count:03d}_{datetime.datetime.now().strftime('%Y%m%d')}{'_' + self.camid_input.text().strip() if self.camid_input.text().strip() else ''}{os.path.splitext(file_path)[1]}"))
            self.hash_log[new_basename] = checksum
        # For backward compatibility, keep the old mapping as well
        if success and checksum:
            self.hash_log[file_path] = checksum

        # --- PATCH 1: Forcer la progression à 100 % à la toute fin ---
        # (Déplacé, voir plus bas pour la nouvelle logique de progression indéterminée)

        # ────────────────
        # PATCH : Progression indéterminée pendant la finalisation (checksum, logs, MHL/JSON)
        # ────────────────
        if not self.rename_only and self.completed_count == len(self.files_to_process):
            # Entrée en phase de finalisation : progression indéterminée
            self.progress_bar.setRange(0, 0)
            self.percent_label.setText("Finalisation…")
            QtCore.QCoreApplication.processEvents()

        if self.completed_count == len(self.files_to_process):
            # Export log if enabled
            if load_params().get("export_log", True):
                try:
                    if self.rename_only:
                        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
                        log_path = os.path.join(
                            os.path.dirname(self.files_to_process[0]),
                            f"{self.labroll_input.text()}_{timestamp}.log"
                        )
                    else:
                        log_path = self.mhl_file_path.replace(".mhl", ".log")
                    with open(log_path, "w") as log_file:
                        log_file.write(f'### CREATING LABROLL\nStarting at {self.start_time}\n\n')
                        index = 0
                        for i in range(self.drop_list.count()):
                            item = self.drop_list.item(i)
                            path = item.data(QtCore.Qt.UserRole)
                            orig_name = os.path.basename(path)

                            # Reconstruct renamed name based on stored order
                            labroll_index = item.data(QtCore.Qt.UserRole + 2)
                            ext = os.path.splitext(path)[1]
                            date_suffix = datetime.datetime.now().strftime("%Y%m%d")
                            camid = self.camid_input.text().strip()
                            if camid:
                                new_name = f"{self.labroll_input.text()}C{labroll_index:03d}_{date_suffix}_{camid}{ext}"
                            else:
                                new_name = f"{self.labroll_input.text()}C{labroll_index:03d}_{date_suffix}{ext}"

                            hash_summary = self.hash_log.get(new_name, "") or self.hash_log.get(path, "")
                            index += 1
                            log_file.write(f'[#{index:02d}] {orig_name} --> {new_name} | hash: {hash_summary}\n')
                        log_file.write(f'\n### END OF OPERATION at {datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")}')
                except Exception as e:
                    print(f"Erreur lors de l'écriture du log : {e}")
            # If any failure, update icon for failed file(s)
            if not success:
                for i in range(self.drop_list.count()):
                    item = self.drop_list.item(i)
                    if item.data(QtCore.Qt.UserRole) == file_path:
                        item.setIcon(self.img_error)
                        break
            self.cancel_button.setEnabled(False)
            self.rename_button.setEnabled(True)

            # Sortie de la phase indéterminée, retour à 100 % avant de masquer la barre
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(100)
            self.percent_label.setText("100 % | Terminé")
            QtCore.QCoreApplication.processEvents()
            self.progress_bar.setVisible(False)

            # Set status icon on the same row as counter/percent
            self.status_icon_label.setPixmap(self.img_checked.pixmap(16, 16))

            # --- BEGIN PATCHED BLOCK ---
            export_mhl = load_params().get("export_mhl", True)
            export_json = load_params().get("export_json", True)

            if not self.rename_only and (export_mhl or export_json):
                start_time = self.start_time
                finish_time = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

                # Only write MHL if export_mhl is enabled
                if export_mhl:
                    with open(self.mhl_file_path, 'w') as mhl_file:
                        mhl_file.write('<?xml version="1.0" encoding="UTF-8"?>\n')
                        mhl_file.write('<hashlist version="1.1">\n\n')
                        mhl_file.write('  <creatorinfo>\n')
                        mhl_file.write(f'    <name>{getpass.getuser()}</name>\n')
                        mhl_file.write(f'    <username>{getpass.getuser()}</username>\n')
                        mhl_file.write(f'    <hostname>{socket.gethostname()}</hostname>\n')
                        mhl_file.write('    <tool>labrollUtility</tool>\n')
                        mhl_file.write(f'    <startdate>{start_time}</startdate>\n')
                        mhl_file.write(f'    <finishdate>{finish_time}</finishdate>\n')
                        mhl_file.write('  </creatorinfo>\n\n')

                        for filename, checksum in self.hash_log.items():
                            if os.path.sep in filename:  # skip original full paths
                                continue
                            full_path = os.path.join(self.destination_folder, filename)
                            try:
                                size = os.path.getsize(full_path)
                                mtime = datetime.datetime.utcfromtimestamp(os.path.getmtime(full_path)).strftime("%Y-%m-%dT%H:%M:%SZ")
                            except Exception:
                                size = 0
                                mtime = ""
                            mhl_file.write('  <hash>\n')
                            mhl_file.write(f'    <file>{filename}</file>\n')
                            mhl_file.write(f'    <size>{size}</size>\n')
                            mhl_file.write(f'    <lastmodificationdate>{mtime}</lastmodificationdate>\n')
                            mhl_file.write(f'    <xxhash64be>{checksum}</xxhash64be>\n')
                            mhl_file.write(f'    <hashdate>{finish_time}</hashdate>\n')
                            mhl_file.write('  </hash>\n\n')

                        mhl_file.write('</hashlist>\n')

                json_data = {
                    "creatorinfo": {
                        "name": getpass.getuser(),
                        "username": getpass.getuser(),
                        "hostname": socket.gethostname(),
                        "tool": "labrollUtility",
                        "startdate": self.start_time,
                        "finishdate": finish_time
                    },
                    "hashes": []
                }

                for i in range(self.drop_list.count()):
                    item = self.drop_list.item(i)
                    new_name = ""
                    hash_value = ""
                    original_name = item.data(QtCore.Qt.UserRole + 1)
                    labroll_index = item.data(QtCore.Qt.UserRole + 2)
                    ext = os.path.splitext(original_name)[1]
                    date_suffix = datetime.datetime.now().strftime("%Y%m%d")
                    camid = self.camid_input.text().strip()

                    if camid:
                        new_name = f"{self.labroll_input.text()}C{labroll_index:03d}_{date_suffix}_{camid}{ext}"
                    else:
                        new_name = f"{self.labroll_input.text()}C{labroll_index:03d}_{date_suffix}{ext}"

                    hash_value = self.hash_log.get(new_name, "") or self.hash_log.get(item.data(QtCore.Qt.UserRole), "")

                    full_path = os.path.join(self.destination_folder, new_name)
                    try:
                        size = os.path.getsize(full_path)
                        mtime = datetime.datetime.utcfromtimestamp(os.path.getmtime(full_path)).strftime("%Y-%m-%dT%H:%M:%SZ")
                    except Exception:
                        size = 0
                        mtime = ""

                    json_data["hashes"].append({
                        "file": new_name,
                        "original": original_name,
                        "size": size,
                        "lastmodificationdate": mtime,
                        "xxhash64be": hash_value,
                        "hashdate": finish_time
                    })

                # Only write JSON if export_json is enabled
                if export_json:
                    json_path = self.mhl_file_path.replace(".mhl", ".json")
                    with open(json_path, "w") as json_file:
                        json.dump(json_data, json_file, indent=2)
            # --- END PATCHED BLOCK ---

            # Send Slack and/or Discord messages if enabled
            try:
                settings = load_params()
                slack_hook = settings.get("slack_hook", "")
                discord_hook = settings.get("discord_hook", "")
                slack_active = settings.get("slack_active", False)
                discord_active = settings.get("discord_active", False)

                message = f"✅ Labroll {self.labroll_input.text()} done with {self.completed_count} clips renamed."

                if slack_active and slack_hook:
                    import requests
                    payload = {"text": message}
                    requests.post(slack_hook, json=payload)

                if discord_active and discord_hook:
                    from discordwebhook import Discord
                    discord = Discord(url=discord_hook)
                    discord.post(content=message)

            except Exception as notify_error:
                print(f"Erreur lors de l'envoi des notifications : {notify_error}")

            # Auto-increment labroll name after completion
            import re
            current_labroll = self.labroll_input.text().strip()
            match = re.match(r"([A-Za-z]*)(\d+)", current_labroll)
            if match:
                prefix, number = match.groups()
                new_number = int(number) + 1
                new_labroll = f"{prefix}{new_number:03d}"
                self.labroll_input.setText(new_labroll)
                save_params({"last_labroll": new_labroll})

    def closeEvent(self, event):
        # Use a safer loop to avoid accessing deleted threads
        for thread, worker in list(self.threads):
            try:
                if thread and thread.isRunning():
                    thread.quit()
                    thread.wait()
            except RuntimeError:
                continue
        event.accept()

    def reverse_from_json(self):
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        import json

        file_path, _ = QFileDialog.getOpenFileName(self, "Sélectionner un fichier JSON", "", "Fichiers JSON (*.json)")
        if not file_path:
            return

        try:
            with open(file_path, 'r') as f:
                data = json.load(f)

            self.drop_list.clear()
            recovered_files = []

            for entry in data.get("hashes", []):
                renamed = entry["file"]
                full_path = os.path.join(self.destination_input.text(), renamed)
                if not os.path.exists(full_path):
                    continue

                # Use the original filename from the JSON entry
                original_path = os.path.join(self.destination_input.text(), entry.get("original", ""))
                print(f'original_path : {original_path}')

                # Ajout à la liste
                widget = QtWidgets.QWidget()
                widget.setStyleSheet("background-color: transparent;")
                widget.setAttribute(QtCore.Qt.WA_StyledBackground, False)

                layout = QtWidgets.QHBoxLayout(widget)
                layout.setContentsMargins(8, 2, 8, 2)

                name_label = QtWidgets.QLabel(renamed)
                name_label.setStyleSheet("color: #fafafa; background-color: transparent;")
                layout.addWidget(name_label)
                layout.addStretch()

                # Force a consistent row height (same as normal drop rows)
                widget.setMinimumHeight(32)

                item = QtWidgets.QListWidgetItem()
                item.setSizeHint(QtCore.QSize(0, 32))
                item.setData(QtCore.Qt.UserRole, full_path)
                item.setData(QtCore.Qt.UserRole + 1, renamed)
                item.setData(QtCore.Qt.UserRole + 3, original_path)
                item.setIcon(self.img_checked)
                self.drop_list.addItem(item)
                self.drop_list.setItemWidget(item, widget)

                recovered_files.append((full_path, original_path))

            if recovered_files:
                from PySide6.QtWidgets import QDialog, QVBoxLayout, QDialogButtonBox, QCheckBox, QLabel

                dialog = QDialog(self)
                dialog.setWindowTitle("Restaurer les fichiers sélectionnés")
                layout = QVBoxLayout(dialog)
                layout.addWidget(QLabel("Sélectionnez les fichiers à restaurer à leur nom original :"))

                checkboxes = []
                for renamed_path, original_path in recovered_files:
                    cb = QCheckBox(f"{os.path.basename(renamed_path)} → {os.path.basename(original_path)}")
                    cb.renamed_path = renamed_path
                    cb.original_path = original_path
                    cb.setChecked(True)
                    checkboxes.append(cb)
                    layout.addWidget(cb)

                buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
                buttons.accepted.connect(dialog.accept)
                buttons.rejected.connect(dialog.reject)
                layout.addWidget(buttons)

                if dialog.exec():
                    for cb in checkboxes:
                        if cb.isChecked() and os.path.exists(cb.renamed_path):
                            try:
                                shutil.move(cb.renamed_path, cb.original_path)
                            except Exception as e:
                                print(f"Erreur lors de la restauration : {e}")
                else:
                    # User cancelled: offer to copy files to another folder and add to the list
                    from PySide6.QtWidgets import QFileDialog
                    target_folder = QFileDialog.getExistingDirectory(self, "Sélectionner le dossier de destination pour la copie des fichiers originaux")
                    if target_folder:
                        for renamed_path, original_path in recovered_files:
                            try:
                                shutil.copy2(renamed_path, os.path.join(target_folder, os.path.basename(original_path)))
                                # Also add copied file to the list
                                copied_path = os.path.join(target_folder, os.path.basename(original_path))
                                if os.path.exists(copied_path):
                                    basename = os.path.basename(copied_path)
                                    widget = QtWidgets.QWidget()
                                    widget.setStyleSheet("background-color: transparent;")
                                    widget.setAttribute(QtCore.Qt.WA_StyledBackground, False)

                                    layout = QtWidgets.QHBoxLayout(widget)
                                    layout.setContentsMargins(8, 2, 8, 2)

                                    name_label = QtWidgets.QLabel(basename)
                                    name_label.setStyleSheet("color: #fafafa; background-color: transparent;")
                                    layout.addWidget(name_label)
                                    layout.addStretch()
                                    widget.setMinimumHeight(28)

                                    item = QtWidgets.QListWidgetItem()
                                    item.setSizeHint(QtCore.QSize(0, 28))
                                    item.setData(QtCore.Qt.UserRole, copied_path)
                                    item.setData(QtCore.Qt.UserRole + 1, basename)
                                    item.setIcon(self.img_checked)
                                    self.drop_list.addItem(item)
                                    self.drop_list.setItemWidget(item, widget)
                            except Exception as e:
                                print(f"Erreur lors de la copie : {e}")

        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Impossible de charger le JSON : {e}")
