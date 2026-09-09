#!/usr/bin/env python3
"""Turn the ROTA checkout into Seeker Gravity.

Idempotent text edits (project.godot, export preset, title scene, splash scene) plus removal of
author-branded / Steam / itch files. Run after make_gravity_brand.py has produced the new art.
"""
import pathlib
import shutil

ROOT = pathlib.Path(__file__).resolve().parents[2]
NAME = "Seeker Gravity"
PKG = "com.justinliehu.seekergravity"


def edit(rel, pairs, required=True):
    p = ROOT / rel
    s = p.read_text(encoding="utf-8")
    before = s
    for old, new in pairs:
        if old not in s:
            if required:
                print("  !! not found in %s: %r" % (rel, old[:60]))
            continue
        s = s.replace(old, new)
    if s != before:
        p.write_text(s, encoding="utf-8", newline="\n")
        print("  ok  ", rel)
    else:
        print("  --  ", rel, "(unchanged)")


def main():
    print("1) project.godot")
    edit("project.godot", [
        ('config/name="ROTA: Bend Gravity"', 'config/name="%s"' % NAME),
        ('config/description="ROTA: Bend Gravity by Harmony Monroe\nharmonymonroe.com"',
         'config/description="%s - a gravity-bending block puzzle platformer. Based on ROTA by Harmony Monroe (MIT)."' % NAME),
        ('config/custom_user_dir_name="ROTA-Harmony"', 'config/custom_user_dir_name="Seeker-Gravity"'),
        ('boot_splash/image="res://media/image/UI/harmony-monroe-square-white.png"',
         'boot_splash/image="res://media/image/UI/splash.png"'),
        ('boot_splash/bg_color=Color( 0, 0, 0, 1 )', 'boot_splash/bg_color=Color( 0.078, 0.047, 0.157, 1 )'),
        ('config/windows_native_icon="res://media/image/icon/rota.ico"\n', ''),
    ])

    print("2) export_presets.cfg (Android preset)")
    edit("export_presets.cfg", [
        ('export_path="export/android/ROTA.apk"', 'export_path="build/android/seeker-gravity-release.apk"'),
        ('package/unique_name="harmonyhoney.rota"', 'package/unique_name="%s"' % PKG),
        ('package/name="ROTA"', 'package/name="%s"' % NAME),
        ('architectures/armeabi-v7a=true', 'architectures/armeabi-v7a=false'),
        ('launcher_icons/main_192x192="res://media/image/icon/android-icon192.png"',
         'launcher_icons/main_192x192="res://media/image/icon/icon192.png"'),
        ('launcher_icons/adaptive_foreground_432x432=""',
         'launcher_icons/adaptive_foreground_432x432="res://media/image/icon/adaptive_fg_432.png"'),
        ('launcher_icons/adaptive_background_432x432=""',
         'launcher_icons/adaptive_background_432x432="res://media/image/icon/adaptive_bg_432.png"'),
        ('version/name="1.0"', 'version/name="1.0.0"'),
    ])

    print("3) title scene")
    edit("src/menu/MenuTitle.tscn", [
        # credits list: "a game by" [author logo] -> our attribution mark
        ('[ext_resource path="res://media/image/UI/harmony-monroe-white.png" type="Texture" id=13]',
         '[ext_resource path="res://media/image/UI/credit-rota.png" type="Texture" id=13]'),
        ('text = "harmonymonroe.com   "', 'text = "MIT licensed - thank you Harmony!   "'),
        # attract-screen labels
        ('text = "ROTA"', 'text = "SEEKER GRAVITY"'),
        ('text = "BEND GRAVITY"', 'text = "BASED ON ROTA BY HARMONY MONROE"'),
    ])

    print("4) splash scene")
    edit("src/menu/Splash.tscn", [
        ('[ext_resource path="res://media/image/UI/harmony-monroe-square-white.png" type="Texture" id=1]',
         '[ext_resource path="res://media/image/UI/splash.png" type="Texture" id=1]'),
    ])

    print("5) remove author-branded / platform-specific files")
    for rel in ("media/image/UI/harmony-monroe-white.png", "media/image/UI/harmony-monroe-square-white.png",
                "media/image/UI/HarmonyHoneyLogo.svg", "media/image/icon/rota.ico",
                "media/image/icon/android-icon192.png",
                "media/font/Fontopo.otf", "media/font/KodomoRounded.otf"):
        p = ROOT / rel
        for f in (p, pathlib.Path(str(p) + ".import")):
            if f.exists():
                f.unlink()
                print("  rm  ", f.relative_to(ROOT))
    for rel in ("linux", "export"):
        p = ROOT / rel
        if p.exists():
            shutil.rmtree(p)
            print("  rm -r", rel)
    # the Alexandria font family is only used by the brand generator; keep just the weight it needs
    for f in (ROOT / "media/font").glob("alexandria-latin-*.ttf"):
        if "900" not in f.name:
            f.unlink()
            imp = pathlib.Path(str(f) + ".import")
            if imp.exists():
                imp.unlink()
    print("  fonts left:", sorted(x.name for x in (ROOT / "media/font").glob("*.[ot]tf")))

    print("6) sanity: leftover author strings in shipped scenes/scripts")
    hits = []
    for p in list((ROOT / "src").rglob("*.tscn")) + list((ROOT / "src").rglob("*.gd")) + [ROOT / "project.godot", ROOT / "export_presets.cfg"]:
        t = p.read_text(encoding="utf-8", errors="ignore")
        for needle in ("harmonymonroe.com", "harmonyhoney.rota", "harmony-monroe", "HarmonyHoneyLogo", "Bend Gravity", "ROTA: "):
            if needle in t:
                hits.append("%s: %s" % (p.relative_to(ROOT), needle))
    print("  " + ("\n  ".join(hits) if hits else "none"))


if __name__ == "__main__":
    main()
