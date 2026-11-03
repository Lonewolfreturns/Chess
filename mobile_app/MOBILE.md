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

A new APK is built automatically every time you push a change inside `mobile_app/` to `main`. You can
also start a build by hand: **Actions → Android build → Run workflow**. The build settings live in
`.github/workflows/android.yml` at the top of the repository (a copy is kept in `mobile_app/github/`).

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

Building needs Linux or macOS. On Windows, use WSL (Ubuntu). From the `mobile_app` folder:

```
sudo apt install -y build-essential git zip unzip autoconf automake libtool libtool-bin libltdl-dev \
    pkg-config cmake lld zlib1g-dev libncurses-dev libffi-dev libssl-dev openjdk-17-jdk python3.11-venv
python3.11 -m venv ~/wwc-venv && source ~/wwc-venv/bin/activate      # keep the venv outside the project
bash github/scripts/build_apk.sh aarch64
```

This is the same script GitHub runs. It downloads the Android SDK/NDK (about 3 GB, once) and the
PySide6 Android wheels, then builds. The first build takes 20–40 minutes; the APK ends up in `apk_out/`.

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
