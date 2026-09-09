extends SceneTree

# Daily revive-in-place regression test (Godot 3.6, run with --no-window):
#   die -> prompt (not a reload) -> revive at the last stand with grace -> counter drops
#   3 revives -> the 4th death offers only RESTART -> restart reloads the level
#   save round-trip and day rollover for the counter
# Run: Godot_v3.6.1-stable_win64.exe --no-window --path . --script res://tools/brand/test_revive_rota.gd
#
# NOTE: autoloads are looked up through the tree at runtime on purpose. A `--script` MainLoop is
# parsed BEFORE the autoloads are registered, and the Godot 3 type checker resolves an unknown
# `Shared` identifier by loading Shared.tscn early -> "cyclic reference" + every game script breaks.

const LEVEL := "res://src/map/worlds/1/2.tscn"

var _failures := []
var _step := 0
var _t := 0.0
var shared = null
var revive = null
var prompt = null
var _player = null
var _safe := Vector2.ZERO
var _revives_done := 0
var _reload_seen := false
var _total := 0.0
var _scene_changes := 0


func _check(ok: bool, msg: String) -> void:
	if ok:
		print("  ok   " + msg)
	else:
		_failures.append(msg)
		print("  FAIL " + msg)


func _on_scene_changed() -> void:
	_scene_changes += 1
	print("  .. scene_changed #%d step=%d map=%s" % [_scene_changes, _step, str(shared.map_name)])
	if _step >= 5:
		_reload_seen = true


