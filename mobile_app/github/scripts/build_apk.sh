#!/usr/bin/env bash
# Builds the Android APK. Run from the mobile_app folder on Linux (GitHub Actions or WSL):
#     bash github/scripts/build_apk.sh aarch64      (phones)
#     bash github/scripts/build_apk.sh x86_64       (Android emulator)
# Result: apk_out/WizardWarChess-<arch>.apk
set -euo pipefail
ARCH="${1:-aarch64}"
PYSIDE_VERSION="${PYSIDE_VERSION:-6.12.0}"
CACHE="$HOME/.pyside6_android_deploy"
SDK="$CACHE/android-sdk"
echo "== Building WizardWarChess for $ARCH with PySide6 $PYSIDE_VERSION"

echo "== System packages for python-for-android"
if command -v apt-get >/dev/null && [ -n "${CI:-}" ]; then
  sudo apt-get update -qq
  sudo apt-get install -y -qq --no-install-recommends build-essential ccache git zip unzip patch \
    autoconf automake libtool libtool-bin libltdl-dev pkg-config cmake lld \
    zlib1g-dev libncurses-dev libffi-dev libssl-dev libsqlite3-dev libbz2-dev liblzma-dev
fi

echo "== Qt for Python (host) and the deploy tool"
python -m pip install -q --upgrade pip
python -m pip install -q "PySide6==${PYSIDE_VERSION}" jinja2 pkginfo tqdm "packaging==24.1" markupsafe \
  "buildozer==1.6.0" "cython==0.29.33" setuptools wheel

echo "== Patching the deploy tool: load Qt Core first on Android"
# pyside6-android-deploy 6.12 rebuilds the Qt module list as an unordered set (it ignores the
# order in pysidedeploy.spec). Android loads the libraries in that order, and if e.g. Quick
# starts before Core the app crashes at launch. Put the modules in dependency order instead.
python - <<'PY'
import pathlib
import PySide6
p = pathlib.Path(PySide6.__file__).parent / "scripts" / "deploy_lib" / "android" / "android_config.py"
s = p.read_text()
old = "self.modules = list(set(modls))"
order = ["Core", "Gui", "Network", "OpenGL", "Concurrent", "Qml", "QmlModels", "QmlMeta", "QmlWorkerScript",
         "Quick", "QuickShapes", "Quick3DUtils", "Quick3DRuntimeRender", "Quick3D", "Multimedia",
         "Widgets", "QuickWidgets"]
new = ("self.modules = sorted(dict.fromkeys(modls), key=lambda m: _WWC_ORDER.index(m) "
       "if m in _WWC_ORDER else len(_WWC_ORDER))")
if "_WWC_ORDER" in s:
    print("already patched")
elif old in s and "class AndroidConfig" in s:
    s = s.replace(old, new).replace("class AndroidConfig", f"_WWC_ORDER = {order!r}\n\n\nclass AndroidConfig", 1)
    p.write_text(s)
    print("patched", p)
else:
    raise SystemExit("::error::could not patch the module order in " + str(p))

# Let the app rotate (buildozer's default locks it to portrait).
b = p.parent / "buildozer.py"
t = b.read_text()
anchor = 'self.set_value("app", "title", pysidedeploy_config.title)'
line = ('\n        self.set_value("app", "orientation", "portrait, landscape, portrait-reverse, '
        'landscape-reverse", raise_warning=False)')
if "landscape-reverse" in t:
    print("orientation already patched")
elif anchor in t:
    t = t.replace(anchor, anchor + line, 1)
    b.write_text(t)
    print("patched orientation in", b)
else:
    print("::warning::could not set the screen orientation; the app stays portrait-only")

# Package music files too (by default only .py, images, .qml and .js go into the app).
old_ext = 'include_exts = f"{include_exts},qml,js"'
if "qml,js,mp3" in t:
    print("audio extensions already patched")
elif old_ext in t:
    b.write_text(t.replace(old_ext, 'include_exts = f"{include_exts},qml,js,mp3,ogg,wav,m4a"', 1))
    print("patched packaged file types (music)")
else:
    print("::warning::could not add music file types; music will not be packaged")
PY

echo "== Android SDK and NDK"
if [ ! -d "$SDK/platform-tools" ] || ! ls -d "$CACHE"/android-ndk/android-ndk-r* >/dev/null 2>&1; then
  rm -rf /tmp/pyside-setup
  git clone -q --depth 1 --branch "${PYSIDE_VERSION}" https://github.com/qtproject/pyside-pyside-setup.git /tmp/pyside-setup
  (cd /tmp/pyside-setup && python tools/cross_compile_android/main.py --download-only --skip-update \
     --auto-accept-license --plat-name "$ARCH")
