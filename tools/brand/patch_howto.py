#!/usr/bin/env python3
"""Idempotent (1.4.5): "How to Play" page + a one-time fading tip in the first level.

Store feedback on 1.4.4 was "no in game tutorial or explanation": a first-time player cannot guess the
one mechanic the whole game is built on. This keeps the no-tutorial design (nothing interrupts play,
nothing to dismiss) and adds the two smallest things that answer it:

  1. MenuHowTo (autoload scene, new file): controls with the on-screen button icons and three lines of
     rules. Reachable from the title menu and the pause menu, opt-in, closes on accept or back.
  2. Tip (autoload scene, new file): the first time the player stands in the first level of a new game,
     one line fades in at the bottom for five seconds and fades out. Shown once ever; the flag lives in
     user://tips.json so the save slots keep their format. Erasing a slot teaches again.

This script only wires the two new scenes into the existing files.
"""
import io
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
NL = "\n"


def rewrite(rel, fn):
    p = ROOT / rel
    before = io.open(p, encoding="utf-8").read()
    after = fn(before)
    if after != before:
        io.open(p, "w", encoding="utf-8", newline=NL).write(after)
        print("  ok  ", rel)
    else:
        print("  --  ", rel, "(already patched)")


def patch_project(s):
    if "MenuHowTo=" in s:
        return s
    a = 'RevivePrompt="*res://src/menu/RevivePrompt.tscn"' + NL
    assert a in s, "autoload anchor"
    # appended last so Shared / UI / Audio / MenuPause already exist when these two run _ready()
    return s.replace(a, a + 'MenuHowTo="*res://src/menu/MenuHowTo.tscn"' + NL
                     + 'Tip="*res://src/autoload/Tip.tscn"' + NL, 1)


def patch_title_scene(s):
    if 'name="HowTo"' in s:
        return s
    a = '[node name="Options" type="Label" parent="Canvas/CenterContainer/Control/MenuTitle/List"]'
    assert a in s, "title Options anchor"
    block = ('[node name="HowTo" type="Label" parent="Canvas/CenterContainer/Control/MenuTitle/List"]' + NL
             + "margin_left = 34.0" + NL
             + "margin_top = 235.0" + NL
             + "margin_right = 300.0" + NL
             + "margin_bottom = 286.0" + NL
             + "size_flags_horizontal = 4" + NL
             + "size_flags_vertical = 5" + NL
             + "theme = ExtResource( 26 )" + NL
             + 'text = "How to Play"' + NL
             + "align = 1" + NL
             + "valign = 1" + NL
             + NL)
    return s.replace(a, block + a, 1)


def patch_title_script(s):
    if '"howto"' in s:
        return s
    a = '\t\t"options":' + NL
    assert a in s, "title accept anchor"
    return s.replace(a, '\t\t"howto":' + NL + "\t\t\tsub_menu(MenuHowTo)" + NL + a, 1)


def patch_pause_scene(s):
    if 'name="HowTo"' in s:
        return s
    a = '[node name="Store" type="Label" parent="Control/List/Items"]'
    assert a in s, "pause Store anchor"
    block = ('[node name="HowTo" type="Label" parent="Control/List/Items"]' + NL
             + "margin_left = 496.0" + NL
             + "margin_top = 433.0" + NL
             + "margin_right = 784.0" + NL
             + "margin_bottom = 484.0" + NL
             + "size_flags_horizontal = 4" + NL
             + "size_flags_vertical = 5" + NL
             + "custom_fonts/font = ExtResource( 2 )" + NL
             + 'text = "How to Play"' + NL
             + "align = 1" + NL
             + "valign = 1" + NL
             + NL)
    return s.replace(a, block + a, 1)


def patch_pause_script(s):
    if '"howto"' in s:
        return s
    a = '\t\t"options":' + NL + "\t\t\tsub_menu(MenuOptions)" + NL
    assert a in s, "pause accept anchor"
    return s.replace(a, a + '\t\t"howto":' + NL + "\t\t\tsub_menu(MenuHowTo)" + NL, 1)


def patch_shared(s):
    # erasing a save slot means a fresh player: teach the mechanic again
    if "Tip.forget()" in s:
        return s
    a = "func erase_slot(arg := 0):" + NL + "\tsave_dict[arg] = {}" + NL
    assert a in s, "erase_slot anchor"
    return s.replace(a, a + "\tTip.forget()" + NL, 1)


if __name__ == "__main__":
    rewrite("project.godot", patch_project)
    rewrite("src/menu/MenuTitle.tscn", patch_title_scene)
    rewrite("src/menu/MenuTitle.gd", patch_title_script)
    rewrite("src/menu/MenuPause.tscn", patch_pause_scene)
    rewrite("src/menu/MenuPause.gd", patch_pause_script)
    rewrite("src/autoload/Shared.gd", patch_shared)
