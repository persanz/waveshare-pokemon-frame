# PICODEX & Virtual Pokemon

Two offline Pokémon apps for the Waveshare RP2350-Touch-LCD-1.54, with 1,538 artwork entries on an SD card. The project includes firmware sources, compiled MicroPython modules, artwork archives, Spanish descriptions, preserved English descriptions, and the assets needed to reproduce the build.

## Printable quick guide

[Guía rápida en español · A4, dos caras](docs/guia/Guia-rapida-Pokemon-A4.pdf)
includes child-friendly instructions and six recreated screen images. Print at
100% on A4, double-sided with long-edge binding. Build source and image notes
are in [docs/guia/LEEME.md](docs/guia/LEEME.md).

## Startup and controls

A Pokémon logo and Poké Ball splash shows **Loading....** for five seconds, then opens the graphical **ELIGE TU MUNDO** menu. Tap Pikachu for **Virtual Pokemon** or the red Pokédex for **PICODEX**. The left hardware button selects Virtual Pokemon; the right selects PICODEX. Selecting an app performs a clean soft restart so it has enough memory for artwork. Restart the board to return to the menu.

Hold the left hardware button for 1.5 seconds to show the red Poké Ball goodbye screen and shut down on battery. USB can keep the board powered after the screen goes off.

### PICODEX

- Tap the left or right third of the screen, or use the hardware buttons, to browse in National Pokédex order. Alternate forms sit beside their base species and show the species' Pokédex number.
- Hold the centre of the artwork for 0.8 seconds to read its Spanish description in white on black. Tap to advance pages, then return to the artwork. Motion shuffle pauses while reading.
- Hold the right button to return to the first Pokémon.

### Virtual Pokemon

- Tap the artwork to pet your Pokémon, or use **COMIDA / CARICIA / JUGAR**.
- Food and happiness decrease while the board is powered. No offline elapsed time is assumed.
- The left hardware button feeds; the right plays.
- Movement brings a new random companion with fresh care meters. The current companion and meters save in `/companion.json` every five minutes and on encounters or shutdown.

### Motion in both apps

Gentle shakes trigger a random artwork entry other than the current one. The threshold is 2,200 raw acceleration-change units, with two consecutive samples over roughly 200 ms. After a change, the minimum interval is 1.5 seconds, and movement must settle for five samples (about half a second) before another shake can trigger. Continued shaking alone cannot cause repeated changes.

## Board and SD files

Firmware targets MicroPython 1.29, mpy format v6.3. Upload these files to the board's root:

```text
main.py
power_screen.mpy
charge_overlay.mpy
boot_menu.mpy
boot_splash.mpy
boot_splash.dat
menu_pikachu.dat
menu_pokedex.dat
companion_app.mpy
companion_state.mpy
frame_app.mpy
dex_description.mpy
shutdown_screen.mpy
sdcard.mpy
pokemon_order.bin
pokemon_dex.bin
pokemon_descriptions_es.bin
```

Keep the board's Waveshare `lcd.py`, `poweron_art.dat`, and existing hardware files. The preserved English `pokemon_descriptions.bin` can also remain on the board. The SD card must contain `/waveshare_pokemon_frame/pokemon_hd.dat` (mounted as `/sd` by the apps). Order and dex lookup files correspond to the bundled artwork archive; rebuild them if the archive changes.

Use `uv tool run mpremote connect list` to find the serial port, then upload with `uv tool run mpremote connect <port> fs cp <file> :<file>`. Close other serial applications first. A hardware reset clears a running watchdog before long transfers; after reconnecting, remain at the menu while transferring files.

The original standalone frame entry point is preserved as `frame_main.py`. Copy it to the board as `main.py` to boot directly into PICODEX. The previous clock app is preserved in `previous-clock-main.py` and the separate `pico-cuadrat-rellotge` project. Local snapshots of board files are in `device-backups/` and intentionally excluded from Git.

## Spanish descriptions and English originals

`pokemon_descriptions_es.json`, `.md` and `.bin` contain all 1,538 Spanish entries. The English `pokemon_descriptions.json`, `.md` and `.bin` remain unchanged. There are 890 entries using official matching-game-version Spanish text from PokeAPI, and 648 using reviewed local translations of the original English. Per-entry provenance is stored in the Spanish JSON, and review corrections are retained in `description-sources/translation-overrides-es.json`. Alternate artwork shares species descriptions where the English originals do.

Descriptions support Spanish accents, ñ, ü and inverted punctuation. Long descriptions paginate without dropping text. Rebuild and verify from the project directory:

```bash
python3 localize_descriptions.py
python3 build_descriptions.py --source pokemon_descriptions_es.json --output pokemon_descriptions_es.bin --encoding utf-8
python3 validate_spanish_descriptions.py
```

The localization script uses cached translations. For uncached entries it requires local Ollama with `qwen3-8b-nothink:latest`. PokeAPI CSV inputs are pinned by `description-sources/commit.txt`; English-original checksums are in `description-sources/english-original-sha256.json`.

## Build and verification

Compile each firmware `.py` module using MicroPython 1.29 mpy-cross, for example:

```bash
uv tool run --from mpy-cross mpy-cross frame_app.py
python3 -m unittest discover -s tests -v
python3 validate_spanish_descriptions.py
```

`main.py` stays as source on the board. Matching compiled modules are included for deployment.

The Spanish database and uploaded modules passed checksum verification. On-board testing successfully opened a description and returned to artwork; both apps have loaded artwork successfully. Motion logic was checked with simulated sustained shaking, calm and a fresh shake. Final sensitivity depends on physical handling.

## Artwork and splash sources

