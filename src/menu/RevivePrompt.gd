extends CanvasLayer

# Shown when the death animation ends and a revive is available or purchasable. Touch buttons plus
# ui_accept / ui_cancel so the on-screen pad and gamepads work. Player decides what happens on
# revive/restart; the purchase itself is driven by the Revive autoload (resolved at runtime so this
# scene also loads in headless tests).

signal revive_chosen
signal restart_chosen

onready var revive_button: Button = $Center/Panel/VBox/Buttons/ReviveButton
onready var restart_button: Button = $Center/Panel/VBox/Buttons/RestartButton
onready var buy_button: Button = $Center/Panel/VBox/Buttons/BuyButton
onready var buttons_box: Control = $Center/Panel/VBox/Buttons
onready var waiting_box: Control = $Center/Panel/VBox/Waiting
onready var waiting_label: Label = $Center/Panel/VBox/Waiting/WaitLabel
onready var cancel_button: Button = $Center/Panel/VBox/Waiting/WaitButtons/CancelButton
onready var pay_button: Button = $Center/Panel/VBox/Waiting/WaitButtons/PayButton
onready var info_label: Label = $Center/Panel/VBox/Info

var is_open := false
var is_waiting := false
var is_confirm := false      # "Pay 100 SKR?" step between BUY and the wallet
var _buy_block_until := 0.0  # ignore BUY briefly after a failure (no double-tap purchases)
var map_name := ""
var _revive = null


func _ready() -> void:
	visible = false
	revive_button.connect("pressed", self, "_on_revive")
	restart_button.connect("pressed", self, "_on_restart")
	buy_button.connect("pressed", self, "_on_buy")
	cancel_button.connect("pressed", self, "_on_cancel")
	pay_button.connect("pressed", self, "_on_pay")
	_revive = get_node_or_null("/root/Revive")
	if _revive != null:
		_revive.connect("purchase_completed", self, "_on_purchase_completed")
		_revive.connect("purchase_failed", self, "_on_purchase_failed")
		_revive.connect("purchase_step", self, "_on_purchase_step")


func open(p_map_name: String) -> void:
	map_name = p_map_name
	is_open = true
	is_waiting = false
	is_confirm = false
	visible = true
	_touch_controls(false)
	_refresh()


func close() -> void:
	is_open = false
	is_waiting = false
	is_confirm = false
	visible = false
	_touch_controls(true)


# the game buttons (jump/grab) must not be tappable under the prompt; pause menu does the same
func _touch_controls(shown: bool) -> void:
	var ts = get_node_or_null("/root/TouchScreen")
	if ts != null and ts.has_method("set_game"):
		ts.set_game(shown)


func _refresh() -> void:
	var free: int = _revive.remaining(map_name) if _revive != null else 0
	var credits: int = _revive.paid_credits(map_name) if _revive != null else 0
	var can_buy: bool = _revive != null and _revive.purchases_enabled and free == 0 and credits == 0
	buttons_box.visible = not is_waiting and not is_confirm
	waiting_box.visible = is_waiting or is_confirm
	pay_button.visible = is_confirm
	if is_confirm:
		waiting_label.text = "Pay %d SKR with your Seeker wallet to revive here?" % _revive.PRICE_SKR
	revive_button.visible = free > 0 or credits > 0
	buy_button.visible = can_buy
	if free > 0:
		revive_button.text = "REVIVE HERE  (%d left today)" % free
		info_label.text = "Continue from where you stood. Blocks and the timer stay as they are."
	elif credits > 0:
		revive_button.text = "REVIVE HERE  (paid x%d)" % credits
		info_label.text = "Payment received. Continue from where you stood."
	elif can_buy:
		buy_button.text = "PAY %d SKR TO REVIVE" % _revive.PRICE_SKR
		info_label.text = "No free revives left today for this level. Pay %d SKR with your Seeker wallet to continue from where you stood." % _revive.PRICE_SKR
	else:
		info_label.text = "No free revives left today for this level."
	if is_confirm:
		pay_button.grab_focus()
	elif is_waiting:
		cancel_button.grab_focus()
	elif revive_button.visible:
		revive_button.grab_focus()
	elif buy_button.visible:
		buy_button.grab_focus()
	else:
		restart_button.grab_focus()


func _unhandled_input(event: InputEvent) -> void:
	if !is_open:
		return
	if event.is_action_pressed("ui_cancel"):
		get_tree().set_input_as_handled()
		if is_waiting or is_confirm:
			_on_cancel()
		else:
			_on_restart()
	elif event.is_action_pressed("ui_accept"):
		get_tree().set_input_as_handled()
		if is_waiting or is_confirm:
			return  # paying is a deliberate tap on PAY, never a generic accept
		if revive_button.visible:
			_on_revive()
		elif not buy_button.visible:
			_on_restart()


func _on_revive() -> void:
	if !is_open or is_waiting:
		return
	close()
	emit_signal("revive_chosen")


func _on_restart() -> void:
	if !is_open or is_waiting:
		return
	close()
	emit_signal("restart_chosen")


func _on_buy() -> void:
	if !is_open or is_waiting or is_confirm or _revive == null:
		return
	if OS.get_ticks_msec() / 1000.0 < _buy_block_until:
		return
	is_confirm = true
	_refresh()


func _on_pay() -> void:
	if !is_open or !is_confirm or _revive == null:
		return
	is_confirm = false
	is_waiting = true
	waiting_label.text = "Opening your Seeker wallet for the %d SKR payment..." % _revive.PRICE_SKR
	_refresh()
	_revive.begin_purchase(map_name)


func _on_cancel() -> void:
	if !is_open or not (is_waiting or is_confirm):
		return
	var was_waiting := is_waiting
	is_waiting = false
	is_confirm = false
	if was_waiting and _revive != null:
		_revive.cancel_purchase()
	_buy_block_until = OS.get_ticks_msec() / 1000.0 + 1.5
	_refresh()


func _on_purchase_completed(p_map_name: String) -> void:
	if is_open and p_map_name == map_name:
		# paid for THIS death -> revive at once; no second menu and no RESTART to mis-tap
		is_waiting = false
		is_confirm = false
		close()
		emit_signal("revive_chosen")


func _on_purchase_failed(reason: String) -> void:
	if is_open and is_waiting:
		is_waiting = false
		_buy_block_until = OS.get_ticks_msec() / 1000.0 + 1.5
		_refresh()
		# the diagnosis makes a screenshot enough to tell where the wallet handshake stopped
		info_label.text = reason + "\n" + _revive.wallet_diagnosis() + "\nTap REVIVE to try again."


# Live progress from the wallet plugin, so the waiting screen never looks frozen.
func _on_purchase_step(step: String) -> void:
	if is_open and is_waiting:
		waiting_label.text = step.capitalize() + "..."
