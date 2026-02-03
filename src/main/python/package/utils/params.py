import sys
from pathlib import Path

def resource_path(relative_path):
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / relative_path
    return Path(__file__).resolve().parent / relative_path

from PySide6 import QtWidgets, QtCore
import os
import json
import requests
from discordwebhook import Discord

def get_params_path():
    return os.path.join(os.path.expanduser("~"), "Library", "Application Support", "LabrollUtility", "labrollUtility_params.json")

def ensure_params_file():
    app_support_path = os.path.dirname(get_params_path())
    os.makedirs(app_support_path, exist_ok=True)

    if not os.path.exists(get_params_path()):
        with open(get_params_path(), 'w') as f:
            json.dump({
                "last_labroll": "A000",
                "nb_thread": 5,
                "export_mhl": True,
                "export_json": True,
                "export_log": True,
                "rename_only": False,
                "ignore_mxf": True,
                "camid": "",
                "slack_active": False,
                "slack_hook": "",
                "discord_active": False,
                "discord_hook": "",
                "slack_locked": False,
                "discord_locked": False
            }, f, indent=4)
    return get_params_path()

def load_params():
    ensure_params_file()
    try:
        with open(get_params_path(), 'r') as f:
            return json.load(f)
    except:
        return {}

def save_params(new_data):
    print(f'save settings : {new_data}')
    ensure_params_file()
    data = load_params()
    data.update(new_data)
    with open(get_params_path(), 'w') as f:
        json.dump(data, f, indent=4)


