extends SceneTree

# Paid revive regression test (Godot 3.6, --no-window). Wallet-only flow, no browser anywhere.
# Needs the mock status server running WITHOUT ever reporting paid (so only the wallet path can grant):
#   python tools/brand/mock_pay_server.py 8765 999
#   Godot_v3.6.1-stable_win64.exe --no-window --path . --script res://tools/brand/test_paid_revive_rota.gd res://tools/brand/TestDummy.tscn
#
# Part A  no wallet plugin        -> BUY fails at once with a clear reason, order stays pending
# Part B  wallet declines         -> pay() called with the right arguments, live steps shown, reason + wallet
#                                    diagnosis shown, order stays pending
# Part C  wallet hangs            -> CANCEL abandons the attempt (plugin cancel() called), BUY again succeeds
#                                    via the POLLED status (no signal needed) -> REVIVE HERE (paid) -> revived
# Part D  save round-trip of the pending order; purchases disabled -> death reloads the level directly
# Same headless rules as test_revive_rota.gd (runtime autoload lookup, dummy scene, wipe path).

const LEVEL := "res://src/map/worlds/1/2.tscn"
const MOCK := "http://127.0.0.1:8765"


# Stand-in for the SeekerWallet Android plugin: same methods and signals. Emits NO signal in
# "done" mode so the test proves the polled getStatus() path alone is enough.
class FakeWallet extends Node:
	signal pay_done(ref, signature)
	signal pay_failed(ref, reason)
	var calls := []
	var cancels := 0
	var outcome := "done"   # "done" | "declined" | "hang"
	var _status := "idle|"

	func isAvailable() -> bool:
		return true

	func isBusy() -> bool:
		return _status.begins_with("working|")

	func diagnose() -> String:
		return "wallets: com.example.fakewallet | cleartext=true"

	func getStatus() -> String:
		return _status

	func cancel() -> void:
		cancels += 1
		_status = "idle|"

	func pay(base_url: String, ref: String, product: String, identity_name: String, identity_uri: String, icon_uri: String) -> void:
		calls.append([base_url, ref, product, identity_name, identity_uri, icon_uri])
		_status = "working|opening wallet"
		yield(get_tree().create_timer(0.7), "timeout")
		_status = "working|connecting to wallet"
		yield(get_tree().create_timer(0.3), "timeout")
		if outcome == "hang":
			return
		if outcome == "declined":
			_status = "failed|You cancelled the payment in the wallet."
			emit_signal("pay_failed", ref, "You cancelled the payment in the wallet.")
		else:
			_status = "done|5FAKEsignature"


var _failures := []
var _step := 0
var _t := 0.0
var _total := 0.0
var shared = null
var revive = null
var prompt = null
var _player = null
var _safe := Vector2.ZERO
var _scene_changes := 0
var _fake: FakeWallet = null
var _seen_steps := []


func _check(ok: bool, msg: String) -> void:
	if ok:
		print("  ok   " + msg)
	else:
		_failures.append(msg)
		print("  FAIL " + msg)


func _on_scene_changed() -> void:
	_scene_changes += 1


func _on_step(step: String) -> void:
	_seen_steps.append(step)


func _player_ready() -> bool:
	return shared.map_name == "1/2" and shared.player != null and bool(shared.player.spr_easy.show) and bool(shared.player.has_safe)


