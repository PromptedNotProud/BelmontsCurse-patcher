Belmont Patcher v0.30.0
=======================
by PromptedNotProud (made with AI assistance)

Unofficial fan mod for Castlevania: Belmont's Curse on Steam (PC, Windows 10/11). Made for the
demo and updated for the full game.
Not affiliated with or endorsed by Konami. Use at your own risk.

What it does, in one sentence: the game keeps running exactly as it does now (same physics,
same controls, same timing), but it is drawn smoothly at your monitor's frame rate, looks
sharper, and has no freeze on the first line of each conversation. There is also an optional,
experimental 120 Hz input mode that makes Rose react faster to your inputs.


QUICK START
-----------
  1. Find the game folder. In Steam: Library > right-click the game > Manage > Browse local
     files. A folder opens that contains "Castlevania Belmont's Curse.exe".

  2. Copy the whole "Belmont Patcher" folder from this zip INTO that game folder, so you have:
         ...\Castlevania Belmont's Curse\Belmont Patcher\Install.bat

  3. Make sure the game is closed, then double-click Install.bat.

     The patcher is written in Python. If Python 3 is not on your PC, a black window tells you
     so and offers to install it for you: press any key and it downloads the official installer
     from python.org (about 27 MB), installs Python for your user account (no administrator
     rights needed) and continues. Close the window instead if you'd rather not.

  4. The settings window opens. Leave the options as they are (the defaults are the
     recommended ones) and click "Apply".

  5. Wait for the log in the window to end with "Done." The first install takes a few
     minutes: it downloads the Python package the patcher needs (UnityPy) and scans the
     game's asset files once for the menu text. Later runs take a few seconds.

  6. Start the game as usual from Steam. That's it.

You need an internet connection for step 3 and the first step 5 only.
To change an option later: close the game, open Install.bat again, change the option, click
Apply again. Your choices are remembered.


WHAT THE OPTIONS DO
-------------------
Image Quality
  - Improved Resolutions (on): the stock menu lists sizes that aren't what you get (for example
    "2560x1080" actually gives 1920x1080, because the game only draws 16:9). The list is now
    16:9 from 1280x720 to 7680x4320 (incl. 4K, 5K, 5.7K) plus the ultra-wide sizes 2560x1080,
    3440x1440 and 5120x1440. An entry only appears if your monitor (or NVIDIA DSR / AMD VSR)
    offers that mode, and every entry is the size you get. On a display above 4K the game now
    renders at its full size instead of stopping at 3840x2160 and being upscaled. The same step
    fills in an English menu text the game left empty: the Anti-Aliasing "None" option, which
    otherwise shows the French word "Aucun".
    Above 4K (DSR/VSR): set your Windows desktop to that resolution and use borderless
    fullscreen. Exclusive Fullscreen works too, but resets after alt-tab. To restore it, pick
    another resolution in the game menu, then yours again.
  - Ultra-Wide Rendering (off, experimental): the game only draws 16:9, so on an ultra-wide
    monitor it shows a 16:9 image with black bars at the sides, whatever you pick. With this
    option the three ultra-wide entries render at their full width: you see more of the level to
    the left and right and the interface stretches to the edges. The game was not designed for
    this, so the edges of some rooms may show things that were meant to stay off-screen. Try it,
    and untick it if you don't like the result. Needs Improved Resolutions.
  - TAA in the Anti-Aliasing Menu (on): the game ships Unity's temporal anti-aliasing but hides
    the menu entry. With this option the Video menu offers None, FXAA, SMAA and TAA; pick it there.
    TAA smooths edges and shimmer in motion much better than SMAA, but it can blur a little and
    leave faint trails behind fast effects.
  - SMAA High (on): SMAA quality High instead of Low.
  - Anti-Aliasing in Reflections: Off (stock), SMAA (default) or TAA (experimental) on the water
    and mirror reflections. Note: to anti-alias a reflection the game has to post-process it, which
    clamps its brightness to the range of the main image, so very bright reflected lights may look
    a touch dimmer than before. Choose Off if you prefer the stock look.

Graphics (all on by default)
  - Better Shadows: soft shadows, higher shadow resolution.
  - Shadows in Reflections: water and mirror reflections render shadows. The game has the setting
    but its own code switched it off again before drawing the reflection. Costs some GPU time.
  - Better Light Shafts: full resolution, 32 samples.
  - 16x Anisotropic Filtering: sharper textures seen at an angle.