def show(parent=None):
    dialog = QtWidgets.QDialog(None)
    try:
        css_file = resource_path("assets/style.css")
        with open(css_file, 'r') as f:
            dialog.setStyleSheet(f.read())
    except Exception:
        pass
    dialog.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint)
    dialog.setAttribute(QtCore.Qt.WA_TranslucentBackground)
    dialog.setWindowTitle("Preferences")
    dialog.setModal(True)
    dialog.resize(int(1920 / 5), dialog.sizeHint().height())

    #Appliquer le style global à la fenêtre
    try:
        css_file = resource_path("assets/style.css")
        with open(css_file, 'r') as f:
            dialog.setStyleSheet(f.read())
    except Exception:
        pass

    layout = QtWidgets.QVBoxLayout()

    # Slider de nombre de threads
    import multiprocessing
    max_threads = max(1, multiprocessing.cpu_count() // 2)
    current_params = load_params()
    current_value = current_params.get("nb_thread", 5)

    # Load export preferences
    mhl_enabled = current_params.get("export_mhl", True)
    json_enabled = current_params.get("export_json", True)
    log_enabled = current_params.get("export_log", True)
    rename_only = current_params.get("rename_only", False)
    ignore_mxf = current_params.get("ignore_mxf", True)

    slack_locked = current_params.get("slack_locked", False)
    discord_locked = current_params.get("discord_locked", False)

    slider_label = QtWidgets.QLabel(f"Threads : {current_value}")
    slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
    slider.setMinimum(1)
    slider.setMaximum(max_threads)
    slider.setValue(current_value)

    def update_value(value):
        slider_label.setText(f"Threads : {value}")
        save_params({"nb_thread": value})

    slider.valueChanged.connect(update_value)

    layout.addWidget(slider_label)
    layout.addWidget(slider)

    # Add MHL export checkbox
    mhl_checkbox = QtWidgets.QCheckBox("Export xxhash MHL")
    mhl_checkbox.setChecked(mhl_enabled)
    mhl_checkbox.stateChanged.connect(lambda state: save_params({"export_mhl": bool(state)}))

    # Add JSON export checkbox
    json_checkbox = QtWidgets.QCheckBox("Export xxHash JSON")
    json_checkbox.setChecked(json_enabled)
    json_checkbox.stateChanged.connect(lambda state: save_params({"export_json": bool(state)}))

    layout.addWidget(mhl_checkbox)
    layout.addWidget(json_checkbox)

    # Add Log export checkbox
    log_checkbox = QtWidgets.QCheckBox("Export Log")
    log_checkbox.setChecked(log_enabled)
    log_checkbox.stateChanged.connect(lambda state: save_params({"export_log": bool(state)}))
    layout.addWidget(log_checkbox)

    # Add Rename Only checkbox
    rename_checkbox = QtWidgets.QCheckBox("Rename only (no copy)")
    rename_checkbox.setToolTip("Désactive la copie de fichiers : seuls les noms seront modifiés dans leur emplacement d’origine.")
    rename_checkbox.setChecked(rename_only)

    def toggle_export_options(state):
        is_renaming = bool(state)
        mhl_checkbox.setEnabled(not is_renaming)
        json_checkbox.setEnabled(not is_renaming)
        #log_checkbox.setEnabled(not is_renaming)

        save_params({"rename_only": is_renaming})

    rename_checkbox.stateChanged.connect(toggle_export_options)
    layout.addWidget(rename_checkbox)

    mxf_checkbox = QtWidgets.QCheckBox("Ignore MXF video files")
    mxf_checkbox.setChecked(ignore_mxf)
    mxf_checkbox.setToolTip("Activez cette option pour ne pas inclure les fichiers MXF lors de l’importation.")
    mxf_checkbox.stateChanged.connect(lambda state: save_params({"ignore_mxf": bool(state)}))
    layout.addWidget(mxf_checkbox)

    # --- Add Slack and Discord settings UI ---
    slack_enabled = current_params.get("slack_active", False)
    slack_hook = current_params.get("slack_hook", "")

    discord_enabled = current_params.get("discord_active", False)
    discord_hook = current_params.get("discord_hook", "")

    slack_checkbox = QtWidgets.QCheckBox("Send Slack message at end of job")
    slack_checkbox.setChecked(slack_enabled)
    slack_checkbox.stateChanged.connect(lambda state: save_params({"slack_active": bool(state)}))

    slack_input = QtWidgets.QLineEdit()
    slack_input.setPlaceholderText("Slack webhook URL")
    slack_input.setText(slack_hook)
    slack_input.setReadOnly(slack_locked)
    slack_input.textChanged.connect(lambda text: save_params({"slack_hook": text}))

    slack_lock = QtWidgets.QPushButton()
    slack_lock.setFixedWidth(10)
    slack_lock.setText("🔒" if slack_locked else "🔓")
    slack_lock.setStyleSheet("background-color : transparent; border:none;")

    def toggle_slack_lock(locked):
        slack_input.setReadOnly(locked)
        slack_lock.setText("🔒" if locked else "🔓")
        save_params({"slack_locked": locked})

    slack_lock.clicked.connect(lambda: toggle_slack_lock(not slack_input.isReadOnly()))

    discord_checkbox = QtWidgets.QCheckBox("Send Discord message at end of job")
    discord_checkbox.setChecked(discord_enabled)
    discord_checkbox.stateChanged.connect(lambda state: save_params({"discord_active": bool(state)}))

    discord_input = QtWidgets.QLineEdit()
    discord_input.setPlaceholderText("Discord webhook URL")
    discord_input.setText(discord_hook)
    discord_input.setReadOnly(discord_locked)
    discord_input.textChanged.connect(lambda text: save_params({"discord_hook": text}))

    discord_lock = QtWidgets.QPushButton()
    discord_lock.setFixedWidth(10)
    discord_lock.setText("🔒" if discord_locked else "🔓")
    discord_lock.setStyleSheet("background-color : transparent; border:none;")

    def toggle_discord_lock(locked):
        discord_input.setReadOnly(locked)
        discord_lock.setText("🔒" if locked else "🔓")
        save_params({"discord_locked": locked})

    discord_lock.clicked.connect(lambda: toggle_discord_lock(not discord_input.isReadOnly()))

    slack_layout = QtWidgets.QHBoxLayout()
    slack_layout.addWidget(slack_input)
    slack_layout.addWidget(slack_lock)

    discord_layout = QtWidgets.QHBoxLayout()
    discord_layout.addWidget(discord_input)
    discord_layout.addWidget(discord_lock)

    layout.addWidget(slack_checkbox)
    layout.addLayout(slack_layout)
    layout.addWidget(discord_checkbox)
    layout.addLayout(discord_layout)
    # --- End Slack and Discord settings UI ---

    # Disable export options if renaming is active
    toggle_export_options(rename_checkbox.isChecked())

    close_button = QtWidgets.QPushButton("Close")
    close_button.clicked.connect(dialog.accept)
    layout.addWidget(close_button)

    # Wrap layout in a rounded container
    container = QtWidgets.QFrame()
    container.setObjectName("param_container")
    container.setLayout(layout)
    container.setStyleSheet("""
        #param_container {
            background-color: rgb(60,60,60);
            border-radius: 12px;
            padding: 15px;
        }
    """)
    outer_layout = QtWidgets.QVBoxLayout(dialog)
    outer_layout.setContentsMargins(5, 5, 5, 5)
    outer_layout.addWidget(container)

    dialog.setLayout(outer_layout)

    # Make dialog movable
    def mousePressEvent(event):
        if event.button() == QtCore.Qt.LeftButton:
            dialog.drag_position = event.globalPosition().toPoint() - dialog.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(event):
        if event.buttons() == QtCore.Qt.LeftButton:
            dialog.move(event.globalPosition().toPoint() - dialog.drag_position)
            event.accept()

    dialog.mousePressEvent = mousePressEvent
    dialog.mouseMoveEvent = mouseMoveEvent

    dialog.exec()

__all__ = ["resource_path", "get_params_path", "load_params", "save_params", "show"]
