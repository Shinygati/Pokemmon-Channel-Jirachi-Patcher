#!/usr/bin/env python3
"""
Pokemon Channel (GameCube, PAL/AUS) - Jirachi patcher for GameCube disc images

Saves a patched copy of your disc image; the original is never changed.

  1. pokechan.bin (the GBA program sent over the link cable) - each one optional
       * Pokedex requirement      -> removed
       * Hall of Fame requirement -> removed
       * One Jirachi per save     -> as many Jirachi as you like
  2. main.dol (the game itself)
       * Custom Jirachi shiny odds of 1 in N (default N = 8192)
         Re-runs the game's own pre-Jirachi RNG sequence (menu pattern +
         accept rolls) from new starting points until the normal generator
         produces a shiny (or non-shiny) Jirachi. Every result is one the
         unmodified game can produce from a menu-reachable seed, so it passes
         PKHeX's PID/IV correlation and Channel menu-pattern checks.

  3. pch/scripts/stage_myroom.pkc (optional, asked when you run it)
       * Skips the Jirachi cutscene: choosing Jirachi in Options goes straight
         to the GBA link, as if you had answered "Yes". The shiny routine stays
         active so every Jirachi still comes from a legal, menu-reachable seed
         (odds 0 = the game's normal 1 in 8192 in that case).

Easiest: double-click this script (or run it with no arguments). It asks for
the ISO (you can drag it onto the window) and then asks what you want.

Command-line usage (any supported image type works in place of game.iso):
  py patch_channel_iso.py "game.iso"              apply everything, asks for odds
  py patch_channel_iso.py "game.iso" --odds 512   apply everything, odds 1/512
  py patch_channel_iso.py "game.iso" --odds 1     always shiny
  py patch_channel_iso.py "game.iso" --odds 0     normal game odds (shiny patch removed)
  py patch_channel_iso.py "game.iso" --skip-cutscene   also skip the Jirachi cutscene
  py patch_channel_iso.py "game.iso" --keep-cutscene   restore the Jirachi cutscene
  py patch_channel_iso.py "game.iso" --keep-hof        keep the Hall of Fame requirement
  py patch_channel_iso.py "game.iso" --keep-dex        keep the Pokedex requirement
  py patch_channel_iso.py "game.iso" --single          keep the one-Jirachi-per-save limit
    (without these three, the command line removes all of them, as before)
  py patch_channel_iso.py "game.iso" --undo       revert everything
  py patch_channel_iso.py "game.iso" --out "new.iso"   where to save the result

The original ISO is never changed: the patched copy is saved as
"<name> (Jirachi patched).iso" next to it, or wherever you choose.

You can re-run it on a patched ISO any time to change the odds or options.
Accepts .iso (full 1:1 or trimmed), .ciso and .rvz images. CISO and RVZ files
are unpacked and saved as a plain .iso (RVZ files using Zstandard - Dolphin's
default - need the 'zstandard' module; the patcher offers to install it).
"""
import hashlib
import os
import struct
import sys

# ---------------------------------------------------------------- pokechan.bin
BIN_SIZE = 70236
BIN_SHA1_ORIG = "32429c491ae83f84b2a71fe5523fccd215aaab59"
BIN_SIG_OFFSET = 0x4600
BIN_SIG = bytes.fromhex(
    "24d081420ad80348814247d0024814e04158504a4158504941585649044881423c"
    "d0814208d8034881420bd034e00000415850534158564a014881422ed02be0"
)
# key: (offset in pokechan.bin, original bytes, patched bytes, description)
BIN_PATCHES = {
    "dex":   (0x46F4, "00b50748", "01207047", "Pokedex requirement"),       # check -> return 1
    "hof":   (0x4754, "05490648", "01207047", "Hall of Fame requirement"),  # check -> return 1
    "multi": (0x4AB3, "d0", "e0", "One Jirachi per save"),                 # skip "already received" check
}

