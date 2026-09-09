extends SceneTree

# "How to Play" + first-level tip test (Godot 3.6, --no-window):
#   Godot_v3.6.1-stable_win64.exe --no-window --path . --script res://tools/brand/test_howto.gd res://tools/brand/TestDummy.tscn

var _failures := []
var _t := 0.0
var _step := 0
var _title = null


func _check(ok: bool, msg: String) -> void:
	if ok:
		print("  ok   " + msg)
	else:
		_failures.append(msg)
		print("  FAIL " + msg)


func _auto(n: String):
	return get_root().get_node_or_null(n)


func _names(menu) -> Array:
	var out := []
	for i in menu.items:
		out.append(i.name)
	return out


func _idle(delta: float) -> bool:
	_t += delta
	var howto = _auto("MenuHowTo")
	var tip = _auto("Tip")
	var pause = _auto("MenuPause")
	var shared = _auto("Shared")
	match _step:
		0:
			if _t < 0.4:
				return false
			if howto == null or tip == null or pause == null or shared == null:
				_check(false, "autoloads MenuHowTo / Tip / MenuPause / Shared present")
				_finish()
				return false
			_check(true, "autoloads MenuHowTo and Tip present")

			# ── the page itself ──
			var vbox = howto.get_node("Fade/Center/Panel/VBox")
			_check(vbox.get_node("Title").text == "HOW TO PLAY", "page title reads HOW TO PLAY")
			var rows := 0
			for n in vbox.get_node("Controls").get_children():
				if n is TextureRect and n.texture != null:
					rows += 1
			_check(rows == 4, "four control rows with an icon each (%d)" % rows)
			var rules: String = vbox.get_node("Rules").text
			_check("gravity" in rules and "block" in rules and "gems" in rules, "rules cover gravity, blocks and gems")
			shared.is_mobile = true
			howto._ready()
			_check("buttons on the screen" in vbox.get_node("Note").text, "mobile note points at the on-screen buttons")
			shared.is_mobile = false
			howto._ready()
			_check("Options" in vbox.get_node("Note").text, "desktop note points at Options")

			# ── opens from the pause menu and gives it back ──
			pause.set_open(true, false)
			var pnames := _names(pause)
			_check(pnames.has("HowTo"), "pause menu lists How to Play: %s" % str(pnames))
			pause.cursor = pnames.find("HowTo")
			pause.accept()
			_check(bool(howto.is_open) and bool(pause.is_sub_menu), "pause -> How to Play opens as a sub-menu")
			howto.is_open = false
			_check(not bool(howto.is_open) and not bool(pause.is_sub_menu) and bool(pause.is_open), "closing it returns to the pause menu")
			pause.set_open(false, false)

			# ── the tip ──
			tip.forget()
			tip._clock = -1.0
			shared.map_name = "3/2_room"
			_t = 0.0
			_step = 1
		1:
			if _t < 0.3:
				return false
			_check(not tip.is_showing(), "no tip in a later level")
			shared.map_name = tip.FIRST_MAP
			_t = 0.0
			_step = 2
		2:
			if _t < 0.3:
				return false
			_check(tip.is_showing() and tip.fade.visible, "tip appears in the first level")
			_check("edge" in tip.label.text and "gravity" in tip.label.text, "tip names the mechanic: %s" % tip.label.text)
			_check(tip.seen.has("gravity"), "tip marked as seen")
			var f := File.new()
			_check(f.file_exists("user://tips.json"), "seen flag persisted to user://tips.json")
			# it fades out on its own
			tip._clock = tip.FADE_IN + tip.HOLD + tip.FADE_OUT + 0.1
			_t = 0.0
			_step = 3
		3:
			if _t < 0.3:
				return false
			_check(not tip.is_showing() and not tip.fade.visible, "tip fades out on its own")
			shared.map_name = ""
			_t = 0.0
			_step = 4
		4:
			if _t < 0.2:
				return false
			shared.map_name = tip.FIRST_MAP
			_t = 0.0
			_step = 5
		5:
			if _t < 0.4:
				return false
			_check(not tip.is_showing(), "tip never shows a second time")
			# a fresh start teaches again
			tip.forget()
			_check(not tip.seen.has("gravity"), "erasing a slot forgets the tip")
			_t = 0.0
			_step = 6
		6:
			if _t < 0.4:
				return false
			_check(tip.is_showing(), "after forgetting, the first level teaches again")
			tip._clock = -1.0
			tip.fade.visible = false
			# ── the title menu also offers it ──
			change_scene(shared.title_path)
			_t = 0.0
			_step = 7
		7:
			if _t < 1.2:
				return false
			for n in get_root().get_children():
				_title = _find_title(n)
				if _title != null:
					break
			if _title == null:
				_check(false, "title menu found in the title scene")
				_finish()
				return false
			_title.fill_items()
			var tnames := _names(_title)
			_check(tnames.has("HowTo"), "title menu lists How to Play: %s" % str(tnames))
			_title.cursor = tnames.find("HowTo")
			_title.accept()
			_check(bool(howto.is_open), "title -> How to Play opens")
			howto.is_open = false
			_finish()
	return false


func _find_title(node):
	if node.get_script() != null and str(node.get_script().resource_path).ends_with("MenuTitle.gd"):
		return node
	for c in node.get_children():
		var r = _find_title(c)
		if r != null:
			return r
	return null


func _finish() -> void:
	if _failures.empty():
		print("How-to-play test passed.")
		quit()
	else:
		for f in _failures:
			push_error(f)
		quit(1)
