extends Node

# Revive-in-place allowance (autoload `Revive`).
#
# Dying normally reloads the level. With this, the player may instead continue from the last spot
# they stood on:
#   - FREE_PER_DAY times per level per calendar day (device local date), and
#   - beyond that, one paid revive at a time: PRICE_SKR SKR paid through the Seeker wallet.
#
# The paid flow never touches the chain from inside the game. begin_purchase() hands the order to the
# SeekerWallet Android plugin (Mobile Wallet Adapter: the Seeker wallet sheet opens over the game,
# the plugin fetches the unsigned transaction from our server, the wallet signs and sends it, the
# server verifies it on-chain). The plugin result is polled through getStatus(); the server's
# /pay/status is polled as well, so a payment that lands late is still credited. The order ref is a
# random hex string stored in the save slot until it is paid or expires.
#
# Everything (counter, paid credits, pending order) lives in the save slot next to gems/goals
# (see Shared.save_data / load_slot).

signal purchase_started(ref)
signal purchase_completed(map_name)
signal purchase_failed(reason)
signal purchase_cancelled
signal purchase_step(step)

const FREE_PER_DAY := 3
const PRICE_SKR := 100
const PENDING_TTL_SEC := 24 * 3600

var pay_base_url := "https://seeker-heli-seeker-doudizhu-126cd50d.koyeb.app/gravity"
var purchases_enabled := true   # false = offline build behaviour (no prompt once the free revives are gone)
var wallet_override = null      # tests inject a fake wallet object here (pay() + pay_done/pay_failed signals)
var identity_name := "Seeker Gravity"
var last_step := ""             # live step from the plugin, shown on the waiting screen
var _wallet_connected = null

var day := ""          # "YYYY-MM-DD" the counts below belong to
var used := {}         # map_name -> free revives used today
var paid := {}         # map_name -> paid revive credits not yet used
var pending_ref := ""  # open order waiting for payment ("" = none)
var pending_map := ""
var pending_since := 0

var _http: HTTPRequest
var _timer: Timer
var _status_timer: Timer
var _busy := false
var _fast := false     # poll every 3s while the player is on the "waiting for payment" screen


func _ready() -> void:
	_http = HTTPRequest.new()
	_http.timeout = 15
	add_child(_http)
	_http.connect("request_completed", self, "_on_status_reply")
	_timer = Timer.new()
	_timer.one_shot = false
	_timer.wait_time = 20.0
	add_child(_timer)
	_timer.connect("timeout", self, "poll")
	_timer.start()
	_status_timer = Timer.new()
	_status_timer.one_shot = false
	_status_timer.wait_time = 0.5
	add_child(_status_timer)
	_status_timer.connect("timeout", self, "_poll_wallet_status")


func _notification(what: int) -> void:
	# coming back from the wallet: ask right away instead of waiting for the timer
	if what == MainLoop.NOTIFICATION_WM_FOCUS_IN or what == MainLoop.NOTIFICATION_APP_RESUMED:
		if pending_ref != "":
			poll()


# ── allowance ─────────────────────────────────────────────────────────────────────────────

func today() -> String:
	var d = OS.get_date()
	return "%04d-%02d-%02d" % [d["year"], d["month"], d["day"]]


func _roll_day() -> void:
	var t = today()
	if day != t:
		day = t
		used = {}


func remaining(map_name: String) -> int:
	_roll_day()
	return int(max(0, FREE_PER_DAY - int(used.get(map_name, 0))))


func paid_credits(map_name: String) -> int:
	return int(paid.get(map_name, 0))


func can_revive(map_name: String) -> bool:
	return map_name != "" and (remaining(map_name) > 0 or paid_credits(map_name) > 0)


# Should the death prompt open at all? Yes if a revive is available now, or if one could be bought.
func can_offer(map_name: String) -> bool:
	return map_name != "" and (can_revive(map_name) or purchases_enabled)


func consume(map_name: String) -> void:
	_roll_day()
	if remaining(map_name) > 0:
		used[map_name] = int(used.get(map_name, 0)) + 1
	elif paid_credits(map_name) > 0:
		paid[map_name] = paid_credits(map_name) - 1
		if paid[map_name] <= 0:
			paid.erase(map_name)


# ── purchase ──────────────────────────────────────────────────────────────────────────────

func status_url(ref: String) -> String:
	return pay_base_url + "/pay/status?ref=" + ref


func has_pending() -> bool:
	if pending_ref != "" and OS.get_unix_time() - pending_since > PENDING_TTL_SEC:
		_clear_pending()
	return pending_ref != ""


func begin_purchase(map_name: String) -> String:
	# an unpaid order for the same level is reused (the player may have paid already and come back)
	if not has_pending() or pending_map != map_name:
		var bytes = Crypto.new().generate_random_bytes(16)
		pending_ref = bytes.hex_encode()
		pending_map = map_name
		pending_since = OS.get_unix_time()
		_persist()
	_fast = true
	_timer.wait_time = 3.0
	_timer.start()
	var w = _wallet()
	if w == null:
		_fast = false
		emit_signal("purchase_failed", "No Seeker wallet plugin in this build.")
		return pending_ref
	# a stuck earlier attempt must never block a new tap
	if str(w.getStatus()).begins_with("working|"):
		w.cancel()
	_connect_wallet(w)
	last_step = "starting"
	# MWA wants the icon RELATIVE to the identity uri; a root-relative path resolves correctly whether or
	# not the identity uri ends with a slash (https://host/gravity + /gravity/static/icon-512.png)
	var host_end := pay_base_url.find("/", pay_base_url.find("//") + 2)
	var base_path := pay_base_url.substr(host_end, pay_base_url.length()) if host_end >= 0 else ""
	w.pay(pay_base_url, pending_ref, "revive", identity_name, pay_base_url, base_path + "/static/icon-512.png")
	_status_timer.start()
	emit_signal("purchase_started", pending_ref)
	poll()
	return pending_ref