The artwork archive uses PokeAPI's high-resolution official artwork, converted to 240 × 240 RGB565. `build_sprites.py` builds the archive from a local artwork checkout with Pillow; its default inputs are `/tmp/pokemon-sprites/sprites/pokemon/other/official-artwork` and `/tmp/art_labels.json`. Images are alpha-cropped, fitted to a canvas, compressed with raw DEFLATE using a 1 KiB window, and indexed with Pokémon IDs and UTF-8 names. The prior 160 × 160 and sprite archives are preserved for recovery. Virtual Pokemon fits this artwork into a 152px square to leave room for care controls.

The boot splash combines downloaded Wikimedia logo and Poké Ball graphics with a custom background. Original assets, PNG preview and attribution are in `assets/splash/`; see [sources and licensing](assets/splash/SOURCES.md). Rebuild it with:

```bash
uv run --with pillow --with resvg-py python build_boot_splash.py
```

Pokémon artwork, names and trademarks belong to their respective owners.

## Charging overlay

After the five-second splash, a stable board power indication opens a black
screen with a large voltage-derived percentage inside a ring: red below 20%,
orange from 20–69%, green from 70%. The labels remain Spanish, without an
ESTIMADO label. Tap anywhere to restore the exact previous menu, artwork,
description page or companion framebuffer; that gesture is consumed. The
companion care clock pauses while the overlay is visible. Long-left shutdown
remains available and saves care state. An inactive indication for 700 ms also
closes the overlay. `/charge-screen.tmp` stores its framebuffer in internal
flash, avoiding a second 115,200-byte RAM allocation.

### Power signal and limitations

The [Waveshare schematic](https://files.waveshare.com/wiki/RP2350-Touch-LCD-1.54/RP2350-Touch-LCD-1.54.pdf)
routes ETA6098 BAT_STAT through Q4/R50/R51 to GPIO17; it does not expose a
separate VBUS-sense GPIO. The old board `charging.py` assumed active-low input.
A physical cable-cycle recording on this board on 2026-11-13 instead showed
GPIO17 high while USB was connected, low during unplug, and high on reconnect,
with battery readings around 4.03 V. The recorder sampled every 500 ms; its
116-sample CSV is in the ignored local
`device-backups/power-diagnostics/reconnect.csv`. Firmware now uses this measured
high-on-USB behaviour, without enabling an internal pull resistor.

The prompt requires 700 ms high, remains dismissed while high, and re-arms only
after 1,500 ms low. Dismissal carries across the menu's app soft restart. Both
apps keep the small monitor alive after dismissal to observe the low interval;
only the overlay and battery-reading code load on demand.

**This is a board-specific, experimentally verified heuristic, not a universal
VBUS detector.** GPIO17 behaviour during every ETA6098 charging/termination,
fault and absent-battery state has not been measured. Such changes could mimic
a cable transition, and another board revision may differ. No button or touch
GPIO is repurposed. USB presence never implies a full battery.

GPIO29 reads BAT_ADC through R27=200k / R32=100k (3:1), matching the original
Waveshare demo. The ADC uses a nominal 3.3 V reference. The display curve was rescaled to
map the observed approximately 4.02 V plateau to 100%, rather than requiring
4.20 V. This is an empirical display adjustment, not a multimeter calibration
or independent confirmation that the cell is fully charged. Intermediate curve
points were also rescaled and have not been individually measured. Eight
readings are averaged and filtered with a 1/4 exponential update. Load,
charging, temperature and cell age affect this estimate; it is not a fuel gauge.
Values outside 2.50–4.35 V show `--%` and `BATERIA NO VERIFICADA`. An absent
battery whose charger voltage looks valid cannot be distinguished reliably.

### Open issue: charging screen on battery-only startup

The owner reports that the charging screen also opens on battery-only power-on.
The current 700 ms GPIO17-high startup rule has not resolved that case. Do not
interpret the cable-cycle test as proof of reliable startup power detection.
A battery-only boot capture is still needed before choosing a longer startup
verification interval or requiring an observed low-to-high transition.

`power_screen.py` currently includes temporary startup logging to `/bootlog.csv`:
GPIO17 and nominal battery voltage are sampled at most every 250 ms during the
first 15 seconds after the module loads. The file is capped around 1,500 bytes
by removing older samples. This diagnostic can write flash during startup and
should be removed after power detection is resolved. It does not change care
state. Board copies and raw diagnostic logs remain in ignored `device-backups/`.

### Description return and verification

The USB-powered description-return failure was captured live as repeated
`memory allocation failed, allocating 1024 bytes` errors. Closing a description
now restores `/picodex-return.tmp`, a saved artwork framebuffer, instead of
decompressing artwork again. Pagination leaves this snapshot untouched.
Power-button handling runs before touch rendering, and touch edges are committed
before rendering so a failed action cannot repeat while held. Shared I2C reads
have a 50 ms timeout. PICODEX shares the existing goodbye renderer.

Twelve host tests cover care state, voltage mapping, filtering, power debounce,
dismissal, re-arming, failed-overlay retries and snapshot integrity. Modules
compile with MicroPython 1.29 mpy-cross (format v6.3); changed device modules
are backed up and staged SHA-256 checks run before activation.

`tests/hardware_description_return.py` and
`tests/hardware_description_shutdown.py` use simulated touch/button inputs with
the real LCD and SD artwork. Compile/upload as `.mpy` modules before importing;
source execution uses extra heap. They confirm byte-identical description
return and shutdown reaching the power latch despite touch read errors.
The charging overlay also passed a simulated-tap byte-identical restoration
check and red/orange/green renders. Physical power cutoff, full charging-state
coverage and sensitivity still require owner handling.
