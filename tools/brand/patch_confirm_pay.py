#!/usr/bin/env python3
"""Idempotent (1.4.2): no accidental purchases, and the death prompt owns the screen.

What happened on the phone: the touch controls stayed active under the death prompt (the boot button
lit up pink in the screenshot) and the prompt mapped ui_accept -> BUY, so a tap on a game button
re-opened the wallet 1.3 s after the player had cancelled. Fixes:
  - RevivePrompt hides the touch controls while open (TouchScreen.set_game(false)), like the pause menu
  - ui_accept never buys; only an explicit tap does
  - BUY first shows a confirmation: "Pay 100 SKR with your Seeker wallet?" [PAY 100 SKR] [BACK]; the
    wallet opens only from PAY
  - after a failed/cancelled payment BUY is ignored for 1.5 s (no double-tap purchases)
  - the paid button reads "PAY 100 SKR TO REVIVE" so it cannot be mistaken for the free revive
"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]

# ── scene: a PAY button next to CANCEL in the waiting box ──────────────────────────────────────
t = ROOT / "src" / "menu" / "RevivePrompt.tscn"
s = t.read_text(encoding="utf-8")
if "PayButton" not in s:
    old = '''[node name="CancelButton" type="Button" parent="Center/Panel/VBox/Waiting/WaitButtons"]
margin_right = 200.0
margin_bottom = 62.0
rect_min_size = Vector2( 200, 62 )
custom_fonts/font = ExtResource( 1 )
text = "CANCEL"
'''
    assert old in s
    new = old + '''
[node name="PayButton" type="Button" parent="Center/Panel/VBox/Waiting/WaitButtons"]
margin_left = 220.0
margin_right = 560.0
margin_bottom = 62.0
rect_min_size = Vector2( 340, 62 )
custom_styles/normal = SubResource( 2 )
custom_styles/hover = SubResource( 2 )
custom_styles/pressed = SubResource( 2 )
custom_styles/focus = SubResource( 2 )
custom_fonts/font = ExtResource( 1 )
custom_colors/font_color = Color( 0.15, 0.08, 0, 1 )
text = "PAY 100 SKR"
'''
    s = s.replace(old, new, 1)
    s = s.replace('text = "REVIVE  -  100 SKR"', 'text = "PAY 100 SKR TO REVIVE"', 1)
    t.write_text(s, encoding="utf-8", newline="\n")
    print("RevivePrompt.tscn: PAY button + clearer buy label")
else:
    print("RevivePrompt.tscn: already patched")

# ── script ─────────────────────────────────────────────────────────────────────────────────────
g = ROOT / "src" / "menu" / "RevivePrompt.gd"
s = g.read_text(encoding="utf-8")
if "is_confirm" not in s:
    s = s.replace('onready var cancel_button: Button = $Center/Panel/VBox/Waiting/WaitButtons/CancelButton\n',
                  'onready var cancel_button: Button = $Center/Panel/VBox/Waiting/WaitButtons/CancelButton\n'
                  'onready var pay_button: Button = $Center/Panel/VBox/Waiting/WaitButtons/PayButton\n', 1)
    s = s.replace('var is_waiting := false\n',
                  'var is_waiting := false\n'
                  'var is_confirm := false      # "Pay 100 SKR?" step between BUY and the wallet\n'
                  'var _buy_block_until := 0.0  # ignore BUY briefly after a failure (no double-tap purchases)\n', 1)
    s = s.replace('\tcancel_button.connect("pressed", self, "_on_cancel")\n',
                  '\tcancel_button.connect("pressed", self, "_on_cancel")\n'
                  '\tpay_button.connect("pressed", self, "_on_pay")\n', 1)

    # open/close own the touch layer like MenuPause does
    s = s.replace('''func open(p_map_name: String) -> void:
	map_name = p_map_name
	is_open = true
	is_waiting = false
	visible = true
	_refresh()
''', '''func open(p_map_name: String) -> void:
	map_name = p_map_name
	is_open = true
	is_waiting = false
	is_confirm = false
	visible = true
	_touch_controls(false)
	_refresh()
''', 1)
    s = s.replace('''func close() -> void:
	is_open = false
	is_waiting = false
	visible = false
''', '''func close() -> void:
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
''', 1)

    # refresh: waiting box serves both the confirm step and the waiting step
    s = s.replace('''	buttons_box.visible = not is_waiting
	waiting_box.visible = is_waiting
''', '''	buttons_box.visible = not is_waiting and not is_confirm
	waiting_box.visible = is_waiting or is_confirm
	pay_button.visible = is_confirm
	if is_confirm:
		waiting_label.text = "Pay %d SKR with your Seeker wallet to revive here?" % _revive.PRICE_SKR
''', 1)
    s = s.replace('''		buy_button.text = "REVIVE  -  %d SKR" % _revive.PRICE_SKR
''', '''		buy_button.text = "PAY %d SKR TO REVIVE" % _revive.PRICE_SKR
''', 1)
    s = s.replace('''	if is_waiting:
		cancel_button.grab_focus()
''', '''	if is_confirm:
		pay_button.grab_focus()
	elif is_waiting:
		cancel_button.grab_focus()
''', 1)

    # input: ui_accept never buys
    s = s.replace('''	if event.is_action_pressed("ui_cancel"):
		get_tree().set_input_as_handled()
		if is_waiting:
			_on_cancel()
		else:
			_on_restart()
	elif event.is_action_pressed("ui_accept"):
		get_tree().set_input_as_handled()
		if is_waiting:
			return
		if revive_button.visible:
			_on_revive()
		elif buy_button.visible:
			_on_buy()
		else:
			_on_restart()
''', '''	if event.is_action_pressed("ui_cancel"):
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
''', 1)

    # buy -> confirm; pay -> wallet; cancel handles both steps
    s = s.replace('''func _on_buy() -> void:
	if !is_open or is_waiting or _revive == null:
		return
	is_waiting = true
''', '''func _on_buy() -> void:
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
''', 1)
    s = s.replace('''func _on_cancel() -> void:
	if !is_open or !is_waiting:
		return
	is_waiting = false
	if _revive != null:
		_revive.cancel_purchase()
	_refresh()
''', '''func _on_cancel() -> void:
	if !is_open or not (is_waiting or is_confirm):
		return
	var was_waiting := is_waiting
	is_waiting = false
	is_confirm = false
	if was_waiting and _revive != null:
		_revive.cancel_purchase()
	_buy_block_until = OS.get_ticks_msec() / 1000.0 + 1.5
	_refresh()
''', 1)
    s = s.replace('''func _on_purchase_failed(reason: String) -> void:
	if is_open and is_waiting:
		is_waiting = false
		_refresh()
''', '''func _on_purchase_failed(reason: String) -> void:
	if is_open and is_waiting:
		is_waiting = false
		_buy_block_until = OS.get_ticks_msec() / 1000.0 + 1.5
		_refresh()
''', 1)
    for must in ["func _on_pay()", "_touch_controls(false)", "is_confirm = true", "_buy_block_until"]:
        assert must in s, "patch incomplete: " + must
    g.write_text(s, encoding="utf-8", newline="\n")
    print("RevivePrompt.gd: confirm step, no accept-buy, touch controls hidden, debounce")
else:
    print("RevivePrompt.gd: already patched")

# ── paid test: BUY now leads to the confirm step; PAY opens the wallet ──────────────────────────
tp = ROOT / "tools" / "brand" / "test_paid_revive_rota.gd"
u = tp.read_text(encoding="utf-8")
if "pay_button" not in u:
    u = u.replace('''				prompt.buy_button.emit_signal("pressed")
				_t = 0.0
				_step = 3
		3:
			if _t > 0.3:
				_check(not prompt.is_waiting and prompt.buy_button.visible, "without a wallet plugin BUY fails straight back to the prompt")''',
                  '''				prompt.buy_button.emit_signal("pressed")
				_check(prompt.is_confirm and prompt.pay_button.visible and not prompt.buttons_box.visible, "BUY asks for confirmation first")
				_check("Pay 100 SKR" in prompt.waiting_label.text, "confirmation names the price: %s" % prompt.waiting_label.text)
				prompt.cancel_button.emit_signal("pressed")
				_check(not prompt.is_confirm and prompt.buy_button.visible, "BACK from the confirmation returns to the prompt without paying")
				_check(revive.pending_ref == "", "no order was created by just looking at the confirmation")
				prompt._buy_block_until = 0.0
				prompt.buy_button.emit_signal("pressed")
				prompt.pay_button.emit_signal("pressed")
				_t = 0.0
				_step = 3
		3:
			if _t > 0.3:
				_check(not prompt.is_waiting and prompt.buy_button.visible, "without a wallet plugin PAY fails straight back to the prompt")''', 1)
    # every later BUY press must go through PAY as well
    u = u.replace('''				_seen_steps = []
				prompt.buy_button.emit_signal("pressed")
				_check(prompt.is_waiting and prompt.waiting_box.visible and not prompt.buttons_box.visible, "BUY switches to the waiting screen")''',
                  '''				_seen_steps = []
				prompt._buy_block_until = 0.0
				prompt.buy_button.emit_signal("pressed")
				prompt.pay_button.emit_signal("pressed")
				_check(prompt.is_waiting and prompt.waiting_box.visible and not prompt.buttons_box.visible, "PAY switches to the waiting screen")''', 1)
    u = u.replace('''				# ── Part C: wallet hangs -> CANCEL -> retry succeeds via polled status ───
				_fake.outcome = "hang"
				prompt.buy_button.emit_signal("pressed")''',
                  '''				# ── Part C: wallet hangs -> CANCEL -> retry succeeds via polled status ───
				_fake.outcome = "hang"
				_check(OS.get_ticks_msec() / 1000.0 < prompt._buy_block_until, "BUY is blocked briefly right after a failure")
				prompt._buy_block_until = 0.0
				prompt.buy_button.emit_signal("pressed")
				prompt.pay_button.emit_signal("pressed")''', 1)
    u = u.replace('''				_fake.outcome = "done"
				prompt.buy_button.emit_signal("pressed")
				_check(revive.pending_ref == ref_before, "retry reuses the same pending order")''',
                  '''				_fake.outcome = "done"
				prompt._buy_block_until = 0.0
				prompt.buy_button.emit_signal("pressed")
				prompt.pay_button.emit_signal("pressed")
				_check(revive.pending_ref == ref_before, "retry reuses the same pending order")''', 1)
    u = u.replace('_check("100 SKR" in prompt.buy_button.text, "price on the button (%s)" % prompt.buy_button.text)',
                  '_check("PAY 100 SKR" in prompt.buy_button.text, "price on the button (%s)" % prompt.buy_button.text)', 1)
    tp.write_text(u, encoding="utf-8", newline="\n")
    print("paid test: confirm step wired in")
else:
    print("paid test: already patched")
