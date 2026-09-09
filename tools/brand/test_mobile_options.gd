extends SceneTree

# Phone-fit options menu test (Godot 3.6, --no-window):
#   Godot_v3.6.1-stable_win64.exe --no-window --path . --script res://tools/brand/test_mobile_options.gd res://tools/brand/TestDummy.tscn
# mobile: keyboard/window rows hidden, phone-relevant rows kept, slider tick logic index-independent;
# desktop: keyboard row back; pause menu never lists the dead Store Page.

var _failures := []
var _t := 0.0


func _check(ok: bool, msg: String) -> void:
	if ok:
		print("  ok   " + msg)
	else:
		_failures.append(msg)
		print("  FAIL " + msg)


func _names(menu) -> Array:
	var out := []
	for i in menu.items:
		out.append(i.name)
	return out


func _idle(delta: float) -> bool:
	_t += delta
	if _t < 0.5:
		return false
	var shared = get_root().get_node_or_null("Shared")
	var options = get_root().get_node_or_null("MenuOptions")
	var pause = get_root().get_node_or_null("MenuPause")
	if shared == null or options == null or pause == null:
		_check(false, "autoloads Shared/MenuOptions/MenuPause not found")
		_finish()
		return false

	# ── phone ──
	shared.is_mobile = true
	options.fill_items()
	var names := _names(options)
	for hidden in ["Keyboard", "Controller", "Fullscreen", "Borderless", "Resolution", "Mouse", "Vsync"]:
		_check(not names.has(hidden), "mobile hides %s" % hidden)
	for kept in ["Touch", "X", "Y", "Music", "SFX", "Interpolate", "TargetFPS", "RadialBlur"]:
		_check(names.has(kept), "mobile keeps %s" % kept)
	_check(not names.has("HeaderInput") and not names.has("Header"), "headers are not navigable items")
	# slider tick decided per row, not by index
	options.cursor = names.find("Touch")
	options.row()
	_check(bool(options.is_audio_joy), "left/right tick on a value row (Touch Screen)")

	# ── desktop ──
	shared.is_mobile = false
	options.fill_items()
	names = _names(options)
	_check(names.has("Keyboard") and names.has("Controller"), "desktop shows Keyboard Setup and Controller Setup again")
	options.cursor = names.find("Controller")
	options.row()
	_check(not bool(options.is_audio_joy), "no tick on an action row (Controller Setup)")
	_check(names.has("Vsync") and names.has("Mouse"), "desktop shows V-Sync and Mouse again")

	# ── pause menu: no dead Store Page ──
	shared.is_mobile = true
	pause.set_open(true, false)
	var pnames := _names(pause)
	_check(not pnames.has("Store"), "pause menu does not list Store Page: %s" % str(pnames))
	_check(pnames.has("Options") and pnames.has("Exit"), "pause menu still has Options and Main Menu")
	pause.set_open(false, false)
	_finish()
	return false


func _finish() -> void:
	if _failures.empty():
		print("Mobile options test passed.")
		quit()
	else:
		for f in _failures:
			push_error(f)
		quit(1)