# -------------------------------------------------------------------- main.dol
DOL_SIZE = 2720352
DOL_SHA1 = "4e17f5a0c06ca271d12bae0965ea1558c09380e7"
# Jirachi generator call site (0x8008EC24) and code cave (0x80004A20), as DOL file offsets
SITE_OFF = 0x8BAA4
SITE_CONTEXT = bytes.fromhex("9421ffd07c0802a69001003439610030480c23e97c761b78")  # 24 bytes before site
SITE_ORIG = bytes.fromhex("3c600001")       # lis r3,1
SITE_NEW = bytes.fromhex("4bf75dfd")        # bl 0x80004A20
CAVE_OFF = 0x1A20
CAVE_CODE = bytes.fromhex(
    "3d600000616b00642c0b00004182013c7d8c42e67d4c5b967d4a59d67d4a6050"
    "386000002c0a00004082000838600001808da47080a400003cc0000360c643fd"
    "3ce0002660e79ec33d0000107d0903a67ca531d67ca53a147ca92b7839000000"
    "7d2931d67d293a14552a17be396000017d6b50307d085b782808000e4180ffe4"
    "7d2931d67d293a147d2931d67d293a147d2931d67d293a147d2931d67d293a14"
    "7d2931d67d293a14552a843e280a4000408100207d2931d67d293a14552a843e"
    "280a547a4081000c7d2931d67d293a147d2931d67d293a147d4931d67d4a3a14"
    "7d6a31d67d6b3a147d8b31d67d8c3a14554a843e556b843e558c843e7d605278"
    "68009cba39000000280c000840800008390000017c0040004182000868008000"
    "7c006278390000002800000840800008390000017c0818004182000c4200ff14"
    "48000008912400003c6000014e800020"
)
# v1 routine (seed stepping, could fail PKHeX menu check) - recognised so it can be replaced
CAVE_CODE_V1 = bytes.fromhex(
    "3d600000616b00402c0b0000418200bc7d8c42e67d4c5b967d4a59d67d4a6050"
    "386000002c0a00004082000838600001808da47080a400003cc0000360c643fd"
    "3ce0002660e79ec33d0000107d0903a67d2531d67d293a147d4931d67d4a3a14"
    "7d6a31d67d6b3a145529843e554a843e556b843e7d4c4a78698c9cba39000000"
    "280b000840800008390000017c0c400041820008698c80007d8c5a7839000000"
    "280c000840800008390000017c081800418200147ca531d67ca53a144200ff94"
    "4800000890a400003c6000014e800020"
)
CHUNK = 16 * 1024 * 1024

# ------------------------------------------------- pch/scripts/stage_myroom.pkc
SCRIPT_PATH = "/pch/scripts/stage_myroom.pkc"
SCRIPT_SIZE = 347865
SCRIPT_SHA1_ORIG = "c607e079ae5178abf7360c89b368060d064938ab"
# bytecode offset 0x3DDCE (+0x24 header): "push 0x2791" -> "jmp 0x3E04F" (the "Yes" branch)
SCRIPT_OFF = 0x24 + 0x3DDCE
SCRIPT_ORIG = bytes.fromhex("190000002791")
SCRIPT_NEW = bytes.fromhex("1d020003e04f")
NATURAL_ODDS = 8192


def cave_with_odds(n):
    c = bytearray(CAVE_CODE)
    c[0:8] = struct.pack(">II", 0x3D600000 | (n >> 16), 0x616B0000 | (n & 0xFFFF))
    return bytes(c)


def find_bin(f):
    pos, tail = 0, b""
    while True:
        f.seek(pos)
        block = f.read(CHUNK)
        if not block:
            return None
        data = tail + block
        base = pos - len(tail)
        i = data.find(BIN_SIG)
        while i != -1:
            start = base + i - BIN_SIG_OFFSET
            if start >= 0:
                f.seek(start)
                if bin_state(f.read(BIN_SIZE)) is not None:
                    return start
            i = data.find(BIN_SIG, i + 1)
        tail = data[-(len(BIN_SIG) - 1):]
        pos += len(block)


