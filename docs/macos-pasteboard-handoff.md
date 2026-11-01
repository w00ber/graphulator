# Making Cmd+V paste work out of Graphulator

## Symptom

Copy a graph out of Graphulator or Paragraphulator, then in VectorCraft:

| How you paste | Result |
| ------------- | ------ |
| **Cmd+V** | nothing happens |
| Edit ▸ Paste | pastes fine |
| Right-click ▸ Paste | pastes fine |

Illustrator and Preview accept the same clipboard through every path,
*including* Cmd+V. And VectorCraft accepts an **Illustrator** copy through
every path, including Cmd+V. So it is neither "VectorCraft is broken" nor
"Graphulator's clipboard is broken" — it is something about this
pasteboard's shape that VectorCraft's keyboard path, specifically, rejects.

The working theory at the time was that VectorCraft has two paste paths, with
Cmd+V gated on something it recognises as native vector artwork while the menu
runs a permissive importer. That turned out to be roughly right in shape and
useless in practice — the keyboard path simply reads a flavour we were not
advertising. See [Resolution](#resolution).

## Resolution

**The fix is one line: `INCLUDE_SVG_AS_TEXT = True`.**

VectorCraft's paste path reads the SVG out of the `public.utf8-plain-text`
flavour. Without it, Cmd+V does nothing. With it, the graph pastes.

### How it was actually found

Not by theory — by diffing a working clipboard against a failing one **on the
same machine, minutes apart**. `scripts/pasteboard_variant.py watch` recorded
both:

```
Diagrammer copy — Cmd+V WORKS              Graphulator copy — Cmd+V FAILS
com.adobe.pdf             6087 bytes       com.adobe.pdf             9994 bytes
public.svg-image         31513 bytes       public.svg-image         36672 bytes
com.adobe.svg            31513 bytes       com.adobe.svg            36672 bytes
public.png               41450 bytes       public.png               43136 bytes
public.utf8-plain-text   31513 bytes       dyn...(image/svg+xml)    36672 bytes
                                           dyn...(application/pdf)   9994 bytes
```

One flavour present on the left and absent on the right. That is the whole
bug, and the comparison took two minutes once it was the thing being measured.

It corroborates the binary, too: VectorCraft's pasteboard vocabulary includes
`text/plain`, and Illustrator — which also pastes fine — advertises its SVG as
text as well.

### Why this took so long

Three avoidable detours, each worth a note:

1. **The `text` candidate was never tested.** It was identified correctly in
   the original handoff, implemented early, then left switched off pending a
   keyboard test that kept getting deferred for more interesting-looking
   theories. The answer sat behind a `False` for most of the investigation.

2. **Diffing against the wrong reference.** Illustrator was used as the
   known-good clipboard for several rounds. It is a *different app* with a
   different clipboard, so its extra flavours (AICB, PGF, private SVG UTIs)
   generated theories that its own binary could not support. The right
   reference was always Diagrammer: same family, known to work, trivially
   available.

3. **A clipboard race ate the first attempt at exactly this measurement.**
   `dump` runs after the copy, so anything touching the clipboard in between
   wins — including copying the dump command out of a browser, which is what
   happened. A dump full of `org.chromium.*` flavours is that race, not a
   result. **Use `watch`**, which records every copy as it happens:

   ```bash
   python scripts/pasteboard_variant.py watch   # then go make copies
   ```

**The lesson for next time: when the same payload works from one app and not
another, diff the two pasteboards before theorising about either.**

### What ships

| Change | Status | Why |
| ------ | ------ | --- |
| `INCLUDE_SVG_AS_TEXT = True` | **the fix** | VectorCraft reads the SVG from the text flavour |
| `writeObjects:` (modern API) | kept | halves `changeCount` churn (+1 per copy, was +2) |
| `com.adobe.svg` alias | kept | free, and what Diagrammer ships |
| `INCLUDE_MIME_ALIASES = True` | kept, optional | VectorCraft reads by MIME name, but Diagrammer pastes with no MIME names at all — so this is defensive, not load-bearing |
| `_strip_svg_doctype` | kept, optional | also defensive; see below |

The last two are **not** what fixed this, and both can be reverted in one line
if they ever cause trouble.

### The cost of the fix

Pasting into a **plain-text** target — BBEdit, a terminal, a code editor —
now yields SVG source instead of nothing. Rich-text and image consumers are
unaffected: they ask for their own flavour and never see this one. The text
flavour goes **last**, after the artwork, so nothing walking the type list in
order prefers the source over the graph.

### Theories that were tested and disproven

Recorded so nobody re-runs them:

| Theory | Verdict |
| ------ | ------- |
| `public.svg-image` alone is enough | ✗ shipped originally; Cmd+V failed |
| The modern `writeObjects:` API | ✗ tried; Cmd+V failed |
| `com.adobe.svg` alias | ✗ tried; failed. Not in VectorCraft's binary, and `UTTypeCopyDeclaration` says it is not registered on this machine |
| `com.adobe.illustrator.aicb` / PGF / private SVG UTIs | ✗ Illustrator advertises them; VectorCraft's binary never mentions them. AICB is proprietary and unproducible anyway |
| MIME names (`image/svg+xml`) | ✗ as *the* fix — VectorCraft does read them, but Diagrammer pastes without any |
| matplotlib's `<!DOCTYPE>` breaking the parser | ✗ **disproven directly**: `graph-with-doctype.svg` opens fine in VectorCraft |
| `pt` units on `width`/`height` | ✗ Diagrammer's working SVG uses `mm`; `usvg` handles unit suffixes |
| A second, narrower importer on the Cmd+V path | ✗ unnecessary — one flavour explains everything |

### How the app was interrogated

Worth repeating on the next app that refuses a paste, because it took minutes
and replaced three rounds of guessing:

```bash
# 1. What does the app say it can read?
plutil -extract CFBundleDocumentTypes json -o - \
    /Applications/VectorCraft.app/Contents/Info.plist

# 2. What pasteboard type names are in the binary at all?
strings -a /Applications/VectorCraft.app/Contents/MacOS/VectorCraft \
  | grep -aE "com\.adobe\.[a-z0-9.]+|public\.(svg-image|png|tiff)|image/|application/"
```

That turned up one contiguous list of literals — the app's pasteboard
vocabulary:

```
image/svg+xml  application/pdf  application/postscript
public.png  public.tiff  image/tiff
com.adobe.encapsulated-postscript  com.adobe.pdf  Apple PDF pasteboard type
```

Two facts fell out immediately: `image/svg+xml` is there and
`public.svg-image` is not, and `com.adobe.illustrator.*` appears **zero**
times — so the AICB/private-UTI theory below was dead before anyone tried it.

### What an Illustrator copy looks like, for reference

```
com.adobe.illustrator.aicb                   56886 bytes
dyn.ah62d4rv4gu81q5xef341g3bptmy1a              -1 bytes   (MIME vnd.usd+zip, no data)
com.adobe.svg                                   -1 bytes   (declared, no data)
public.svg-image                              9193 bytes
com.adobe.pdf                               896151 bytes
com.adobe.illustrator.svgm                    9133 bytes
com.adobe.illustrator.svg                     9133 bytes
public.utf8-plain-text                        9133 bytes
public.png                                    3188 bytes
com.adobe.illustrator.pgf.14.0              496583 bytes
```

Illustrator provides **no** MIME names and still pastes on Cmd+V, so it must
match on `com.adobe.pdf` or `public.png` further down VectorCraft's list. Its
SVG flavours are DOCTYPE-free, which is the point: every clipboard that
worked in this app had parseable SVG, and the one that did not was the one
matplotlib produced.

## Confirm

```bash
PYTHONPATH=src python scripts/pasteboard_variant.py text
```

then Cmd+V into VectorCraft. The shipping pasteboard, one item:

```
com.adobe.pdf                                 3116 bytes
public.svg-image                             10790 bytes
com.adobe.svg                                10790 bytes
public.png                                   12560 bytes
public.utf8-plain-text                       10790 bytes
dyn.ah62d4rv4gu80w5pbq7ww8650q6z1u5pq        10790 bytes   (image/svg+xml)
dyn.ah62d4rv4gu80c6durvy0g2pyrf106p5uqvxa     3116 bytes   (application/pdf)
```

Spot-check Illustrator, Preview and Keynote too, and one plain-text editor —
that last one is the only place the fix is visible as a change, and it will
now receive SVG source.

To bisect again, every variant drives the real `clipboard_export` code,
flipping only its module constants:

```bash
PYTHONPATH=src python scripts/pasteboard_variant.py legacy      # pre-fix
PYTHONPATH=src python scripts/pasteboard_variant.py modern      # UTIs only
PYTHONPATH=src python scripts/pasteboard_variant.py alias       # + com.adobe.svg
PYTHONPATH=src python scripts/pasteboard_variant.py mime        # + MIME names
PYTHONPATH=src python scripts/pasteboard_variant.py text        # what ships now
PYTHONPATH=src python scripts/pasteboard_variant.py eps         # + EPS
PYTHONPATH=src python scripts/pasteboard_variant.py everything  # all of them
PYTHONPATH=src python scripts/pasteboard_variant.py dump        # writes nothing
PYTHONPATH=src python scripts/pasteboard_variant.py watch       # every copy, live
```

## Where the reference implementation is

Diagrammer, in this same `MY_PACKAGES` tree, was the precedent this handoff
started from: identical symptom, fixed by adding the modern API, the
`com.adobe.svg` alias and the plain-text flavour all at once.

**The precedent was right; the reading of it was wrong.** Of its three
ingredients the plain-text flavour was the active one, exactly as the
original handoff suspected. The other two were tried here first — being
cheaper and more interesting — and both failed, which made the precedent look
discredited when it was merely untested. Diagrammer's clipboard was the
correct reference all along.

- `src/diagrammer/io/exporter.py`
  - `_pasteboard_flavors()` — the `(UTI, payload)` list, richest-first
  - `_set_clipboard_macos_ctypes()` / `_pyobjc()` / `_subprocess()`
  - `INCLUDE_SVG_AS_TEXT`
- `tests/test_clipboard_flavors.py`

Graphulator's structure is simpler: `render_figure_formats` already hands
`copy_figure_to_clipboard` the SVG bytes, so none of Diagrammer's
`svg_data` threading was needed.

## Gotchas

**The MIME names cannot go on the NSPasteboardItem.**
`NSPasteboardItem.setData:forType:` refuses a type string that is not a valid
UTI — `'image/svg+xml' is not a valid UTI string` — so they are added at the
*pasteboard* level with `addTypes:owner:` after the item is written. Because
`addTypes:` extends the item already there, a copy still costs a single
`changeCount` bump (measured `2316 -> 2317`). macOS stores a MIME name as a
dynamic UTI, so a dump shows `dyn.ah62d4rv4gu80w5pbq7ww8650q6z1u5pq` rather
than `image/svg+xml`; that is normal, and an app asking by name resolves to
the same dynamic UTI. **Do not "tidy" these into `_pasteboard_flavours`** —
they will be silently rejected and the aliases will vanish without a word.
`test_mime_names_are_deliberately_not_utis` guards that.

To decode a `dyn.*` UTI by hand: strip `dyn.a`, read the rest as 5-bit indices
into `abcdefghkmnpqrstuvwxyz0123456789`, reassemble as bytes. The result is
prefixed `?0=6:4=` for a MIME type.

**Do not drop the plain-text flavour.** `INCLUDE_SVG_AS_TEXT = False` is
what made Cmd+V fail in VectorCraft, and the failure is silent — the copy
succeeds, every other app still pastes, and only that one key in that one app
stops working. `test_svg_source_ships_as_plain_text` guards it. The
trade-off it buys is in [The cost of the fix](#the-cost-of-the-fix).

**Do not reintroduce the DOCTYPE.** If `render_figure_formats` is ever
refactored to hand back matplotlib's raw `savefig` bytes, the declaration
comes back. That is not what broke VectorCraft — it opens a matplotlib SVG
with the DOCTYPE intact — but an editor on the same Rust SVG stack that does
not pass `allow_dtd` would reject our SVG outright.
`test_rendered_svg_carries_no_doctype` guards it.

**Keep the ctypes path first.** It exists so the frozen PyInstaller bundles
(`building/graphulator.spec`, `building/paragraphulator.spec`) get native
vector paste without shipping `pyobjc`. `NSPasteboardItem` is as reachable
through `libobjc.dylib` as `NSPasteboard` is, so this costs nothing — just
do not "simplify" the chain down to the PyObjC path.

**`setData:forType:` on an item means something different than on the
pasteboard.** The item-level call rejects a string that is not a valid UTI,
so a false return is the signal that a *flavour name* is wrong, not that
the data was bad. All three writers log a warning naming the rejected
flavour and raise only if nothing at all was accepted. This is also exactly
why the MIME names have to go on at the pasteboard level — see
[The catch worth knowing](#the-catch-worth-knowing).

**`_PASTEBOARD_SCRIPT` is injected with `str.format`**, so any literal `{`
or `}` added to it must be doubled. `test_pasteboard_script_formats_into_valid_python`
in `tests/test_clipboard_flavours.py` catches the one you forget.

**Tests must not clobber the real pasteboard.**
[`tests/test_clipboard_flavours.py`](../tests/test_clipboard_flavours.py)
monkeypatches the macOS writers and asserts on the `(uti, payload)` list
they receive. Diagrammer learned why the annoying way: a test that left
data on Qt's clipboard silently hijacked an unrelated paste test later in
the same run, because the paste path checks Qt's mime data before falling
back to reading NSPasteboard directly.

## Verify

```bash
QT_QPA_PLATFORM=offscreen python -m pytest tests -q   # 1008 passed, 1 skipped
```

and to inspect the real pasteboard after a copy:

```bash
PYTHONPATH=src python scripts/pasteboard_variant.py dump
```

One item carrying every flavour is correct. Several items, or a flavour
whose length comes back `-1`, means something promised data it never
delivered.