fi
yes 2>/dev/null | "$SDK/cmdline-tools/bin/sdkmanager" --sdk_root="$SDK" --licenses >/dev/null 2>&1 || true

echo "== PySide6 wheels for Android ($ARCH)"
mkdir -p "$HOME/wheels"
base=https://download.qt.io/official_releases/QtForPython
v="${PYSIDE_VERSION//./\\.}"
for pkg in pyside6 shiboken6; do
  if ! ls "$HOME"/wheels/"$pkg"-*android_"$ARCH".whl >/dev/null 2>&1; then
    name=$(curl -fsSL "$base/$pkg/" | grep -oiE "${pkg}-${v}-${v}-[a-z0-9_-]+-android_${ARCH}\.whl" | head -1 || true)
    if [ -z "$name" ]; then echo "::error::No $pkg $PYSIDE_VERSION wheel for android_$ARCH at $base/$pkg/"; exit 1; fi
    echo "$pkg -> $name"
    curl -fsSL --retry 3 -o "$HOME/wheels/$name" "$base/$pkg/$name"
  fi
done
ls -la "$HOME/wheels"
WHEEL_PYSIDE=$(ls "$HOME"/wheels/*yside6-*android_"$ARCH".whl | head -1)
WHEEL_SHIBOKEN=$(ls "$HOME"/wheels/shiboken6-*android_"$ARCH".whl | head -1)

echo "== Bundling the soundtrack"
# Music lives in the repo's dist/music (next to the Windows build). Copy it into the app,
# re-encoded at 112 kbps: plenty for phone speakers and headphones, about a third of the size.
rm -rf music
MUSIC_SRC="${MUSIC_SRC:-../dist/music}"
if [ ! -d "$MUSIC_SRC" ] && [ -n "${CI:-}" ]; then
  git -C .. sparse-checkout add dist/music >/dev/null 2>&1 || true     # GitHub only checked out mobile_app/
fi
if [ -d "$MUSIC_SRC" ]; then
  mkdir -p music
  if ! command -v ffmpeg >/dev/null && [ -n "${CI:-}" ]; then sudo apt-get install -y -qq ffmpeg >/dev/null || true; fi
  find "$MUSIC_SRC" -type f \( -iname '*.mp3' -o -iname '*.ogg' -o -iname '*.wav' -o -iname '*.m4a' -o -iname '*.flac' \) -print0 |
  while IFS= read -r -d '' f; do
    rel="${f#"$MUSIC_SRC"/}"
    out="music/${rel%.*}.mp3"
    mkdir -p "$(dirname "$out")"
    if command -v ffmpeg >/dev/null && ffmpeg -nostdin -loglevel error -y -i "$f" -vn -ac 2 -ar 44100 -b:a 112k "$out"; then
      :
    else
      cp "$f" "music/$rel"
    fi
  done
  echo "music bundled: $(find music -type f | wc -l) tracks, $(du -sh music | cut -f1)"
else
  echo "no music folder found at $MUSIC_SRC - the game will use its built-in theme"
fi

echo "== Building the APK (the first build takes a while)"
rm -rf dist build buildozer.spec .buildozer deployment apk_out
pyside6-android-deploy -f -v --keep-deployment-files \
  --wheel-pyside "$WHEEL_PYSIDE" --wheel-shiboken "$WHEEL_SHIBOKEN" \
  --extra-ignore-dirs tests,build_assets,chess,github

echo "== Generated build settings"
grep -o -- "--qt-libs=[^ ]*" deployment/buildozer.spec buildozer.spec 2>/dev/null | head -1 || true
cat pysidedeploy.spec || true
for f in buildozer.spec deployment/buildozer.spec; do
  [ -f "$f" ] && grep -E "^(requirements|android\.|p4a\.|source\.)" "$f" || true
done

# the deploy tool reports build errors but still exits with success, so look for the APK
APK=$(find . -maxdepth 1 -name "*.apk" | head -1)
[ -n "$APK" ] || APK=$(find . -name "*.apk" -path "*/bin/*" | head -1)
if [ -z "$APK" ]; then echo "::error::No APK was produced - see the build output above"; exit 1; fi
mkdir -p apk_out
cp "$APK" "apk_out/WizardWarChess-$ARCH.apk"
ls -la apk_out