Camera
  - Closer Camera (on): characters about 25% larger on screen. The zoom factor is adjustable. Boss
    arenas and the areas the game deliberately frames wider than normal (open vistas, wide rooms,
    where it zooms the camera out) keep the stock framing, so floors and enemies at the bottom of
    the screen stay in view; the camera blends between the two as you walk in and out. The same
    goes for the special cameras the game switches to at set moments (a door opening, a reveal):
    when they zoom out you get the game's own framing, when they zoom in the closer camera stays.
    The closer camera zooms in toward Rose rather than the centre of the screen, so she keeps
    the place on screen the game gives her and the floor under her stays in view.
  - F8 Switches to the Stock Camera in Game (on): press F8 to pull back to the game's own, wider
    framing when you need to see more of the room, and again for the closer camera. The camera
    eases over; a Windows sound confirms (the default sound for the stock camera, the "information" sound for the closer
    one).

Motion
  - Input Rate: "30 Hz (original, recommended)" or the experimental 120 Hz / 60 Hz input modes
    (see below). This is the rate the game runs at; change it here and click Apply.
  - Smooth Motion (on): the game simulates at 30 frames per second. The stock game already draws
    the player and enemies smoothly in between; this extends it to everything else: water wheels,
    moving and crumbling platforms, gates, saws, cutscene props, projectiles, animated doors,
    levers, chests, spikes, drawbridges, cutscene camera blends and characters walking in
    cutscenes. It applies in both modes.
  - Low Latency (off, experimental): one frame waits for the graphics card instead of Unity's
    default two, so what you press reaches the screen a little sooner. Measured inside the game
    it took about 2 ms off with 30 Hz input and 4 to 5 ms with 120 Hz input. It can cost a
    little frame rate when the graphics card is at its limit. NVIDIA's Low Latency Mode isn't
    needed with it: set to Ultra, it added lag in the same test.

Gameplay
  - Skip Startup Logos (on): the game boots straight to its title screen, without the company logos
    and startup notices. The setup screens shown the very first time you play (brightness, language,
    controls) still appear when they would.
  - Dialogue Preload (on): the first line of every conversation no longer freezes the game for a
    tenth of a second.
  - Font Preload (on): removes hitching in the game from font loading. The game's font list is
    prepared while the first room loads instead of during gameplay.

The "Install Python/Packages" button only installs the package listed above, without touching
the game. "Apply" does that too, so you normally never need it; it is there in case the package
download failed the first time. (Python itself is installed by Install.bat, before the window opens.)


THE EXPERIMENTAL 120 Hz INPUT MODE
----------------------------------
Off by default. Pick "120 Hz input, stock movement" under Input Rate (Motion) and click Apply.

What it changes: nothing about how the game plays. Every character and object still runs its
original 30 frames-per-second code, so jumps, lunges, dodges, hits and knockback are the original
ones (this has been verified move by move against the unmodified game). The only difference is
WHEN Rose's next frame starts while you are controlling her: on the next 1/120 s tick after you
press or release a button or move the stick, instead of waiting for the next 1/30 s step. That
takes up to 25 ms off the input lag (measured inside the game: from about 48 ms to 35 ms on
average, key press to Rose moving). The time gained is given back over the following frames, so
she never gets ahead of the rest of the game, and the rest of the game keeps its exact timing.

"60 Hz input" is the same thing with 1/60 s ticks (about half the benefit).

It is called experimental because it changes something deep in the game's update loop. It has
been tested through the whole demo and the full game uses the same code for everything the mode
touches, but if anything ever looks wrong, pick 30 Hz, click Apply, and you have the stock game
again.


UNINSTALL
---------
Open Install.bat and click "Restore to Original". Every changed file is restored from
the clean copies the patcher saved in "Belmont Patcher\stock" the first time it ran.
You can also use Steam: Properties > Installed Files > Verify integrity of game files.
Don't delete the "stock" folder while the mod is installed.
Python itself stays on your PC; remove it from Windows "Apps & features" if you don't want it.


AFTER A GAME UPDATE
-------------------
Steam replaces the patched files when the game updates. Open Install.bat and click Apply again:
the patcher sees the new original files, saves them as its new clean copies and patches those.
Every change is found by searching for the surrounding code, so most updates work without a new
version of the patcher. Anything it can't find is skipped and listed as "NOT FOUND" in the log;
the rest still works.