def read_at(f, off, n):
    f.seek(off)
    return f.read(n)


def write_at(f, off, data):
    f.seek(off)
    f.write(data)


def bin_state(data):
    """Return {key: patched?} if data is pokechan.bin with any mix of our patches, else None."""
    if len(data) != BIN_SIZE:
        return None
    clean = bytearray(data)
    state = {}
    for key, (off, orig, new, _) in BIN_PATCHES.items():
        o, n = bytes.fromhex(orig), bytes.fromhex(new)
        cur = data[off:off + len(o)]
        if cur not in (o, n):
            return None
        state[key] = cur == n
        clean[off:off + len(o)] = o
    return state if hashlib.sha1(clean).hexdigest() == BIN_SHA1_ORIG else None


def patch_bin(f, want):
    """want: {key: True to apply (remove that restriction) / False to restore}."""
    print("Searching for pokechan.bin (this reads the whole ISO) ...")
    start = find_bin(f)
    if start is None:
        print("  pokechan.bin not found / different version - skipped.")
        return False
    for key, (off, orig, new, _) in BIN_PATCHES.items():
        write_at(f, start + off, bytes.fromhex(new if want[key] else orig))
    f.flush()
    state = bin_state(read_at(f, start, BIN_SIZE))
    ok = state == want
    for key, (_, _, _, desc) in BIN_PATCHES.items():
        if key == "multi":
            label = "removed (multiple Jirachi allowed)" if want[key] else "kept (one Jirachi per save)"
        else:
            label = "removed" if want[key] else "kept"
        print(f"  {desc}: {label}")
    if not ok:
        print("  Requirement patches - VERIFY FAILED!")
    return ok


def patch_dol(f, odds):
    """odds=None -> remove shiny patch; otherwise install 1/odds."""
    dol = struct.unpack(">I", read_at(f, 0x420, 4))[0]
    site = dol + SITE_OFF
    cave = dol + CAVE_OFF
    ctx = read_at(f, site - len(SITE_CONTEXT), len(SITE_CONTEXT))
    cur_site = read_at(f, site, 4)
    cur_cave = read_at(f, cave, len(CAVE_CODE))
    if ctx != SITE_CONTEXT or cur_site not in (SITE_ORIG, SITE_NEW):
        print("  main.dol doesn't match the version this patch was made for - shiny patch skipped.")
        return False
    v1 = len(CAVE_CODE_V1)
    cave_is_ours = cur_cave[8:] == CAVE_CODE[8:]
    cave_is_v1 = cur_cave[8:v1] == CAVE_CODE_V1[8:] and cur_cave[v1:] == bytes(len(CAVE_CODE) - v1)
    if cave_is_v1:
        print("  Replacing the older shiny routine (v1) with the PKHeX-legal version.")
    if not (cave_is_ours or cave_is_v1 or cur_cave == bytes(len(CAVE_CODE))):
        print("  Code cave in main.dol isn't empty - shiny patch skipped.")
        return False
    if cur_site == SITE_ORIG and not (cave_is_ours or cave_is_v1):
        h = hashlib.sha1(read_at(f, dol, DOL_SIZE)).hexdigest()
        if h != DOL_SHA1:
            print("  Note: main.dol differs slightly from the one analysed, but the patch spot matches.")
    if odds is None:
        write_at(f, site, SITE_ORIG)
        write_at(f, cave, bytes(len(CAVE_CODE)))
        f.flush()
        ok = read_at(f, site, 4) == SITE_ORIG
        print("  Shiny patch: removed (normal odds)" + (" OK." if ok else " - VERIFY FAILED!"))
        return ok
    code = cave_with_odds(odds)
    write_at(f, cave, code)
    write_at(f, site, SITE_NEW)
    f.flush()
    ok = read_at(f, cave, len(code)) == code and read_at(f, site, 4) == SITE_NEW
    label = "always shiny" if odds == 1 else f"1 in {odds}"
    print(f"  Shiny patch: odds set to {label}" + (" OK." if ok else " - VERIFY FAILED!"))
    return ok


