extends SceneTree

# Godot 3.x: render the title screen and a few frames later dump the viewport to PNG so the
# reskin can be eyeballed without a phone. Run WITHOUT --no-window (needs a real renderer):
#   Godot_v3.6.1-stable_win64.exe --path . --script res://tools/brand/capture_title.gd

const OUTPUT_DIR := "res://store-assets/screenshots"
const CAPTURES := [
	{"scene": "res://src/menu/MenuTitle.tscn", "output": "title.png", "frames": 90},
	{"scene": "res://src/map/worlds/1/0_hub.tscn", "output": "world1.png", "frames": 120},
	{"scene": "res://src/map/worlds/3/0_hub.tscn", "output": "world3.png", "frames": 120},
	{"scene": "res://src/map/worlds/3A/0_hub.tscn", "output": "world3a.png", "frames": 120},
	{"scene": "res://src/map/worlds/3B/0_hub.tscn", "output": "world3b.png", "frames": 120},
	{"scene": "res://src/map/worlds/2B/0_hub.tscn", "output": "world2b.png", "frames": 120},
	{"scene": "res://src/map/worlds/2C/0_hub.tscn", "output": "world2c.png", "frames": 120},
]

var _index := 0
var _frames_left := 0
var _current: Node = null


func _initialize() -> void:
	var dir := Directory.new()
	dir.make_dir_recursive(ProjectSettings.globalize_path(OUTPUT_DIR))
	OS.window_size = Vector2(1920, 1080)
	_start_next()


func _start_next() -> void:
	if _current != null:
		_current.queue_free()
		_current = null
	if _index >= CAPTURES.size():
		print("Captures written to %s" % OUTPUT_DIR)
		quit()
		return
	var cap: Dictionary = CAPTURES[_index]
	var packed := load(cap["scene"]) as PackedScene
	if packed == null:
		push_error("could not load %s" % cap["scene"])
		quit(1)
		return
	_current = packed.instance()
	get_root().add_child(_current)
	current_scene = _current
	_frames_left = int(cap["frames"])


func _idle(_delta: float) -> bool:
	if _current == null:
		return false
	_frames_left -= 1
	if _frames_left > 0:
		return false
	var img: Image = get_root().get_texture().get_data()
	img.flip_y()
	var out := "%s/%s" % [OUTPUT_DIR, CAPTURES[_index]["output"]]
	var err := img.save_png(out)
	print("Captured %s (%s)" % [out, "ok" if err == OK else str(err)])
	_index += 1
	_start_next()
	return false