func _idle(delta: float) -> bool:
	_t += delta
	_total += delta
	if _total > 120.0:
		_check(false, "WATCHDOG: step=%d t=%.1f pending=%s credits=%s waiting=%s" % [_step, _t, str(revive.pending_ref) if revive else "?", str(revive.paid_credits("1/2")) if revive else "?", str(prompt.is_waiting) if prompt else "?"])
		_finish()
		return false
	match _step:
		0:
			shared = get_root().get_node_or_null("Shared")
			revive = get_root().get_node_or_null("Revive")
			prompt = get_root().get_node_or_null("RevivePrompt")
			if shared == null or revive == null or prompt == null:
				if _t > 5.0:
					_check(false, "autoloads not found")
					_finish()
				return false
			shared.connect("scene_changed", self, "_on_scene_changed")
			revive.connect("purchase_step", self, "_on_step")
			revive.pay_base_url = MOCK
			revive.purchases_enabled = true
			shared.call_deferred("wipe_scene", LEVEL)
			_t = 0.0
			_step = 1
		# ── Part A: no wallet plugin ───────────────────────────────────────────────────
		1:
			if _player_ready() or _t > 8.0:
				_player = shared.player
				_check(_player != null and bool(_player.has_safe), "level loaded, player standing")
				revive.from_save({"day": revive.today(), "used": {"1/2": 3}})
				_check(revive.remaining("1/2") == 0 and revive.can_offer("1/2"), "no free revives left, but a paid one can be offered")
				_check(not revive.has_wallet(), "no wallet plugin in the headless run")
				_safe = _player.safe_pos
				_player.die()
				_t = 0.0
				_step = 2
		2:
			if _t > 1.2:
				_check(prompt.is_open and prompt.buy_button.visible and not prompt.revive_button.visible, "prompt offers REVIVE - 100 SKR only")
				_check("PAY 100 SKR" in prompt.buy_button.text, "price on the button (%s)" % prompt.buy_button.text)
				prompt.buy_button.emit_signal("pressed")
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
				_check(not prompt.is_waiting and prompt.buy_button.visible, "without a wallet plugin PAY fails straight back to the prompt")
				_check("No Seeker wallet plugin" in prompt.info_label.text, "the reason is shown: %s" % prompt.info_label.text.split("\n")[0])
				_check(revive.pending_ref.length() == 32 and revive.pending_map == "1/2", "the order stays pending")
				# ── Part B: wallet declines ──────────────────────────────────────────────
				_fake = FakeWallet.new()
				get_root().add_child(_fake)
				revive.wallet_override = _fake
				_fake.outcome = "declined"
				_check(revive.has_wallet(), "wallet plugin detected once present")
				_seen_steps = []
				prompt._buy_block_until = 0.0
				prompt.buy_button.emit_signal("pressed")
				prompt.pay_button.emit_signal("pressed")
				_check(prompt.is_waiting and prompt.waiting_box.visible and not prompt.buttons_box.visible, "PAY switches to the waiting screen")
				_check(_fake.calls.size() == 1, "the plugin's pay() was called once")
				if _fake.calls.size() == 1:
					var c = _fake.calls[0]
					_check(c[0] == MOCK and c[1] == revive.pending_ref and c[2] == "revive", "pay(base_url, ref, product) carries our server, the pending order and 'revive'")
					_check(c[3] == "Seeker Gravity" and c[4] == MOCK and c[5] == "/static/icon-512.png", "wallet identity: name, uri, root-relative icon (%s)" % c[5])
				_t = 0.0
				_step = 4
		4:  # steps flow to the screen, then the decline comes back
			if not prompt.is_waiting or _t > 6.0:
				_check(_seen_steps.size() >= 1 and _seen_steps.has("connecting to wallet"), "live steps reached the game (polled every 0.5s): %s" % str(_seen_steps))
				_check(not prompt.is_waiting and prompt.buy_button.visible, "a declined payment returns to the prompt")
				_check("cancelled" in prompt.info_label.text, "the reason is shown")
				_check("wallets: com.example.fakewallet" in prompt.info_label.text, "the wallet diagnosis is shown with it")
				_check(revive.pending_ref != "" and revive.paid_credits("1/2") == 0, "order still pending, no credit")
				# ── Part C: wallet hangs -> CANCEL -> retry succeeds via polled status ───
				_fake.outcome = "hang"
				_check(OS.get_ticks_msec() / 1000.0 < prompt._buy_block_until, "BUY is blocked briefly right after a failure")
				prompt._buy_block_until = 0.0
				prompt.buy_button.emit_signal("pressed")
				prompt.pay_button.emit_signal("pressed")
				_t = 0.0
				_step = 5
		5:
			if _t > 1.2:
				_check(prompt.is_waiting and "Connecting" in prompt.waiting_label.text, "waiting screen shows the live step: %s" % prompt.waiting_label.text)
				var ref_before = revive.pending_ref
				prompt.cancel_button.emit_signal("pressed")
				_check(not prompt.is_waiting and prompt.buy_button.visible, "CANCEL returns to the prompt")
				_check(_fake.cancels == 1, "CANCEL told the plugin to abandon the stuck attempt")
				_check(revive.pending_ref == ref_before, "the order stays pending after cancel")
				_fake.outcome = "done"
				prompt._buy_block_until = 0.0
				prompt.buy_button.emit_signal("pressed")
				prompt.pay_button.emit_signal("pressed")
				_check(revive.pending_ref == ref_before, "retry reuses the same pending order")
				_check(_fake.calls.size() == 3, "pay() called for the third time")
				_t = 0.0
				_step = 6
		6:  # done is reported through getStatus() polling only (the fake emits no signal in done mode)
			if not bool(_player.is_dead) or _t > 6.0:
				_check(not prompt.is_open, "auto-revive: the prompt closed itself when the payment was confirmed")
				_check(not bool(_player.is_dead) and _player.global_position.distance_to(_safe) < 2.0, "revived in place without tapping anything")
				_check(revive.paid_credits("1/2") == 0 and revive.pending_ref == "", "the paid credit was consumed by that revive, order closed")
				_check(revive.remaining("1/2") == 0, "free counter untouched")
				_t = 0.0
				_step = 8
		# ── Part D: pending survives a save; offline behaviour ────────────────────────
		8:
			if _t > 1.8 and float(_player.revive_grace) == 0.0:
				revive.from_save({"day": revive.today(), "used": {"1/2": 3}, "pending": {"ref": "ab" + "cd".repeat(15), "map": "1/2", "since": OS.get_unix_time()}})
				var saved = revive.to_save()
				revive.from_save({})
				_check(revive.pending_ref == "", "a fresh save has no pending order")
				revive.from_save(saved)
				_check(revive.pending_ref.length() == 32 and revive.pending_map == "1/2" and int(saved["used"]["1/2"]) == 3, "pending order + free counter survive a save round-trip")
				revive.from_save({"day": revive.today(), "used": {"1/2": 3}})
				revive.wallet_override = null
				revive.purchases_enabled = false
				_check(not revive.can_offer("1/2"), "nothing to offer when purchases are disabled and the free revives are gone")
				set_meta("before", _scene_changes)
				_player.die()
				_t = 0.0
				_step = 9
		9:
			if _t > 1.8:
				_check(not prompt.is_open, "no prompt in that case")
				_check(_scene_changes > int(get_meta("before")), "the level reloaded directly")
				_finish()
	return false


func _finish() -> void:
	if _failures.empty():
		print("Gravity paid revive test passed.")
		quit()
	else:
		for f in _failures:
			push_error(f)
		quit(1)
