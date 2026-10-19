# Pokémon Channel Jirachi Patcher

A Python script that patches your own copy of **Pokémon Channel** (GameCube, PAL) so that you can:

- set the **shiny odds** of the Jirachi gift (for example 1 in 4096, or always shiny), and the Jirachi stays legal
- remove the **Hall of Fame requirement**
- remove the **Pokédex requirement**
- receive **more than one Jirachi** on the same save file
- skip the Jirachi **cutscene** if you want, so choosing Jirachi in Options goes straight to the GBA link

Each option can be turned on or off on its own. The script contains no game data: you need your own Pokémon Channel disc image.

---

## What it does

When you run it, the script makes a patched **copy** of your disc image. Your original file is never changed.

| Option | Changed file | Effect |
|---|---|---|
| Shiny odds | `default.dol` (the game) | Jirachi is shiny 1 time in N, where N is the number you choose. |
| Remove Pokédex requirement | `pokechan.bin` (the program sent to the GBA) | The Pokédex check on your Ruby/Sapphire save always passes. |
| Remove Hall of Fame requirement | `pokechan.bin` | The Hall of Fame check on your save always passes, so you don't need to have beaten the Elite Four. |
| Allow multiple Jirachi | `pokechan.bin` | The "already received Jirachi" check is ignored, so you can receive Jirachi again on the same save. |
| Skip cutscene | `pch/scripts/stage_myroom.pkc` | Choosing Jirachi in Options goes straight to the GBA link screen. |

### How the shiny Jirachi stays legal

The script doesn't edit the Jirachi's PID or IVs. Before Jirachi is generated, Channel makes some random-number calls of its own. The patch reruns those calls from new starting points, using the game's own code, until the game's normal Jirachi generator produces a shiny one (or a non-shiny one).

So every Jirachi the patch produces is one that the unpatched game can also produce. It passes PKHeX's legality checks, including the PID/IV correlation and the Channel menu-pattern check.

---

## Requirements

- **Python 3.8 or newer**
  - Windows: install it from [python.org](https://www.python.org/downloads/), or with `winget install Python.Python.3.12`.
  - macOS and Linux: Python 3 is usually already installed.
- **Your own Pokémon Channel disc image, PAL version.** The USA version has no Jirachi gift. Supported formats:
  - `.iso`, either the full 1:1 image or a trimmed one
  - `.ciso`
  - `.rvz`, Dolphin's compressed format. RVZ files made with Dolphin's default **Zstandard** compression also need the `zstandard` Python module. If it's missing, the script asks whether to install it for you, or you can install it yourself:
    ```
    py -m pip install zstandard
    ```
    On macOS or Linux, use `python3 -m pip install zstandard`.
- **About 1.5 GB of free disk space** for the patched copy.
- To receive Jirachi you need, as with the original game:
  - a **Pokémon Ruby or Sapphire** cartridge, and
  - a way to link a GBA: a GameCube (or Wii with GameCube support) with a GBA link cable, or Dolphin with its built-in GBA emulation.

No other Python packages are needed.

---

## How to use it

### The easy way (Windows, macOS or Linux)

1. Download `patch_channel_iso.py`.
2. Double-click it, or run `py patch_channel_iso.py` (`python3 patch_channel_iso.py` on macOS or Linux).
3. When asked, **drag your disc image onto the window** and press Enter.
4. Follow the options. Pressing Enter accepts the default shown in brackets.

   ```
   Where should the patched ISO be saved?          [Enter = "<name> (Jirachi patched).iso" next to the original]
   Shiny odds for Jirachi, as '1 in N'             [default 1 in 8192]
   Skip the Jirachi cutscene?                      [Y/n]
   Remove the Pokedex requirement?                 [Y/n]
   Remove the Hall of Fame requirement?            [Y/n]
   Allow more than one Jirachi per save file?      [Y/n]
   ```

5. Wait for it to finish, then load the new `.iso` in your loader or emulator.

Shiny odds examples:

| You enter | Result |
|---|---|
| `8192` or just Enter | 1 in 8192, the same odds as the original game |
| `4096` | 1 in 4096 |
| `1` | Always shiny |
| `0` | Shiny patch removed, so the game's own unchanged code is used |

### Command line

```
py patch_channel_iso.py "Pokemon Channel.iso" [options]
```

| Option | Meaning |
|---|---|
| `--out "file.iso"` | Where to save the patched image. Default: `<name> (Jirachi patched).iso` next to the original. |
| `--odds N` | Shiny odds 1 in N. If you leave it out, the script asks. |
| `--skip-cutscene` / `--keep-cutscene` | Skip or keep the Jirachi cutscene. |
| `--keep-dex` | Keep the Pokédex requirement. |
| `--keep-hof` | Keep the Hall of Fame requirement. |
| `--single` | Keep the one-Jirachi-per-save limit. |
| `--undo` | Undo every change. Run this on an already-patched image to get an unmodified copy. |
| `-h`, `--help` | Show the built-in help. |

On the command line, the three requirement patches are applied unless you add `--keep-dex`, `--keep-hof` or `--single`.

Examples:

```
py patch_channel_iso.py "Pokemon Channel.rvz" --odds 4096
py patch_channel_iso.py "Pokemon Channel.iso" --odds 1 --keep-hof --out "Channel shiny.iso"
py patch_channel_iso.py "Channel (Jirachi patched).iso" --undo --out "Channel original.iso"
```

---

## Disclaimer

Use your own legally obtained game dumps. This tool is only for patching your own copies of the games, and it is not affiliated with Nintendo, The Pokémon Company or Game Freak.
