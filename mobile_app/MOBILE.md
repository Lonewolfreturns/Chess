# Wizard War Chess on phones

The game runs on Android (and, later, iPhone) from the same code as the Windows version. It uses
**Qt for Python (PySide6)**, the official Qt library, because it can package Python apps for phones.

## Get it on your Android phone

1. Open the repository on GitHub → **Actions** → **Android build** → the latest run.
2. Download the artifact **WizardWarChess-aarch64-apk** (a .zip) and unzip it; inside is an `.apk` file.
3. Copy the `.apk` to your phone (USB, Google Drive, email…) and tap it.
   Android asks you to allow installing apps from that source the first time; allow it.

The app isn't from the Play Store, so Google Play Protect may show a warning. Choose
*Install anyway*. This is normal for apps you build yourself.

A new APK is built automatically every time you push to the `mobile-app` branch. You can also start
a build by hand: **Actions → Android build → Run workflow**.

## What's different on a phone

| Desktop | Phone |
| --- | --- |
| Menu bar | **☰** button (top left) opens a slide-out menu with everything |
| Camera buttons under the board | **🎥** button (top right): Light / Shadow / Top / Side views, slow orbit |
| Mouse wheel / drag to orbit | **Pinch** to zoom, drag on empty space or with **two fingers** to orbit |
| Battle buttons in the side panel | **Hint · Undo · Redo · Flip** under the board; Resign, Draw, New battle in ☰ |
| Save / Load PGN files | **Copy game** / **Paste game** (PGN) through the clipboard |
| Esc | Phone **Back** button: closes menus, then returns to the main menu |
| Stockfish | Not available (phones can't run a separate engine program) |
| Your music folder | Music is only played from the app's own `music` folder (see below); otherwise the built-in theme plays |

The layout adapts when you turn the phone: board on top when upright, board on the left when sideways.
Bloom glow and anti-aliasing start switched off on phones to save battery. Turn them on in
**☰ → Settings → Graphics** if your phone handles it.

Settings, rank, XP and puzzle progress are stored on the phone and kept between launches.

## Try the phone layout on a PC

```
pip install -r requirements.txt
python main.py --mobile                    # phone held upright (390 x 844)
python main.py --mobile --phone 844x390    # phone held sideways
```

The preview keeps its own settings, separate from your normal desktop settings.

## Building the APK yourself (instead of GitHub)

Building needs Linux or macOS. On Windows, use WSL (Ubuntu). From this folder:

```
sudo apt install -y build-essential git zip unzip autoconf automake libtool libtool-bin libltdl-dev \
    pkg-config cmake lld zlib1g-dev libncurses-dev libffi-dev libssl-dev openjdk-17-jdk
python3.11 -m venv ~/wwc-venv && source ~/wwc-venv/bin/activate      # keep the venv outside the project
pip install "PySide6==6.12.0" jinja2 pkginfo tqdm "packaging==24.1" "buildozer==1.6.0" "cython==0.29.33"

# Android SDK + NDK (one time, about 3 GB)
git clone --depth 1 --branch 6.12.0 https://github.com/qtproject/pyside-pyside-setup.git ~/pyside-setup
python ~/pyside-setup/tools/cross_compile_android/main.py --download-only --skip-update --auto-accept-license --plat-name aarch64

# PySide6 for Android (phone = aarch64)
#   https://download.qt.io/official_releases/QtForPython/pyside6/   pyside6-6.12.0-6.12.0-cp310-abi3-android_aarch64.whl
#   https://download.qt.io/official_releases/QtForPython/shiboken6/ shiboken6-6.12.0-...-android_aarch64.whl
pyside6-android-deploy -f --wheel-pyside <pyside6 wheel> --wheel-shiboken <shiboken6 wheel>
```

The first build takes 20–40 minutes; later builds are much faster. The `.apk` appears in this folder.

## Publishing on the Google Play Store (later)

Set `mode = release` in `pysidedeploy.spec` to get an `.aab` file instead of an `.apk`. You'll also
need a Google Play developer account (one-time fee) and an app signing key. Only include music
in a published app if you own the rights to it.

## iPhone

Qt for Python 6.12 can also build iPhone apps (`pyside6-ios-deploy`). That needs a Mac with Xcode, and
an Apple developer account to install the app on a phone. The game code is already ready for it:
the phone layout, touch controls and file locations all work the same on iOS.

## Music on a phone

The built-in synthesized music always works. To use your own soundtrack, the MP3/OGG files must be
inside the app. Put them in a `music` folder next to `main.py` (with optional `menu`, `battle`, `learn`,
`victory`, `defeat` sub-folders), and add `mp3,ogg` to the file types the build includes
(`source.include_exts` in the generated `buildozer.spec`). Keep your own copyrighted tracks out of anything
you share.
