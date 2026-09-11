extends SceneTree
# Render the death prompt in its three states (free revive, paid offer, wallet waiting) to PNG.
# Run WITHOUT --no-window (needs a real renderer):
#   Godot_v3.6.1-stable_win64.exe --path . --script res://tools/brand/capture_revive.gd
# Autoloads are looked up at runtime: naming them directly in a --script file breaks their loading.

const OUT_DIR := "res://store-assets/screenshots-howto"

var _step := 0
var _t := 0.0


func _initialize() -> void:
	var dir := Directory.new()
	dir.make_dir_recursive(ProjectSettings.globalize_path(OUT_DIR))
	OS.window_size = Vector2(1280, 720)


func _auto(n: String):
	return get_root().get_node_or_null(n)


func _shot(name: String) -> void:
	var img: Image = get_root().get_texture().get_data()
	img.flip_y()
	var path := "%s/%s.png" % [OUT_DIR, name]
	print("Captured %s %s (%s)" % [path, img.get_size(), "ok" if img.save_png(path) == OK else "fail"])


func _idle(delta: float) -> bool:
	_t += delta
	var shared = _auto("Shared")
	var revive = _auto("Revive")
	var prompt = _auto("RevivePrompt")
	if shared == null or revive == null or prompt == null:
		print("autoloads missing")
		quit(1)
		return false
	match _step:
		0:
			if _t > 0.5:
				change_scene(shared.start_path)
				_t = 0.0
				_step = 1
		1:
			if _t > 3.0:
				revive.purchases_enabled = true
				revive.from_save({})
				shared.map_name = "0/1_start"
				prompt.open(shared.map_name)
				_t = 0.0
				_step = 2
		2:
			if _t > 1.0:
				_shot("revive-free")
				# use the three free revives up so the paid offer is the only thing left
				revive.used[shared.map_name] = 3
				prompt._refresh()
				_t = 0.0
				_step = 3
		3:
			if _t > 0.8:
				_shot("revive-paid")
				prompt._on_buy()          # the confirmation step
				_t = 0.0
				_step = 4
		4:
			if _t > 0.8:
				_shot("revive-confirm")
				prompt.close()
				print("done")
				quit()
	return false