func _idle(delta: float) -> bool:
	_t += delta
	_total += delta
	if _total > 45.0:
		var st = "step=%d t=%.1f scene_changes=%d" % [_step, _t, _scene_changes]
		if shared != null:
			st += " map=%s player=%s" % [str(shared.map_name), str(shared.player)]
		if _player != null:
			st += " is_dead=%s prompt_flag=%s has_safe=%s grace=%s" % [str(_player.is_dead), str(_player.is_revive_prompt), str(_player.has_safe), str(_player.revive_grace)]
		if prompt != null:
			st += " prompt_open=%s" % str(prompt.is_open)
		_check(false, "WATCHDOG: test did not finish in 45s: " + st)
		_finish()
		return false
	match _step:
		0:  # autoloads are children of root once Main::start finished
			shared = get_root().get_node_or_null("Shared")
			revive = get_root().get_node_or_null("Revive")
			prompt = get_root().get_node_or_null("RevivePrompt")
			if shared == null or revive == null or prompt == null:
				if _t > 5.0:
					_check(false, "autoloads Shared/Revive/RevivePrompt not found under root")
					_finish()
				return false
			shared.connect("scene_changed", self, "_on_scene_changed")
			revive.purchases_enabled = false  # this test covers the free tier / offline behaviour
			# the game's own path: wipe out -> change_scene -> wipe in (the wipe-in is what reveals the
			# player sprite and lets _physics_process run). Deferred, because a direct call from _idle
			# would resume its yield(idle_frame) in the same frame, before the level was instanced.
			shared.call_deferred("wipe_scene", LEVEL)
			_t = 0.0
			_step = 1
		1:  # wait for the level + player to settle (wipe out + in, then 0.2s of standing)
			var ready_now = shared.map_name == "1/2" and shared.player != null and bool(shared.player.spr_easy.show) and bool(shared.player.has_safe)
			if ready_now or _t > 8.0:
				_player = shared.player
				_check(_player != null, "Shared.player exists in the level")
				if _player == null:
					_finish()
					return false
				_check(shared.map_name == "1/2", "map_name is 1/2 (got %s)" % shared.map_name)
				_check(revive.remaining(shared.map_name) == 3, "3 free revives to start")
				var cut = get_root().get_node_or_null("Cutscene")
				var wipe = get_root().get_node_or_null("Wipe")
				print("  .. diag pos=%s vel=%s is_floor=%s stand_clock=%s cutscene=%s wipe=%s spr_show=%s spr_less=%s" % [str(_player.global_position), str(_player.velocity), str(_player.is_floor), str(_player.stand_clock), str(cut.is_playing) if cut else "?", str(wipe.is_wipe) if wipe else "?", str(_player.spr_easy.show), str(_player.spr_easy.is_less)])
				_check(bool(_player.has_safe), "a safe stand was recorded once the player touched the floor")
				_safe = _player.safe_pos
				_player.die()
				_t = 0.0
				_step = 2
		2:  # death animation ends -> prompt, no reload
			if _t > 1.2:
				_check(prompt.is_open, "the revive prompt opens after the death animation")
				_check(bool(_player.is_dead) and bool(_player.is_revive_prompt), "the player is held in the dead state while the prompt is up")
				_check(prompt.revive_button.visible, "the REVIVE button is offered")
				_check(shared.map_name == "1/2" and shared.player == _player, "no level reload happened while the prompt was up")
				prompt.revive_button.emit_signal("pressed")
				_check(not prompt.is_open, "the prompt closes when REVIVE is tapped")
				_t = 0.0
				_step = 3
		3:  # revived at the safe stand with grace
			if _t > 0.2:
				_check(not bool(_player.is_dead), "the player is alive again")
				_check(_player.global_position.distance_to(_safe) < 2.0, "revived at the last safe stand (%s vs %s)" % [_player.global_position, _safe])
				_check(float(_player.revive_grace) > 0.0, "grace period is running")
				_check(revive.remaining(shared.map_name) == 2, "one revive consumed (2 left)")
				_player.die()
				_check(not bool(_player.is_dead), "dying during grace is ignored")
				_revives_done = 1
				_t = 0.0
				_step = 4
		4:  # burn the remaining revives
			if _t > 1.8 and float(_player.revive_grace) == 0.0:
				if _revives_done < 3:
					if not bool(_player.is_dead):
						_player.die()
					elif bool(_player.is_revive_prompt) and prompt.is_open:
						prompt.revive_button.emit_signal("pressed")
						_revives_done += 1
						_t = 0.0
				else:
					_check(revive.remaining(shared.map_name) == 0, "all 3 daily revives used")
					_player.die()
					_t = 0.0
					_step = 5
		5:  # 4th death: allowance spent -> no prompt, the level simply reloads (a paid tier can hook in here later)
			if _t > 1.6:
				_check(not prompt.is_open, "no prompt once the daily allowance is spent")
				_check(_reload_seen, "dying with 0 revives left reloads the level directly")
				_check(not bool(shared.player.is_dead), "the player is alive after that reload")
				_reload_seen = false
				# RESTART button path: die again on a fresh allowance and choose restart
				revive.from_save({})
				_t = 0.0
				_step = 51
		51:
			if _t > 1.0 and not bool(shared.player.is_dead) and bool(shared.player.spr_easy.show) and bool(shared.player.has_safe):
				shared.player.die()
				_t = 0.0
				_step = 52
		52:
			if _t > 1.2:
				_check(prompt.is_open and bool(shared.player.is_revive_prompt), "the prompt opens again with a fresh allowance")
				prompt.restart_button.emit_signal("pressed")
				_check(not prompt.is_open, "the prompt closes when RESTART is tapped")
				_t = 0.0
				_step = 6
		6:
			if _t > 1.5:
				_check(_reload_seen, "RESTART reloads the level")
				_check(not bool(shared.player.is_dead), "the player is alive after the restart")
				_check(revive.remaining("1/2") == 3, "RESTART does not consume a revive")
				# save round-trip + day rollover
				revive.consume("1/2")
				revive.consume("1/2")
				var saved = revive.to_save()
				revive.from_save({})
				_check(revive.remaining("1/2") == 3, "a fresh save has 3 revives")
				revive.from_save(saved)
				_check(revive.remaining("1/2") == 1, "the counter survives a save round-trip")
				revive.day = "2000-01-01"
				_check(revive.remaining("1/2") == 3, "a new day resets the allowance")
				_finish()
	return false


func _finish() -> void:
	if _failures.empty():
		print("Gravity revive test passed.")
		quit()
	else:
		for f in _failures:
			push_error(f)
		quit(1)
