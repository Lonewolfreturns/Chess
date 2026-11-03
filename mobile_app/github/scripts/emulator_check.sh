#!/usr/bin/env bash
# Install the APK on the running emulator, start it, and collect screenshots + logs in emu_out/.
# A summary (is it running? Python errors? crash lines) is also printed to the job log.
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
check() {   # $1 = label: is the app still running?
  if adb shell pidof "$PKG" >/dev/null 2>&1; then echo "$1: RUNNING"; else echo "$1: NOT RUNNING"; fi | tee -a emu_out/status.txt
}
sleep 20; check "after 20s";  adb exec-out screencap -p > emu_out/01_after_20s.png
sleep 40; check "after 60s";  adb exec-out screencap -p > emu_out/02_after_60s.png
sleep 40; check "after 100s"; adb exec-out screencap -p > emu_out/03_after_100s.png

# open the 2D board (the "2D" button, top right), then back to 3D
tap() { adb shell input tap "$1" "$2"; }
W=$(adb shell wm size | sed -n 's/.*: \([0-9]*\)x\([0-9]*\).*/\1/p' | tail -1); W=${W:-1080}
H=$(adb shell wm size | sed -n 's/.*: \([0-9]*\)x\([0-9]*\).*/\2/p' | tail -1); H=${H:-2400}
tap $((W * 77 / 100)) $((H * 8 / 100)); sleep 25
check "2D board"; adb exec-out screencap -p > emu_out/06_board_2d.png
tap $((W * 77 / 100)) $((H * 8 / 100)); sleep 15
check "back to 3D"; adb exec-out screencap -p > emu_out/07_back_to_3d.png
# start a battle: "Battle AI" on the main menu, then Enter accepts the New Battle dialog
tap $((W * 27 / 100)) $((H * 72 / 100)); sleep 8
adb exec-out screencap -p > emu_out/08_new_battle_dialog.png
adb shell input keyevent 66; sleep 25
check "battle"; adb exec-out screencap -p > emu_out/09_battle.png

# turn the phone sideways and back
adb shell settings put system accelerometer_rotation 0
adb shell settings put system user_rotation 1
sleep 15; check "landscape"; adb exec-out screencap -p > emu_out/04_landscape.png
adb shell settings put system user_rotation 0
sleep 10; check "portrait again"; adb exec-out screencap -p > emu_out/05_portrait_again.png

adb shell run-as "$PKG" cat files/error.log > emu_out/error.log 2>&1 || true
adb shell run-as "$PKG" ls -la files > emu_out/files.txt 2>&1 || true
adb logcat -d > emu_out/logcat.txt
set +x
echo "================ SUMMARY ================"
cat emu_out/status.txt
echo "---------------- error.log (Python errors saved by the game) ----------------"
head -c 6000 emu_out/error.log
echo
echo "---------------- crash / Python lines from logcat ----------------"
grep -E "FATAL|AndroidRuntime|Traceback|Error|Exception|python|libc *:|DEBUG *:|qt\.|Qt |QML|qml|ActivityManager.*(Process|died|$PKG)" emu_out/logcat.txt \
  | grep -vE "ConnectivityService|GoogleApiManager|chatty|Finsky|gms" | tail -250
echo "========================================="
exit 0