def find_file(f, want):
    """Return (disc offset, size) of a file in the disc's file table, or None."""
    fst_off, fst_size = struct.unpack(">II", read_at(f, 0x424, 8))
    fst = read_at(f, fst_off, fst_size)
    count = struct.unpack(">I", fst[8:12])[0]
    names = fst[count * 12:]
    stack, i = [("", count)], 1
    while i < count:
        while stack and i >= stack[-1][1]:
            stack.pop()
        w0, a, b = struct.unpack(">III", fst[i * 12:i * 12 + 12])
        n0 = w0 & 0xFFFFFF
        name = names[n0:names.index(b"\0", n0)].decode("latin-1")
        full = (stack[-1][0] if stack else "") + "/" + name
        if w0 >> 24:
            stack.append((full, b))
        elif full.lower() == want.lower():
            return a, b
        i += 1
    return None


def script_state(f):
    """Return (offset, 'orig'|'skip') for stage_myroom.pkc, or None if unknown."""
    found = find_file(f, SCRIPT_PATH)
    if not found or found[1] != SCRIPT_SIZE:
        return None
    off = found[0]
    cur = read_at(f, off + SCRIPT_OFF, len(SCRIPT_ORIG))
    if cur == SCRIPT_ORIG:
        data = read_at(f, off, SCRIPT_SIZE)
        return (off, "orig") if hashlib.sha1(data).hexdigest() == SCRIPT_SHA1_ORIG else None
    if cur == SCRIPT_NEW:
        data = bytearray(read_at(f, off, SCRIPT_SIZE))
        data[SCRIPT_OFF:SCRIPT_OFF + 6] = SCRIPT_ORIG
        return (off, "skip") if hashlib.sha1(data).hexdigest() == SCRIPT_SHA1_ORIG else None
    return None


def patch_script(f, skip):
    st = script_state(f)
    if st is None:
        print("  stage_myroom.pkc doesn't match the version this patch was made for - cutscene patch skipped.")
        return False
    off, state = st
    if (state == "skip") == skip:
        print("  Cutscene: already " + ("skipped." if skip else "normal."))
        return True
    write_at(f, off + SCRIPT_OFF, SCRIPT_NEW if skip else SCRIPT_ORIG)
    f.flush()
    ok = read_at(f, off + SCRIPT_OFF, 6) == (SCRIPT_NEW if skip else SCRIPT_ORIG)
    print("  Cutscene: " + ("skipped (goes straight to the GBA link)" if skip else "restored") + (" OK." if ok else " - VERIFY FAILED!"))
    return ok


def ask_yes_no(question, default):
    hint = "[Y/n]" if default else "[y/N]"
    while True:
        s = input(f"{question} {hint}: ").strip().lower()
        if s == "":
            return default
        if s in ("y", "yes"):
            return True
        if s in ("n", "no"):
            return False
        print("  Please answer y or n.")


def clean_path(p):
    p = p.strip().strip('"').strip("'").strip()
    if p.startswith("& "):  # PowerShell drag-and-drop prefix
        p = p[2:].strip().strip("'").strip('"')
    return p


# ----------------------------------------------------------- disc image formats
GC_MAGIC = bytes.fromhex("c2339f3d")   # at 0x1C in every GameCube disc header
WII_MAGIC = bytes.fromhex("5d1c9ea3")  # at 0x18 in Wii disc headers
IMAGE_EXTS = (".iso", ".gcm", ".ciso", ".rvz")
FORMAT_NAMES = {
    "iso": "ISO",
    "ciso": "CISO",
    "rvz": "RVZ",
}