TROUBLESHOOTING
---------------
  - The automatic Python install failed (no internet, download blocked): install Python yourself
    from https://www.python.org/downloads/ - on the FIRST screen of its installer tick "Add
    python.exe to PATH" - then double-click Install.bat again.
  - "The settings window could not start": your Python is missing its "tcl/tk" component. Run
    the Python installer again, choose Modify, and tick "tcl/tk and IDLE". (Python installed by
    Install.bat always includes it.)
  - Package install failed / menu text skipped: check your internet connection and click
    "Install Python/Packages", then Apply again. The rest of the mod is already installed
    when this happens, except Improved Resolutions and TAA in the menu, which need the menu
    text: they stay off until it is updated (the log says so next to them).
  - "could not be written" next to a file in the log: Windows refused to replace the file
    (the game or Steam still had it open, or the antivirus was scanning it). Close the game and
    click Apply again; it only redoes the files it missed.
  - Antivirus warning: the patcher is a readable Python script that edits the game's own files.
    You can open belmont_patcher.py in a text editor to see exactly what it does. The Python
    installer it downloads is the official one from python.org.
  - Ultra-Wide Rendering shows something odd at the sides of a room: that is the game's level
    design meeting a width it never expected. Untick the option and click Apply.
  - Something looks wrong in game: untick the related option, click Apply, and tell the person
    who gave you this mod, with the log text from the window (also saved as install_log.txt in the Belmont Patcher folder).


WHAT CHANGED IN 0.30.0
----------------------
  - New option Low Latency (Motion, off by default, experimental): one frame waits for the
    graphics card instead of two, for a few milliseconds less input lag.


WHAT CHANGED IN 0.29.2
----------------------
  - F8 is now described as what it's for: pulling back to the game's wider view when you need to
    see more of the room.
  - When the menu text could not be updated (the Python package failed to install, a file was in
    use), the resolution menu showed the wrong names for the sizes it applied: on a 1440p monitor
    the highest entry read "1920x1080". Improved Resolutions now stays off until the menu text is
    in place, so the menu is always right; click Apply again once the cause is fixed.
  - The window's log is also saved as install_log.txt in the Belmont Patcher folder, for bug reports.
  - The settings window shows the note about resolutions above 4K under Improved Resolutions.


WHAT CHANGED IN 0.29.1
----------------------
  - Closer Camera: it zoomed in around the centre of the screen, and because the game frames Rose
    low, her feet and the floor could drop off the bottom in some rooms. It now zooms in toward Rose.
  - Note on resolutions above 4K (see Improved Resolutions).


WHAT CHANGED IN 0.29
--------------------
  - New Gameplay option Font Preload (on): removes hitching in the game from font loading.


WHAT CHANGED IN 0.28
--------------------
  - The Anti-Aliasing menu now offers TAA as its own 4th entry; "None" is back to meaning none.
  - New resolution list (720p to 8K plus the three ultra-wide sizes) and the experimental
    ultra-wide rendering option.
  - Anti-aliasing in reflections is a choice (Off / SMAA / TAA) instead of a switch.
  - The F9 live 30/120 Hz switch is gone; the Input Rate chosen in the window is simply the rate
    the game runs at. F8 (camera) stays.
  - The developer diagnostics (logs written next to the game) are gone from the release build.
  - The settings window is regrouped (Image Quality, Graphics, Camera, Motion, Gameplay) and its
    buttons renamed: Apply, Restore to Original, Install Python/Packages.


VERSION NUMBERS
---------------
Versions are MAJOR.MINOR.PATCH (semantic versioning). A new feature or option raises MINOR (0.28.0),
a release with fixes only raises PATCH (0.28.1). 1.0.0 will mark the first release considered
complete and stable. Older releases were numbered v20 to v27; v27 is 0.27.0, v26 is 0.26.0 and so on.


HOW IT WORKS (short version)
----------------------------
The patcher never ships any of the game's files. It edits your own copy:
  - GameAssembly.dll (the game's compiled code): small code changes, plus a new code section for
    the smoothing and the optional 120 Hz input scheduler.
  - globalgamemanagers / globalgamemanagers.assets: shadow resolution and texture filtering.
  - Asset bundles: the resolution names in the settings menu (all languages), the English "None"
    label, and the hidden TAA entry of the Anti-Aliasing menu made visible.
  Earlier versions (v15-v19) also added texture mipmaps. v20 removed them: the next Install puts
  those files back to their originals by itself.
Original copies are kept in the "stock" folder so everything can be undone.
Your choices are saved in belmont_settings.json next to the patcher.
