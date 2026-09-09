#!/usr/bin/env python3
"""Wire the daily revive-in-place feature into Seeker Gravity (Godot 3.6). Idempotent.

- project.godot: autoloads Revive + RevivePrompt
- Shared.gd: persist Revive state in the save slot
- Player.gd: remember the last safe stand, offer the prompt when the death animation ends,
  revive with a short grace period instead of reloading the level
"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
NL = "\n"
TAB = "\t"


def rewrite(rel, fn):
    p = ROOT / rel
    before = p.read_text(encoding="utf-8")
    after = fn(before)
    if after != before:
        p.write_text(after, encoding="utf-8", newline=NL)
        print("  ok  ", rel)
    else:
        print("  --  ", rel, "(already patched)")


def patch_project(s):
    if "Revive=" in s:
        return s
    anchor = 'TouchScreen="*res://src/autoload/touch_screen.tscn"'
    assert anchor in s
    return s.replace(anchor, anchor + NL + 'Revive="*res://src/autoload/Revive.gd"' + NL +
                     'RevivePrompt="*res://src/menu/RevivePrompt.tscn"')


def patch_shared(s):
    if "Revive.to_save()" in s:
        return s
    old_save = TAB + 's["maps_visited"] = maps_visited.duplicate()' + NL
    assert old_save in s
    s = s.replace(old_save, old_save + TAB + 's["revives"] = Revive.to_save()' + NL, 1)
    old_keys = 'if not i in "time, csfn, last_scene, goals, dye, hair, maps_visited":'
    assert old_keys in s
    s = s.replace(old_keys, 'if not i in "time, csfn, last_scene, goals, dye, hair, maps_visited, revives":', 1)
    old_load = TAB + 'maps_visited = s["maps_visited"].duplicate() if s.has("maps_visited") else []'
    assert old_load in s
    s = s.replace(old_load, old_load + NL + TAB * 2 + 'Revive.from_save(s.get("revives", {}))', 1)
    return s


def patch_player(s):
    if "func revive_here" in s:
        return s
    # 1) state
    old_vars = "var is_dead := false" + NL + "var dead_clock := 0.0"
    assert old_vars in s
    s = s.replace(old_vars, old_vars + NL +
                  "# revive-in-place: last spot the player stood on, and post-revive invulnerability" + NL +
                  "var safe_pos := Vector2.ZERO" + NL +
                  "var safe_dir := 0" + NL +
                  "var has_safe := false" + NL +
                  "var revive_grace := 0.0" + NL +
                  "var is_revive_prompt := false" + NL +
                  "var stand_clock := 0.0", 1)
    # 2) grace check + remember stand in die()
    old_die = "func die():" + NL + TAB + "if is_dead: return"
    assert old_die in s
    s = s.replace(old_die, "func die():" + NL + TAB + "if is_dead: return" + NL + TAB + "if revive_grace > 0.0: return", 1)
    # 3) death animation end -> offer revive instead of reloading
    old_end = (TAB * 3 + "if dead_clock >= dead_time:" + NL +
               TAB * 4 + "Cutscene.is_playing = false" + NL +
               TAB * 4 + "Shared.reset()")
    assert old_end in s, "death branch not found"
    new_end = (TAB * 3 + "if dead_clock >= dead_time:" + NL +
               TAB * 4 + "_death_complete()")
    s = s.replace(old_end, new_end, 1)
    old_guard = TAB + "if is_dead:" + NL + TAB * 2 + "sprites.position += rot(velocity) * delta"
    assert old_guard in s
    s = s.replace(old_guard, TAB + "if is_dead:" + NL + TAB * 2 + "if is_revive_prompt: return" + NL +
                  TAB * 2 + "sprites.position += rot(velocity) * delta", 1)
    # 4) remember the last safe stand: right after the early return of _physics_process, so it runs
    #    whenever the player is alive and grounded (is_floor is set by move()); 0.2s settle timer
    old_ret = TAB + "if is_dead or (spr_easy.is_less or !spr_easy.show):" + NL + TAB * 2 + "return" + NL
    assert old_ret in s
    s = s.replace(old_ret, old_ret + TAB + NL +
                  TAB + "# revive-in-place: remember the last spot we stood on for at least 0.2s (is_floor comes from move())" + NL +
                  TAB + "if is_floor and !is_npc:" + NL +
                  TAB * 2 + "stand_clock += delta" + NL +
                  TAB * 2 + "if stand_clock >= 0.2:" + NL +
                  TAB * 3 + "safe_pos = global_position" + NL +
                  TAB * 3 + "safe_dir = dir" + NL +
                  TAB * 3 + "has_safe = true" + NL +
                  TAB + "else:" + NL +
                  TAB * 2 + "stand_clock = 0.0" + NL, 1)
    # 5) grace countdown + blink in _process
    old_proc = "func _process(delta):" + NL
    assert old_proc in s
    s = s.replace(old_proc, old_proc +
                  TAB + "if revive_grace > 0.0:" + NL +
                  TAB * 2 + "revive_grace = max(0.0, revive_grace - delta)" + NL +
                  TAB * 2 + "sprites.modulate.a = 0.4 if int(revive_grace * 10.0) % 2 == 0 else 1.0" + NL +
                  TAB * 2 + "if revive_grace == 0.0:" + NL +
                  TAB * 3 + "sprites.modulate.a = 1.0" + NL, 1)
    # 6) the new functions
    s = s.rstrip(NL) + NL + NL + '''func _death_complete():
	Cutscene.is_playing = false
	var prompt = get_node_or_null("/root/RevivePrompt")
	var revive = get_node_or_null("/root/Revive")
	if prompt != null and revive != null and has_safe and revive.can_offer(Shared.map_name):
		is_revive_prompt = true
		Cutscene.is_playing = true
		if !prompt.is_connected("revive_chosen", self, "revive_here"):
			prompt.connect("revive_chosen", self, "revive_here", [], CONNECT_ONESHOT)
		if !prompt.is_connected("restart_chosen", self, "restart_level"):
			prompt.connect("restart_chosen", self, "restart_level", [], CONNECT_ONESHOT)
		prompt.open(Shared.map_name)
	else:
		Shared.reset()

func restart_level():
	is_revive_prompt = false
	Cutscene.is_playing = false
	Shared.reset()

func revive_here():
	var revive = get_node_or_null("/root/Revive")
	if revive != null:
		revive.consume(Shared.map_name)
	is_revive_prompt = false
	is_dead = false
	dead_clock = 0.0
	Cutscene.is_playing = false
	revive_grace = 1.5
	global_position = safe_pos
	self.dir = safe_dir
	velocity = Vector2.ZERO
	joy = Vector2.ZERO
	sprites.position = Vector2.ZERO
	sprites.rotation = turn_to
	turn_ease.clock = turn_ease.time
	sprites.modulate.a = 1.0
	is_floor = false
	is_jump = true
	has_jumped = true
	anim.play("jump")
	Shared.save_data()
'''
    return s


if __name__ == "__main__":
    rewrite("project.godot", patch_project)
    rewrite("src/autoload/Shared.gd", patch_shared)
    rewrite("src/actor/Player.gd", patch_player)
