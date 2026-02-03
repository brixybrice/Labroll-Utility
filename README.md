# Labroll Utility

**Labroll Utility** is a macOS application designed for audiovisual and DIT workflows, built to **reliably rename, organize, and prepare video footage** in a consistent and reproducible way, especially in multi‑camera contexts (GoPro, cinema cameras, drones, etc.).

The application is developed in **Python 3.10 / PySide6** and distributed as a native macOS application using **PyInstaller**.

---

![screen capture](/README/labrollUtility2.0.png)
---

## ✨ Key Features

- Structured video file renaming
- Labroll / camroll management
- Reliable clip ordering (GoPro chapters, metadata, intelligent fallback)
- *Rename only* or *Copy + Rename* modes
- Real‑time progress bar
- Clean and immediate cancellation handling
- Native macOS user interface
- Apple Silicon (arm64) support

---

## 🖥️ Supported Platforms

- macOS 26 (Tahoe) and later
- Apple Silicon (arm64)

---

## 🧰 Technology Stack

- **Python** 3.10
- **PySide6** (Qt for Python)
- **PyInstaller**
- **hachoir** (video metadata extraction)
- Shell scripts for build and packaging

---

## 📁 Project Structure

```
Labroll-Utility/
├── labrollUtility/
│   └── src/
│       └── main/
│           ├── python/
│           │   ├── main.py
│           │   └── package/
│           │       ├── main_window.py
│           │       └── utils/
│           │           └── assets/
│           └── LabrollUtility.spec
├── version.plist
├── freeze.sh
└── README.md
```

---

## 🚀 Run in Development Mode

```bash
python labrollUtility/src/main/python/main.py
```

---

## 📦 Build the macOS Application

### Build the `.app`

```bash
./src/main/freeze.sh
```

The build process **exclusively uses** the following spec file:

```
src/main/LabrollUtility.spec
```

Result:

```
dist/
├── LabrollUtility.app
└── LabrollUtility-X.Y.Z.dmg
```

---

## 🔢 Version Management

The application version is defined **once** in:

```
version.plist
```

Keys used:
- `CFBundleShortVersionString`
- `CFBundleVersion`

This version is:
- displayed in Finder
- embedded in the macOS application bundle
- automatically reused for the DMG filename

---

## 🔁 Reverse JSON

Labroll Utility supports a **Reverse JSON** workflow.

This feature allows the application to:
- read a previously generated JSON file
- reconstruct the original clip order and naming logic
- reapply or verify renaming decisions

This is especially useful for:
- auditing a past operation
- rebuilding a labroll after partial data loss
- validating consistency between source media and delivered files

The Reverse JSON mechanism is designed as a safety and traceability layer, ensuring that every renaming operation can be understood and reproduced after the fact.


## 🎨 macOS Icon (Liquid Glass)

Starting with macOS 26, Apple enforces the **Liquid Glass** visual style.

The provided application icon complies with the new requirements:
- solid background
- no transparency
- consistent rendering in Finder, Dock, and Launchpad

---

## ⚠️ Important Notes

- Only **one** `.spec` file is used (`LabrollUtility.spec`)
- Never run PyInstaller directly on `main.py`
- All `.spec` paths are relative to `src/main/`

---

## 🛠️ Python Dependencies

```bash
pip install PySide6 pyinstaller hachoir
```

---

## 📄 License

This project is **open source** and distributed under the **MIT License**.

You are free to:
- use the software for personal or commercial purposes
- modify the source code
- redistribute the project

Provided that the original copyright notice and the MIT license are preserved.

---

## 👤 Author

Developed by Brix @**Be4Post**  
Workflow tools for post‑production and immersive media.
