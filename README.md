# PICODEX & Virtual Pokemon

Two offline Pokémon apps for the Waveshare RP2350-Touch-LCD-1.54, with 1,538 artwork entries on an SD card. The project includes firmware sources, compiled MicroPython modules, artwork archives, Spanish descriptions, preserved English descriptions, and the assets needed to reproduce the build.

## Startup and controls

A Pokémon logo and Poké Ball splash shows **Cargando....** for five seconds, then opens the graphical **ELIGE TU MUNDO** menu. Tap Pikachu for **Virtual Pokemon** or the red Pokédex for **PICODEX**. The left hardware button selects Virtual Pokemon; the right selects PICODEX. Selecting an app performs a clean soft restart so it has enough memory for artwork. Restart the board to return to the menu.

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
