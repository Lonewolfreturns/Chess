# python-chess (bundled copy)

This folder is an unmodified copy of [python-chess](https://github.com/niklasf/python-chess) 1.11.2,
licensed under the GNU GPL v3 or later (see LICENSE.txt).

It is bundled so the Android and iOS builds work without installing extra packages: the phone
build tools only package the project folder plus PySide6. On a PC, `pip install chess` works too;
this copy simply takes priority when you run `python main.py` from this folder.
