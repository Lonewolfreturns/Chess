#!/usr/bin/env bash
# Install the APK on the running emulator, start it, and collect screenshots + logs in emu_out/.
set -x
APK=$(ls "$1"/*.apk | head -1)
mkdir -p emu_out
AAPT=$(ls "$ANDROID_HOME"/build-tools/*/aapt 2>/dev/null | tail -1)
PKG=$("$AAPT" dump badging "$APK" | sed -n "s/^package: name='\([^']*\)'.*/\1/p")
echo "package=$PKG" | tee emu_out/info.txt
ls -la "$APK" >> emu_out/info.txt

adb install -r "$APK" 2>&1 | tee -a emu_out/info.txt
adb logcat -c
adb shell monkey -p "$PKG" -c android.intent.category.LAUNCHER 1
sleep 60
adb exec-out screencap -p > emu_out/01_after_60s.png
sleep 40
adb exec-out screencap -p > emu_out/02_after_100s.png

# turn the phone sideways and back
adb shell settings put system accelerometer_rotation 0
adb shell settings put system user_rotation 1
sleep 15
adb exec-out screencap -p > emu_out/03_landscape.png
adb shell settings put system user_rotation 0
sleep 10
adb exec-out screencap -p > emu_out/04_portrait_again.png

# Back button at the main menu should leave the app running in the background, not crash it
(adb shell pidof "$PKG" || echo "NOT RUNNING") > emu_out/pid.txt
adb shell run-as "$PKG" cat files/error.log > emu_out/error.log 2>&1 || true
adb shell run-as "$PKG" ls -la files > emu_out/files.txt 2>&1 || true
adb logcat -d > emu_out/logcat.txt
grep -iE "python|qt|traceback|error|fatal|WizardWar" emu_out/logcat.txt | tail -300 > emu_out/logcat_filtered.txt || true
exit 0
