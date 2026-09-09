#!/usr/bin/env python3
"""Idempotent (1.4.3): a confirmed payment revives immediately. No second menu, no RESTART after paying.

User report: after paying, the prompt showed REVIVE HERE (paid) + RESTART LEVEL; RESTART "still revived in
place" (adjacent buttons, the gold one big and centred - a mis-tap waiting to happen) and there is no
reason to offer a restart after money changed hands. So:
  - when the payment for the CURRENT death is confirmed, the prompt closes itself and emits revive_chosen
    at once: the player continues from where they stood, the paid credit is consumed, nothing to tap.
  - a credit that lands later (order recovered after the app was closed) is banked; on the next death
    the prompt shows REVIVE HERE (paid) - RESTART stays available there so a paid credit is never
    stranded (it survives a restart and is used on the following death).
"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]

g = ROOT / "src" / "menu" / "RevivePrompt.gd"
s = g.read_text(encoding="utf-8")
if "revive at once" not in s:
    old = '''func _on_purchase_completed(p_map_name: String) -> void:
	if is_open and p_map_name == map_name:
		is_waiting = false
		_refresh()
'''
    assert old in s, "anchor _on_purchase_completed"
    new = '''func _on_purchase_completed(p_map_name: String) -> void:
	if is_open and p_map_name == map_name:
		# paid for THIS death -> revive at once; no second menu and no RESTART to mis-tap
		is_waiting = false
		is_confirm = false
		close()
		emit_signal("revive_chosen")
'''
    s = s.replace(old, new, 1)
    g.write_text(s, encoding="utf-8", newline="\n")
    print("RevivePrompt.gd: auto-revive on payment")
else:
    print("RevivePrompt.gd: already patched")

t = ROOT / "tools" / "brand" / "test_paid_revive_rota.gd"
u = t.read_text(encoding="utf-8")
if "auto-revive" not in u:
    old = '''		6:  # done is reported through getStatus() polling only (the fake emits no signal in done mode)
			if revive.paid_credits("1/2") == 1 or _t > 6.0:
				_check(revive.paid_credits("1/2") == 1 and revive.pending_ref == "", "polled done -> credit granted, order closed (no signal involved)")
				_check(not prompt.is_waiting and prompt.revive_button.visible and "paid" in prompt.revive_button.text, "REVIVE HERE (paid) offered: %s" % prompt.revive_button.text)
				_check(not prompt.buy_button.visible, "no BUY while a paid credit exists")
				prompt.revive_button.emit_signal("pressed")
				_t = 0.0
				_step = 7
		7:
			if _t > 0.2:
				_check(not bool(_player.is_dead) and _player.global_position.distance_to(_safe) < 2.0, "revived in place after the in-app payment")
				_check(revive.paid_credits("1/2") == 0 and revive.remaining("1/2") == 0, "paid credit consumed, free counter untouched")
				_t = 0.0
				_step = 8
'''
    assert old in u, "anchor test step 6/7"
    new = '''		6:  # done is reported through getStatus() polling only (the fake emits no signal in done mode)
			if not bool(_player.is_dead) or _t > 6.0:
				_check(not prompt.is_open, "auto-revive: the prompt closed itself when the payment was confirmed")
				_check(not bool(_player.is_dead) and _player.global_position.distance_to(_safe) < 2.0, "revived in place without tapping anything")
				_check(revive.paid_credits("1/2") == 0 and revive.pending_ref == "", "the paid credit was consumed by that revive, order closed")
				_check(revive.remaining("1/2") == 0, "free counter untouched")
				_t = 0.0
				_step = 8
'''
    u = u.replace(old, new, 1)
    t.write_text(u, encoding="utf-8", newline="\n")
    print("paid test: expects auto-revive after payment")
else:
    print("paid test: already patched")
