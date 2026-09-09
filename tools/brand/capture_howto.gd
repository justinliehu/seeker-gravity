extends SceneTree
# Render the How to Play page and the first-level tip to PNG so they can be checked without a phone.
# Run WITHOUT --no-window (needs a real renderer):
#   Godot_v3.6.1-stable_win64.exe --path . --script res://tools/brand/capture_howto.gd
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
	var howto = _auto("MenuHowTo")
	var tip = _auto("Tip")
	var shared = _auto("Shared")
	if howto == null or tip == null or shared == null:
		print("autoloads missing")
		quit(1)
		return false
	match _step:
		0:
			if _t > 0.5:
				change_scene(shared.title_path)
				_t = 0.0
				_step = 1
		1:
			if _t > 2.5:
				howto.is_open = true
				_t = 0.0
				_step = 2
		2:
			if _t > 1.5:
				_shot("howto")
				howto.is_open = false
				_t = 0.0
				_step = 3
		3:
			if _t > 1.0:
				change_scene(shared.start_path)   # the first level itself, without the opening cutscene
				_t = 0.0
				_step = 5
		5:
			if _t > 3.5:
				tip.forget()
				tip.show_tip("gravity", "Walk off an edge: gravity turns with you")
				_t = 0.0
				_step = 4
		4:
			if _t > 1.2:
				_shot("tip")
				print("done")
				quit()
	return false
