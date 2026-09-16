# SeekerWallet — Mobile Wallet Adapter for Godot 3 (Android)

A small Android plugin that lets a **Godot 3** game take a Solana payment in the phone's own wallet
(Seed Vault Wallet, Phantom, Solflare…) through the Mobile Wallet Adapter. It was written for
[Seeker Gravity](../../readme.md), where it pays a 100 SKR revive on the Solana Seeker.

Godot 3 has no official MWA integration — the Godot Solana SDK is a GDExtension and needs Godot 4 — so this
wraps `com.solanamobile:mobile-wallet-adapter-clientlib:2.0.3` as a classic Godot 3 Android plugin:
428 lines of Java (`SeekerWallet.java` 402, `Base58.java` 26).

One wallet session does the whole purchase:

```
authorize  ->  POST {base}/pay/tx {ref, wallet}  ->  signAndSendTransactions  ->  POST {base}/pay/confirm {ref, signature}
```

The game never sees a key or a seed phrase, and the server never signs anything.

## Files

| Path | What it is |
|---|---|
| `src/main/java/org/godotengine/plugin/seekerwallet/SeekerWallet.java` | the plugin: local association, authorize, sign and send, cancellation, timeouts, status channel |
| `src/main/java/org/godotengine/plugin/seekerwallet/Base58.java` | base58 encoding for the returned signature |
| `build.gradle` | builds the AAR; `minSdk 23`, the client library is `compileOnly` and resolved at export time |
| `../../android/plugins/SeekerWallet.aar` | the prebuilt plugin |
| `../../android/plugins/SeekerWallet.gdap` | plugin descriptor; lists the Maven dependencies |

## Add it to a Godot 3 project

1. Copy `android/plugins/SeekerWallet.aar` and `android/plugins/SeekerWallet.gdap` into your project's
   `android/plugins/`.
2. In the Godot editor: **Project > Install Android Build Template** (the plugin needs the Gradle build).
3. In the Android export preset, enable the plugin (`plugins/SeekerWallet=true` in `export_presets.cfg`)
   and keep the minimum SDK at 23 or higher.
4. Export. Gradle pulls `com.solanamobile:mobile-wallet-adapter-clientlib:2.0.3` and
   `androidx.annotation:annotation:1.7.1` from Maven, as listed in the `.gdap`.

After editing the Java, rebuild the AAR with `tools/brand/build-plugin.ps1`. It needs `JAVA_HOME` pointing at
a JDK 17 and the Android SDK, and it copies the result into `android/plugins/` for you.

## API

```gdscript
var wallet = Engine.get_singleton("SeekerWallet") if Engine.has_singleton("SeekerWallet") else null
```

| Call | Returns | Notes |
|---|---|---|
| `isAvailable()` | bool | an MWA-capable wallet app is installed on this phone |
| `isBusy()` | bool | a payment is already running |
| `getStatus()` | String | `idle\|`, `working\|<step>`, `done\|<signature>`, `failed\|<reason>` |
| `cancel()` | void | abandon a stuck attempt so the player can try again |
| `diagnose()` | String | which wallet packages were found; useful inside an error message |
| `pay(base_url, ref, product, identity_name, identity_uri, icon_uri)` | void | starts the purchase |

Signals: `pay_done(ref, signature)` and `pay_failed(ref, reason)`.

Poll `getStatus()` as well as listening for the signals — Seeker Gravity does both, so a payment never looks
frozen if a signal is missed while the app is in the background.

`ref` is your own order reference (Seeker Gravity uses 16 random bytes as hex), `product` is a label for the
purchase such as `"revive"`, and `identity_name` / `identity_uri` / `icon_uri` are what the wallet shows the
player before they approve.

## Minimal example

```gdscript
extends Node

const BASE := "https://your-server.example"

func _ready() -> void:
	var w = Engine.get_singleton("SeekerWallet") if Engine.has_singleton("SeekerWallet") else null
	if w == null or not w.isAvailable():
		return                       # desktop build, or no wallet app installed
	w.connect("pay_done", self, "_on_paid")
	w.connect("pay_failed", self, "_on_failed")
	w.pay(BASE, "9f1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e", "revive",
		"Your Game", BASE, "/static/icon-512.png")

func _on_paid(ref: String, signature: String) -> void:
	print("paid ", ref, " in ", signature)

func _on_failed(ref: String, reason: String) -> void:
	print("not paid: ", reason)
```

## What your server has to provide

| Endpoint | Request | Response |
|---|---|---|
| `POST /pay/tx` | `{"ref": ..., "wallet": ...}` | `{"tx": "<base64 unsigned transaction>"}` or `{"error": ...}` |
| `POST /pay/confirm` | `{"ref": ..., "signature": ...}` | `{"paid": true}` or `{"error": ...}` |

The player's wallet is the fee payer, so build the transaction for the account the plugin sends you.
[`server/`](../../server) in this repository is a working implementation: it builds an SPL `transfer_checked`
plus a Memo carrying the order reference, then verifies on chain that the money arrived for that memo. It
holds no private key.

## Licence

MIT, the same as the rest of this repository — see [LICENSE](../../LICENSE). The Mobile Wallet Adapter client
library it depends on is published separately by Solana Mobile under its own licence.