def detect_format(path):
    """Return one of FORMAT_NAMES' keys, 'wii', or None."""
    with open(path, "rb") as f:
        head = f.read(0x220)
    if head[0x1C:0x20] == GC_MAGIC:
        return "iso"
    if head[0x18:0x1C] == WII_MAGIC:
        return "wii"
    if head[:4] == b"CISO":
        return "ciso"
    if head[:4] == b"RVZ\x01":
        return "rvz"
    return None


class Progress:
    def __init__(self, total):
        self.total = max(total, 1)
        self.last = -1

    def __call__(self, done):
        pct = min(100, done * 100 // self.total)
        if pct != self.last:
            self.last = pct
            print(f"\r  {pct}%", end="", flush=True)


def copy_plain(src, dst):
    total = os.path.getsize(src)
    prog = Progress(total)
    done = 0
    with open(src, "rb") as fi, open(dst, "wb") as fo:
        while True:
            block = fi.read(CHUNK)
            if not block:
                break
            fo.write(block)
            done += len(block)
            prog(done)


def convert_ciso(src, dst):
    with open(src, "rb") as fi, open(dst, "wb") as fo:
        hdr = fi.read(0x8000)
        block_size = struct.unpack_from("<I", hdr, 4)[0]
        used = [i for i, v in enumerate(hdr[8:0x8000]) if v]
        if not block_size or not used:
            raise ValueError("empty or damaged CISO file")
        fo.truncate((used[-1] + 1) * block_size)
        prog = Progress(len(used))
        for n, i in enumerate(used):
            data = fi.read(block_size)
            fo.seek(i * block_size)
            fo.write(data)
            prog(n + 1)


# Lagged Fibonacci generator used by RVZ to rebuild the disc's padding ("junk") data.
# Same algorithm as Dolphin's LaggedFibonacciGenerator; the 521-word state is kept as
# bytes in output order, so XOR steps work on big integers for speed.
LFG_K, LFG_J, LFG_BYTES = 521, 32, 521 * 4


def lfg_forward(buf):
    def x(a, b, n):
        v = int.from_bytes(buf[a:a + n], "little") ^ int.from_bytes(buf[b:b + n], "little")
        buf[a:a + n] = v.to_bytes(n, "little")
    x(0, (LFG_K - LFG_J) * 4, LFG_J * 4)
    for i in range(LFG_J, LFG_K, LFG_J):
        x(i * 4, (i - LFG_J) * 4, min(LFG_J, LFG_K - i) * 4)


class LFG:
    def __init__(self, seed_bytes):
        b = list(struct.unpack(">17I", seed_bytes)) + [0] * (LFG_K - 17)
        for i in range(17, LFG_K):
            b[i] = ((b[i - 17] << 23) & 0xFFFFFFFF) ^ (b[i - 16] >> 9) ^ b[i - 1]
        self.buf = bytearray(b"".join(
            ((v & 0xFF00FFFF) | ((v >> 2) & 0x00FF0000)).to_bytes(4, "big") for v in b))
        for _ in range(4):
            lfg_forward(self.buf)
        self.pos = 0

    def skip(self, n):
        self.pos += n
        while self.pos >= LFG_BYTES:
            lfg_forward(self.buf)
            self.pos -= LFG_BYTES

    def take(self, n):
        out = bytearray()
        while n > 0:
            if self.pos >= LFG_BYTES:
                lfg_forward(self.buf)
                self.pos -= LFG_BYTES
            k = min(n, LFG_BYTES - self.pos)
            out += self.buf[self.pos:self.pos + k]
            self.pos += k
            n -= k
        return bytes(out)


def zstd_decompress(data):
    try:
        from compression import zstd  # Python 3.14+
        return zstd.decompress(data)
    except ImportError:
        pass
    try:
        import zstandard
    except ImportError:
        zstandard = None
    if zstandard is None:
        print("\n\nThis RVZ file is Zstandard-compressed, which needs the 'zstandard' Python module.")
        if not ask_yes_no("Install it now (runs: python -m pip install zstandard)?", True):
            raise RuntimeError("the 'zstandard' module is needed for this file "
                               "(install it with: py -m pip install zstandard)")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "zstandard"])
        import zstandard
        print()
    return zstandard.ZstdDecompressor().decompressobj().decompress(data)


