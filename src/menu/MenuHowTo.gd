extends MenuBase
# The "How to Play" page, opened from the title menu and from the pause menu.
#
# It has no items to pick: any accept or cancel closes it (is_accept_close / is_back_close in the
# scene), so the on-screen touch buttons, a keyboard and a gamepad all work without extra wiring.
# Nothing here interrupts play - the page only exists for a player who goes looking for it.

onready var note_label: Label = $Fade/Center/Panel/VBox/Note


func _ready() -> void:
	._ready()
	# the icons are the on-screen buttons themselves, so only the closing line differs per platform
	note_label.text = "Use the buttons on the screen." if Shared.is_mobile else "Keys can be changed in Options."
