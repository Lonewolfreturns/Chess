[app]

# Name shown under the app icon (letters only: it is also used for the Android package name)
title = WizardWarChess

# Project root directory. Default: the parent directory of input_file
project_dir =

# Entry point (must be main.py for Android)
input_file = main.py

# Directory where the .apk is written
exec_directory =

project_file =

# Application icon
icon = build_assets/icon.png

[python]

# Buildozer: for deploying Android applications
android_packages = buildozer==1.6.0,cython==0.29.33

[qt]

# Found automatically: scene3d/qml/*.qml
qml_files =

excluded_qml_plugins =

# Qt libraries used. Android must load Core first; the deploy tool ignores the order given here
# (it re-detects the list), so github/scripts/build_apk.sh patches the tool to always put Core first.
modules = Core,Gui,Network,OpenGL,Concurrent,Qml,Quick,Quick3D,Multimedia,Widgets,QuickWidgets

plugins =

[android]

# Downloaded by the GitHub workflow (or passed with --wheel-pyside / --wheel-shiboken)
wheel_pyside =

wheel_shiboken =

# Qt plugins copied into the app: the Android window plugin and Android's own media player for
# sound and music (the FFmpeg one needs libraries Qt's loader can't find on Android)
plugins = platforms_qtforandroid,multimedia_androidmediaplugin

[buildozer]

# debug = .apk you can install directly; release = .aab for the Play Store
mode = debug

recipe_dir =

jars_dir =

# Empty = use the SDK/NDK downloaded into ~/.pyside6_android_deploy
ndk_path =

sdk_path =

# Plugin libraries loaded when the app starts (no FFmpeg: see [android] plugins above)
local_libs = plugins_platforms_qtforandroid,plugins_multimedia_androidmediaplugin

# aarch64 = phones; x86_64 = the Android emulator
arch =