def make_decompressor(method, props):
    import bz2
    import lzma
    if method == 0:
        return lambda d: d
    if method == 2:
        return bz2.decompress
    if method == 3:
        p, dict_size = props[0], struct.unpack_from("<I", props, 1)[0]
        filt = {"id": lzma.FILTER_LZMA1, "dict_size": dict_size,
                "lc": p % 9, "lp": (p // 9) % 5, "pb": p // 45}
        return lambda d: lzma.LZMADecompressor(lzma.FORMAT_RAW, filters=[filt]).decompress(d)
    if method == 4:
        p = props[0]
        dict_size = 0xFFFFFFFF if p >= 40 else (2 | (p & 1)) << (p // 2 + 11)
        filt = {"id": lzma.FILTER_LZMA2, "dict_size": dict_size}
        return lambda d: lzma.LZMADecompressor(lzma.FORMAT_RAW, filters=[filt]).decompress(d)
    if method == 5:
        return zstd_decompress
    raise ValueError(f"unknown RVZ compression method {method}")


def rvz_unpack(data, offset, size):
    """RVZ packing: runs of literal bytes or junk (rebuilt from a 68-byte LFG seed)."""
    out = bytearray()
    pos = 0
    while len(out) < size and pos < len(data):
        n = struct.unpack_from(">I", data, pos)[0]
        pos += 4
        if n & 0x80000000:
            n &= 0x7FFFFFFF
            lfg = LFG(data[pos:pos + 68])
            pos += 68
            lfg.skip((offset + len(out)) % 0x8000)
            out += lfg.take(n)
        else:
            out += data[pos:pos + n]
            pos += n
    return bytes(out)


def convert_rvz(src, dst):
    with open(src, "rb") as fi, open(dst, "wb") as fo:
        head = fi.read(0x48)
        iso_size = struct.unpack_from(">Q", head, 0x24)[0]
        disc_size = struct.unpack_from(">I", head, 0x0C)[0]
        disc = fi.read(disc_size)
        disc_type, method = struct.unpack_from(">II", disc, 0)
        chunk = struct.unpack_from(">I", disc, 0x0C)[0]
        if disc_type != 1:
            raise ValueError("this is a Wii disc, not a GameCube disc")
        dhead = disc[0x10:0x90]
        n_raw, raw_off, raw_size = struct.unpack_from(">IQI", disc, 0xB4)
        n_groups, group_off, group_size = struct.unpack_from(">IQI", disc, 0xC4)
        props = disc[0xD5:0xD5 + disc[0xD4]]
        dec = make_decompressor(method, props)
        fi.seek(raw_off)
        raws = dec(fi.read(raw_size))
        fi.seek(group_off)
        groups = dec(fi.read(group_size))
        fo.truncate(iso_size)
        fo.seek(0)
        fo.write(dhead)
        prog = Progress(n_groups)
        done = 0
        for r in range(n_raw):
            off, size, gidx, gcount = struct.unpack_from(">QQII", raws, r * 24)
            skipped = off % 0x8000
            off -= skipped
            size += skipped
            for j in range(gcount):
                g_start = off + j * chunk
                g_len = min(chunk, off + size - g_start)
                d_off, d_size, packed = struct.unpack_from(">III", groups, (gidx + j) * 12)
                compressed = bool(d_size & 0x80000000)
                d_size &= 0x7FFFFFFF
                if d_size:
                    fi.seek(d_off << 2)
                    data = fi.read(d_size)
                    if compressed:
                        data = dec(data)
                    if packed:
                        data = rvz_unpack(data, g_start, g_len)
                    fo.seek(g_start)
                    if g_start < 0x80:  # disc header lives in 'dhead'
                        data = data[0x80 - g_start:]
                        fo.seek(0x80)
                    fo.write(data[:g_len])
                done += 1
                prog(done)


def convert_image(src, dst, kind):
    if kind == "iso":
        copy_plain(src, dst)
    elif kind == "ciso":
        convert_ciso(src, dst)
    elif kind == "rvz":
        convert_rvz(src, dst)


def image_base(path):
    low = path.lower()
    for ext in IMAGE_EXTS:
        if low.endswith(ext):
            return path[:-len(ext)]
    return os.path.splitext(path)[0]


def output_ext(path, kind):
    if kind == "iso" and path.lower().endswith(".gcm"):
        return ".gcm"
    return ".iso"


def default_output(path, kind):
    return image_base(path) + " (Jirachi patched)" + output_ext(path, kind)


def fix_output_name(out, path, kind):
    """The result is always an uncompressed image, so give it a matching extension."""
    low = out.lower()
    if low.endswith((".iso", ".gcm")):
        return out
    for ext in IMAGE_EXTS:
        if low.endswith(ext):
            return out[:-len(ext)] + output_ext(path, kind)
    return out + output_ext(path, kind)


def same_file(a, b):
    try:
        return os.path.samefile(a, b)
    except OSError:
        return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def ask_output(path, kind):
    default = default_output(path, kind)
    print("\nWhere should the patched ISO be saved? (your original file is not changed)")
    print(f"  Press Enter for: {default}")
    print("  or drag/type a file name or a folder.")
    while True:
        out = clean_path(input("> "))
        if out == "":
            out = default
        elif os.path.isdir(out):
            out = os.path.join(out, os.path.basename(default))
        else:
            out = fix_output_name(out, path, kind)
        if same_file(out, path):
            print("  That's the original file - please choose a different name.")
            continue
        folder = os.path.dirname(os.path.abspath(out))
        if not os.path.isdir(folder):
            print(f"  The folder '{folder}' doesn't exist. Try again.")
            continue
        if os.path.exists(out) and not ask_yes_no(f"  '{out}' already exists. Replace it?", False):
            continue
        return out


def make_output(src, dst, kind):
    verb = "Copying" if kind == "iso" else f"Unpacking the {FORMAT_NAMES[kind]} file"
    print(f"{verb} to: {dst}")
    try:
        convert_image(src, dst, kind)
        print("\r  100% - done.\n")
        with open(dst, "rb") as f:
            if read_at(f, 0x1C, 4) != GC_MAGIC:
                raise ValueError("the unpacked image isn't a GameCube disc")
    except BaseException:
        print()
        try:
            os.remove(dst)
        except OSError:
            pass
        raise


def ask_path():
    while True:
        p = clean_path(input("Drag your Pokemon Channel disc image (.iso, .ciso or .rvz)\nonto this window (or type its path), then press Enter:\n> "))
        try:
            open(p, "rb").close()
            return p
        except OSError as e:
            print(f"  Can't open that file ({e}). Try again.\n")


def ask_odds():
    print("\nShiny odds for Jirachi, as '1 in N'.")
    print("  e.g. 4096 = 1 in 4096,  1 = always shiny,  0 = normal game odds (1 in 8192)")
    while True:
        s = input("Enter N [default 1 in 8192]: ").strip().replace(",", "")
        if s.lower().startswith("1/") or s.lower().startswith("1 in "):
            s = s.split("/")[-1] if "/" in s else s[5:]
            s = s.strip()
        if s == "":
            return 8192
        try:
            n = int(s)
            if 0 <= n <= 0xFFFFFFFF:
                return n
        except ValueError:
            pass
        print("  Please enter a number between 0 and 8192.")


def main():
    args = sys.argv[1:]
    if args and args[0] in ("-h", "--help"):
        print(__doc__)
        return
    interactive = not args or args[0].startswith("-")
    if interactive:
        print("Pokemon Channel - Jirachi patcher\n")
        path = ask_path()
    else:
        path = args[0]
    try:
        kind = detect_format(path)
    except OSError as e:
        print(f"Can't open {path}: {e}")
        sys.exit(2)
    if kind not in FORMAT_NAMES:
        if kind == "wii":
            print("That's a Wii disc image, not Pokemon Channel (GameCube).")
        else:
            print("Unrecognised file. Supported: .iso (full or trimmed), .ciso and .rvz.")
        if interactive:
            input("\nPress Enter to close.")
        sys.exit(2)
    print(f"Image type: {FORMAT_NAMES[kind]}" +
          ("" if kind == "iso" else " (the patched result is saved as a plain .iso)"))
    if "--out" in args:
        try:
            out = clean_path(args[args.index("--out") + 1])
        except IndexError:
            print('--out needs a file name, e.g. --out "patched.iso"')
            sys.exit(1)
        if os.path.isdir(out):
            out = os.path.join(out, os.path.basename(default_output(path, kind)))
        else:
            out = fix_output_name(out, path, kind)
    elif interactive:
        out = ask_output(path, kind)
    else:
        out = default_output(path, kind)
    if same_file(out, path):
        print("The output file can't be the original file - choose a different name with --out.")
        sys.exit(1)
    undo = "--undo" in args
    if "--odds" in args:
        try:
            odds = int(args[args.index("--odds") + 1])
        except (IndexError, ValueError):
            print("--odds needs a whole number, e.g. --odds 100")
            sys.exit(1)
        if not 0 <= odds <= 0xFFFFFFFF:
            print("--odds must be between 0 and 8192")
            sys.exit(1)
    elif undo:
        odds = 0
    else:
        odds = ask_odds()
    if undo:
        skip = False
    elif "--skip-cutscene" in args:
        skip = True
    elif "--keep-cutscene" in args:
        skip = False
    elif interactive:
        print()
        skip = ask_yes_no("Skip the Jirachi cutscene (Options -> Jirachi goes straight to the GBA link)?", True)
    else:
        skip = None  # leave the cutscene setting as it is
    if undo:
        reqs = {"dex": False, "hof": False, "multi": False}
    elif interactive:
        print()
        reqs = {
            "dex": ask_yes_no("Remove the Pokedex requirement?", True),
            "hof": ask_yes_no("Remove the Hall of Fame requirement?", True),
            "multi": ask_yes_no("Allow more than one Jirachi per save file?", True),
        }
    else:
        reqs = {
            "dex": "--keep-dex" not in args,
            "hof": "--keep-hof" not in args,
            "multi": "--single" not in args,
        }
    print()
    try:
        make_output(path, out, kind)
    except (OSError, ValueError, RuntimeError) as e:
        print(f"Couldn't read the image: {e}")
        if interactive:
            input("\nPress Enter to close.")
        sys.exit(2)
    with open(out, "r+b") as f:
        print("Game ID:", read_at(f, 0, 6).decode("ascii", "replace"))
        if skip is None:
            st = script_state(f)
            skip_active = bool(st and st[1] == "skip")
        else:
            skip_active = skip
        if undo:
            shiny = None
        elif odds == 0 and skip_active:
            # The skipped cutscene is where the game makes its pre-Jirachi RNG calls, so the
            # routine must stay on to keep seeds legal; 1 in 8192 = the game's normal odds.
            print("  (Cutscene skip is on, so 'normal odds' uses the routine at 1 in 8192 to stay legal.)")
            shiny = NATURAL_ODDS
        else:
            shiny = None if odds == 0 else odds
        ok1 = patch_dol(f, shiny)
        ok3 = True if skip is None else patch_script(f, skip)
        ok2 = patch_bin(f, reqs)
    print("Done." if (ok1 and ok2 and ok3) else "Finished with warnings (see above).")
    print(f"Patched ISO saved as: {out}")
    if interactive:
        input("\nPress Enter to close.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCancelled. Your original ISO was not changed.")