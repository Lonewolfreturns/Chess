Android build files.

  workflows/android.yml     GitHub runs this from  .github/workflows/android.yml  at the top of the
                            repository (next to the original main.py). Keep that file the same as
                            this one.
  scripts/build_apk.sh      Does the actual build. The workflow calls it; you can also run it
                            yourself on Linux/WSL from the mobile_app folder:
                                bash github/scripts/build_apk.sh aarch64
  scripts/emulator_check.sh Starts the built app on an Android emulator and saves screenshots/logs.
