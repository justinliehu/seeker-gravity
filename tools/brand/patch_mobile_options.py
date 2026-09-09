#!/usr/bin/env python3
"""Idempotent: make the Options / Pause menus fit a phone (1.4.0).

- Shared.is_mobile (true on Android; tests override it)
- MenuOptions: on mobile hide the rows a touch player cannot use - Keyboard Setup, Controller Setup (A/B/X/Y remap), Fullscreen, Borderless,
  Window Size, Mouse, V-Sync. Everything a phone player can use stays: Controller Setup (Bluetooth
  gamepads), Grab Toggle, Touch Screen + margins, audio, performance (Interpolate, Frame Limit,
  Physics Step, Radial Blur, Dynamic Light, Shadows, Shadow Quality, Weather), Speedrun clock.
- MenuOptions.row(): the slider-tick sound used hard-coded cursor indices (cursor == 2 or > 5) that
  break as soon as a row is hidden; decide by "does this row react to left/right" instead.
- MenuPause: hide "Store Page" - the store link was removed in this distribution, so the button
  did nothing.
"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]


def patch(rel, fn):
    p = ROOT / rel
    before = p.read_text(encoding="utf-8")
    after = fn(before)
    if after != before:
        p.write_text(after, encoding="utf-8", newline="\n")
        print("  ok  ", rel)
    else:
        print("  --  ", rel, "(already patched)")


def shared(s):
    if "var is_mobile" in s:
        return s
    a = "var is_touch := false setget set_is_touch\n"
    assert a in s
    return s.replace(a, a + "# phone build: hides desktop-only options (keyboard remap, window size...). Tests may override.\n"
                        "var is_mobile := OS.get_name() == \"Android\"\n", 1)


MOBILE_HIDDEN = '["Keyboard", "Controller", "Fullscreen", "Borderless", "Resolution", "Mouse", "Vsync"]'


def options(s):
    if "MOBILE_HIDDEN" in s:
        return s
    s = s.replace("extends MenuBase\n",
                  "extends MenuBase\n\n"
                  "# rows that only make sense with a keyboard / desktop window; hidden on the phone build\n"
                  "const MOBILE_HIDDEN := " + MOBILE_HIDDEN + "\n", 1)
    old = ("\t\t\tif i.is_in_group(\"shadow\") and i.visible:\n"
           "\t\t\t\ti.visible = Shared.shadow_enabled > 0\n")
    assert old in s
    s = s.replace(old, old +
                  "			if i.name in MOBILE_HIDDEN:
"
                  "				if Shared.is_mobile:
					i.visible = false
"
                  "				elif not i.is_in_group(\"window\"):
"
                  "					i.visible = true  # window-group rows are decided by the fullscreen rule above
", 1)
    old_row = "func row():\n\tis_audio_joy = cursor == 2 or cursor > 5\n"
    assert old_row in s
    s = s.replace(old_row,
                  "func row():\n"
                  "\t# tick sound for rows that react to left/right (index-independent, rows may be hidden)\n"
                  "\tis_audio_joy = cursor < items.size() and items[cursor].has_method(\"axis_x\")\n", 1)
    return s


def pause(s):
    if "store_label" in s:
        return s
    old = ("\t\titems = []\n\t\tfor i in items_node.get_children():\n\t\t\tif i.visible:\n\t\t\t\titems.append(i)\n")
    assert old in s
    return s.replace(old,
                     "\t\t# the store link was removed in this distribution: never show a button that does nothing\n"
                     "\t\tvar store_label = items_node.get_node_or_null(\"Store\")\n"
                     "\t\tif store_label != null:\n"
                     "\t\t\tstore_label.visible = false\n" + old, 1)


if __name__ == "__main__":
    patch("src/autoload/Shared.gd", shared)
    patch("src/menu/options/MenuOptions.gd", options)
    patch("src/menu/MenuPause.gd", pause)