func wallet_diagnosis() -> String:
	var w = _wallet()
	if w == null:
		return "no wallet plugin in this build"
	return str(w.diagnose())


func wallet_step() -> String:
	return last_step


# The player backed out of the waiting screen. The order stays pending (a payment made anyway is
# still credited later); we just stop polling quickly.
func cancel_purchase() -> void:
	_fast = false
	_status_timer.stop()
	last_step = ""
	var w = _wallet()
	if w != null:
		w.cancel()
	_timer.wait_time = 20.0
	_timer.start()
	emit_signal("purchase_cancelled")


# The wallet plugin (Android build with the SeekerWallet plugin) or an injected test double.
func _wallet():
	if wallet_override != null:
		return wallet_override
	if Engine.has_singleton("SeekerWallet"):
		return Engine.get_singleton("SeekerWallet")
	return null


func has_wallet() -> bool:
	return _wallet() != null


func _connect_wallet(w) -> void:
	if _wallet_connected == w:
		return
	_wallet_connected = w
	if not w.is_connected("pay_done", self, "_on_wallet_done"):
		w.connect("pay_done", self, "_on_wallet_done")
	if not w.is_connected("pay_failed", self, "_on_wallet_failed"):
		w.connect("pay_failed", self, "_on_wallet_failed")


# Polled result of the plugin: "working|<step>", "done|<sig>", "failed|<reason>", "idle|".
func _poll_wallet_status() -> void:
	var w = _wallet()
	if w == null or not has_pending():
		_status_timer.stop()
		return
	var st := str(w.getStatus())
	var sep := st.find("|")
	var kind := st.substr(0, sep) if sep >= 0 else st
	var detail := st.substr(sep + 1, st.length()) if sep >= 0 else ""
	match kind:
		"working":
			if detail != last_step:
				last_step = detail
				emit_signal("purchase_step", detail)
		"done":
			_status_timer.stop()
			_grant_pending()
		"failed":
			_status_timer.stop()
			last_step = ""
			emit_signal("purchase_failed", detail)
		_:
			_status_timer.stop()


func _on_wallet_done(ref: String, _signature: String) -> void:
	# the server already verified the payment on-chain before the plugin reports done
	if has_pending() and ref == pending_ref:
		_grant_pending()


func _on_wallet_failed(ref: String, reason: String) -> void:
	if has_pending() and ref == pending_ref:
		emit_signal("purchase_failed", reason)


func poll() -> void:
	if not has_pending() or _busy:
		return
	var err = _http.request(status_url(pending_ref))
	_busy = err == OK
	if err != OK:
		emit_signal("purchase_failed", "Could not reach the payment server (error %d)." % err)


func _on_status_reply(result: int, code: int, _headers: PoolStringArray, body: PoolByteArray) -> void:
	_busy = false
	if result != HTTPRequest.RESULT_SUCCESS or code != 200:
		if _fast:
			emit_signal("purchase_failed", "Payment server unreachable (%s). Still checking..." % (str(code) if code > 0 else "no connection"))
		return
	var parsed = JSON.parse(body.get_string_from_utf8())
	if parsed.error != OK or typeof(parsed.result) != TYPE_DICTIONARY:
		return
	if parsed.result.get("paid", false):
		_grant_pending()


func _grant_pending() -> void:
	_status_timer.stop()
	last_step = ""
	var map_name = pending_map
	paid[map_name] = paid_credits(map_name) + 1
	_clear_pending()
	_fast = false
	_timer.wait_time = 20.0
	_timer.start()
	_persist()
	emit_signal("purchase_completed", map_name)


func _clear_pending() -> void:
	pending_ref = ""
	pending_map = ""
	pending_since = 0


func _persist() -> void:
	var shared = get_node_or_null("/root/Shared")
	if shared != null and shared.has_method("save_data"):
		shared.save_data()


# ── save slot ─────────────────────────────────────────────────────────────────────────────

func to_save() -> Dictionary:
	_roll_day()
	return {"day": day, "used": used.duplicate(), "paid": paid.duplicate(),
			"pending": {"ref": pending_ref, "map": pending_map, "since": pending_since}}


func from_save(d) -> void:
	used = {}
	paid = {}
	day = ""
	_clear_pending()
	if typeof(d) == TYPE_DICTIONARY:
		day = str(d.get("day", ""))
		var u = d.get("used", {})
		if typeof(u) == TYPE_DICTIONARY:
			for k in u.keys():
				used[str(k)] = int(u[k])
		var p = d.get("paid", {})
		if typeof(p) == TYPE_DICTIONARY:
			for k in p.keys():
				if int(p[k]) > 0:
					paid[str(k)] = int(p[k])
		var pend = d.get("pending", {})
		if typeof(pend) == TYPE_DICTIONARY and str(pend.get("ref", "")) != "":
			pending_ref = str(pend.get("ref", ""))
			pending_map = str(pend.get("map", ""))
			pending_since = int(pend.get("since", 0))
	_roll_day()
