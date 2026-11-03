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

echo "== Building the APK (the first build takes a while)"
rm -rf dist build buildozer.spec .buildozer deployment apk_out
pyside6-android-deploy -f -v --keep-deployment-files \
  --wheel-pyside "$WHEEL_PYSIDE" --wheel-shiboken "$WHEEL_SHIBOKEN" \
  --extra-ignore-dirs tests,build_assets,chess,github

echo "== Generated build settings"
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
