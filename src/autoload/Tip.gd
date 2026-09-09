extends CanvasLayer
# One-line hints that fade in, hold and fade out on their own. Nothing to tap, nothing to dismiss.
#
# The game deliberately has no tutorial; this exists only for the one thing a first-time player cannot
# guess by looking at the screen: that walking off an edge turns gravity. It is shown once ever, and
# the flag lives in its own file so the save slots keep their format.

const SAVE_PATH := "user://tips.json"
const FIRST_MAP := "0/1_start"     # Shared.start_path, relative to Shared.worlds_path
const FADE_IN := 0.6
const HOLD := 5.0
const FADE_OUT := 1.2

onready var fade: Control = $Fade
onready var label: Label = $Fade/Box/Panel/Label

var seen := {}       # tip id -> true
var _clock := -1.0   # -1 = nothing showing


func _ready() -> void:
	fade.modulate.a = 0.0
	fade.visible = false
	_load()


func _process(delta: float) -> void:
	if _clock >= 0.0:
		_clock += delta
		var a := 0.0
		if _clock < FADE_IN:
			a = _clock / FADE_IN
		elif _clock < FADE_IN + HOLD:
			a = 1.0
		elif _clock < FADE_IN + HOLD + FADE_OUT:
			a = 1.0 - (_clock - FADE_IN - HOLD) / FADE_OUT
		else:
			_clock = -1.0
			fade.visible = false
			return
		fade.modulate.a = a
		return
	# the one automatic tip: the player is standing in the first level of a new game
	if not seen.has("gravity") and Shared.map_name == FIRST_MAP \
			and not Cutscene.is_playing and not MenuPause.is_paused and not Wipe.is_wipe:
		show_tip("gravity", "Walk off an edge: gravity turns with you")


func show_tip(id: String, text: String) -> void:
	if seen.has(id):
		return
	seen[id] = true
	_save()   # saved as soon as it is shown, so quitting mid-tip does not repeat it
	label.text = text
	fade.modulate.a = 0.0
	fade.visible = true
	_clock = 0.0


func is_showing() -> bool:
	return _clock >= 0.0


func forget() -> void:
	# a fresh start should teach again (called when a save slot is erased)
	seen = {}
	_save()


func to_save() -> Dictionary:
	return seen.duplicate()


func from_save(d) -> void:
	seen = {}
	if typeof(d) == TYPE_DICTIONARY:
		for k in d.keys():
			seen[str(k)] = true


func _save() -> void:
	var f := File.new()
	if f.open(SAVE_PATH, File.WRITE) == OK:
		f.store_string(JSON.print(to_save()))
		f.close()


func _load() -> void:
	var f := File.new()
	if f.file_exists(SAVE_PATH) and f.open(SAVE_PATH, File.READ) == OK:
		var r := JSON.parse(f.get_as_text())
		f.close()
		if r.error == OK:
			from_save(r.result)
