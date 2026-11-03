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

# Qt libraries, in the order Android loads them. Core MUST come first: other Qt libraries need it
# to be set up when they start (if the deploy tool picks the order itself it can put Quick before
# Core, and the app crashes on launch). Each one comes after the libraries it depends on.
modules = Core,Gui,Network,OpenGL,Concurrent,Qml,Quick,Quick3D,Multimedia,Widgets,QuickWidgets

plugins =

[android]

# Downloaded by the GitHub workflow (or passed with --wheel-pyside / --wheel-shiboken)
wheel_pyside =

wheel_shiboken =

plugins =

[buildozer]

# debug = .apk you can install directly; release = .aab for the Play Store
mode = debug

recipe_dir =

jars_dir =

# Empty = use the SDK/NDK downloaded into ~/.pyside6_android_deploy
ndk_path =

sdk_path =

local_libs =

# aarch64 = phones; x86_64 = the Android emulator
arch =
