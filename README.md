# Wizard War Chess

A medieval-fantasy **3D battle chess** game in Python + PyQt6 (Qt Quick 3D), with a classic 2D
board as an alternative view, a built-in AI, a move-by-move coach, lessons and puzzles.

## Play

- **Ready-made game:** `dist/WizardWarChess.exe` (single file, ~60 MB). No install needed.
  For faster start-up, use `dist/WizardWarChess/WizardWarChess.exe` (folder version).
- **From source:**
  ```
  pip install -r requirements.txt
  python main.py
  ```
- **Rebuild the .exe:** `python build_exe.py` (single file) or `python build_exe.py --onedir`.

## Features

**3D battlefield**
- Third-person camera: drag to orbit, mouse wheel to zoom, buttons for Light side / Shadow side / Top /
  Side / slow cinematic orbit. In two-player games the camera swings to the side to move.
- Four exotic locations: **Volcanic Summit** (peak ringed by erupting volcanoes), **Edge of the Void**
  (floating island, orbiting asteroids, crystals), **Frozen Peak** (snow, ice crystals, aurora) and
  **Sky Temple** (marble columns above a sea of clouds).
- Medieval pieces modelled in code. Each army has its own materials and glowing gems:
  - Pawn: foot knight with helm, shield and sword
  - Knight: armoured war horse
  - Bishop: battle-mage with mitre and glowing staff
  - Rook: war elephant (*Haathi*) carrying a castle
  - Queen and King: crowned royals with capes
- Three army themes: Light vs Shadow, Golden Crown vs Iron Horde, Frost vs Flame.
- Every piece moves in its own style, and fights with its own magic:
  - Pawn: sword lunge
  - Knight: cavalry charge
  - Bishop: staff beam
  - Rook: elephant's cannon
  - Queen: lightning storm
  - King: royal shockwave
- **Check:** a red runic circle and warning light appear under the King.
- **Checkmate cinematic:** the board darkens, the camera swoops in, lightning strikes, the losing army
  freezes to ice, and "CHECKMATE / VICTORY" appears.
- Bloom glow, shadows, fog, sky lighting and 3D particles (sparks, fire, smoke, debris, snow, embers).

**Chess**
- All rules, via python-chess: castling, en passant, promotion (piece picker), check, checkmate,
  stalemate, repetition, the 50-move rule and insufficient material.
- **Game modes:** vs AI (5 levels, from Apprentice to Grand Wizard), two players, AI vs AI, and a demo
  battle that plays behind the main menu.
- **Clocks:** bullet, blitz or rapid time controls.
- **Move history:** undo/redo, a clickable move list with ←/→ browsing, and opening names.
- **Files:** save/load PGN, copy FEN, set up a position from FEN.
- **Optional Stockfish:** put `stockfish.exe` next to the game (or in an `engines/` folder) and a
  "Stockfish" level appears.

**Learning**
- **Coach (Merlin):** grades every move (Brilliant / Best / Excellent / Good / Inaccuracy / Mistake /
  Blunder) and explains why: hanging pieces, forks, missed mates, development, centre control. It also
  suggests a better move.
- **Hints:** the best move shown as a glowing path, with an explanation and the expected line.
- **Threat warnings:** red rings mark your pieces in danger, green rings mark enemy pieces you can win,
  and there's a warning when mate is threatened.
- **Evaluation bar and accuracy:** who's winning and by how much, plus a post-game accuracy score.
- **Training Academy:** 13 interactive lessons (24 steps) covering how each piece moves, special
  moves, check, mating patterns, forks, pins, skewers and opening principles, with ★ ratings.
- **Spell Puzzles:** 20 checked puzzles (mate in 1, mate in 2, winning material).
- **Rank and XP:** progress from Squire to Legend of the Realm.

**Sound and music**
- All sound effects are synthesized in code.
- **Your own soundtrack:** the game plays MP3/OGG/WAV files from a `music` folder next to
  `WizardWarChess.exe` (currently `dist/music`), crossfading between them.
  - **Moods:** calm themes on the menu, battle tracks during games, gentle tracks in lessons and
    puzzles, and a victory or defeat track when a game ends.
  - **How tracks are sorted:** by words in the file name (for example "victory", "eternal",
    "send off", "hope"). Anything else counts as battle music. To set a track's mood yourself, put it
    in a subfolder named `menu`, `battle`, `learn`, `victory` or `defeat`.
  - **Controls:** Sound → Next track (`Ctrl+M`), Choose music folder…, Open music folder.
  - **No music folder?** The game falls back to its own synthesized ambient theme.
- The music is kept outside the .exe so you can add or swap songs, and so you don't redistribute
  copyrighted soundtracks if you share the game. Only share the `music` folder if you own the rights
  to those tracks.

**After a battle:** a "Battle Over" panel shows your accuracy, XP and rank, with **Rematch / Play again,
New battle, Review game** (replay every move with the coach's grades) and **Main menu**.

## Controls

| Action | How |
| --- | --- |
| Move | Click a piece, then a glowing square, or drag it |
| Orbit / zoom (3D) | Drag on empty space or right-drag / mouse wheel |
| Mark squares | Right-click (2D: right-drag draws arrows) |
| Hint / Undo / Redo | `H` / `Ctrl+Z` / `Ctrl+Y` |
| Switch side / 2D-3D | `F` / `Ctrl+D` |
| Browse moves | `←` `→` |
| Fullscreen | `F11` |

## Project layout

```
main.py              entry point (exception logging, --selftest for builds)
build_exe.py         PyInstaller build (trims unused Qt modules)
game/                rules, AI engine, game state/PGN, coach, openings, lessons, puzzles
scene3d/             3D: mesh toolkit, piece models, terrain, textures, locations,
                     QQuick3DGeometry bridge, Board3D view, battle choreography, qml/
ui/                  main window, menus/dialogs, widgets, theme, 2D board scene
animations/          coroutine animator + 2D movement/capture/cinematics
effects/             2D particle engine + magic_effect(type, position, duration, intensity)
audio/               synthesized sound effects and music
assets/              optional custom art/sounds (see assets/README.txt)
tests/               validate_content.py: proves every lesson and puzzle is solvable
```

Settings, progress and stats are stored per user (Windows registry, via QSettings). Generated
textures and sounds are cached in `%LOCALAPPDATA%\WizardWarChess`. Errors are logged to
`%LOCALAPPDATA%\WizardWarChess\error.log`.
