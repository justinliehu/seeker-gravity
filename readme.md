# Seeker Gravity

A gravity-bending puzzle platformer for the **Solana Seeker**, with an optional in-app **100 SKR**
purchase approved in the phone's own wallet through the **Mobile Wallet Adapter**. No ads, no accounts,
no analytics; the game itself works fully offline.

Built with **Godot Engine 3.6.1**. Package `com.justinliehu.seekergravity`, version 1.4.5 (versionCode 19).

Signed APK and legal pages: <https://seeker-heli-seeker-doudizhu-126cd50d.koyeb.app/gravity/>

> The game world (levels, art, music) comes from **ROTA: Bend Gravity** by Harmony Honey Monroe, used
> under the MIT licence. What was built in this repository is the mobile and Solana layer described
> below. See [NOTICE.md](NOTICE.md) for the full attribution and [LICENSE](LICENSE) for the original
> licence, both of which ship inside the app.

## What was built here

| Piece | Where | What it is |
|---|---|---|
| **Mobile Wallet Adapter plugin for Godot 3** | `tools/seekerwallet-plugin/` | 428 lines of Java wrapping `com.solanamobile:mobile-wallet-adapter-clientlib:2.0.3` as a Godot 3 Android plugin. Godot 3 has no official MWA integration, so this was written from scratch: local association, `authorize`, `signAndSendTransactions`, cancellation, timeouts, and a status channel the game polls. |
| **In-app purchase flow** | `src/autoload/Revive.gd`, `src/menu/RevivePrompt.*` | Order reference, explicit confirm step, live wallet progress, cancel, retry, recovery of an order paid while the app was closed, and continuing the moment the payment is confirmed on chain. |
| **Payment backend** | `server/` | Builds the unsigned transaction (SPL `transfer_checked` of 100 SKR plus a memo carrying the order reference) and verifies it on chain afterwards. It holds no private key and cannot move funds. |
| **Revive in place** | `src/actor/Player.gd` | Continue from the last spot you stood on instead of restarting the level. Three free revives per level per day; the paid revive exists only after those run out. |
| **Phone-first UI** | `src/autoload/touch_screen.tscn`, `src/menu/options/MenuOptions.gd` | On-screen controls, with the desktop-only option rows (key remap, window size, v-sync) hidden on Android. |
| **In-game explanation** | `src/menu/MenuHowTo.*`, `src/autoload/Tip.*` | A How to Play page in the title and pause menus, plus one line of guidance in the first level that fades out by itself. |

## How the purchase works

```
game                      server (no private key)             Solana
 |-- POST /pay/tx ------->| transfer_checked(100 SKR)            |
 |    {ref, wallet}       | + Memo "seekergravity:revive:<ref>"  |
 |<-- unsigned tx --------|                                      |
 |-- MWA authorize + signAndSendTransactions ------------------->| player approves in the wallet
 |-- GET /pay/status?ref->| getTransaction: memo matches and      |
 |                        | the platform wallet gained >= 100 SKR |
 |<-- {"paid": true} -----|                                      |
 revive granted, play continues
```

The player pays from their own wallet to the publisher wallet. The server only builds and verifies, so
nobody's funds are ever in custody. A payment that lands while the app is closed is recovered on the
next launch by scanning the memo.

## Run it

Requirements: Godot **3.6.1** (standard, not Mono), JDK 17, Android SDK with build-tools 35.

```bash
git clone https://github.com/justinliehu/seeker-gravity.git
cd seeker-gravity
```

1. Open the project once in the Godot editor so the resources import.
2. Press F5 to play on desktop, or export an APK:
   - install the Android build template (`Project > Install Android Build Template`),
   - the wallet plugin ships prebuilt in `android/plugins/`; rebuild it with `tools/brand/build-plugin.ps1` after editing the Java,
   - `tools/brand/build-release.ps1` exports and signs it. It asks for the keystore password on the terminal and never stores it.

The paid revive talks to the live backend by default (`Revive.pay_base_url`). To run everything
locally, start `server/` and point that variable at your own machine.

## Tests

Headless, no device needed. Each run takes the dummy scene as its argument.

```bash
Godot_v3.6.1-stable_win64.exe --no-window --path . --script res://tools/brand/test_revive_rota.gd res://tools/brand/TestDummy.tscn
Godot_v3.6.1-stable_win64.exe --no-window --path . --script res://tools/brand/test_paid_revive_rota.gd res://tools/brand/TestDummy.tscn
Godot_v3.6.1-stable_win64.exe --no-window --path . --script res://tools/brand/test_mobile_options.gd res://tools/brand/TestDummy.tscn
Godot_v3.6.1-stable_win64.exe --no-window --path . --script res://tools/brand/test_howto.gd res://tools/brand/TestDummy.tscn
```

The paid-revive suite drives a fake wallet and a mock server (`tools/brand/mock_pay_server.py 8765 999`),
so the whole purchase path is covered without spending anything. `server/test_pay.py` covers the
backend, including that one transaction can satisfy exactly one order.

## Permissions

`INTERNET` and `ACCESS_NETWORK_STATE`, used only for the optional purchase. Verify with
`aapt dump permissions seeker-gravity-release.apk`. Progress is stored on the device.

## Licence

The game this builds on is MIT (Copyright (c) 2025 Harmony Honey Monroe). Modifications in this
repository are released under the same licence. Fonts and audio added here keep their own licences,
listed in [NOTICE.md](NOTICE.md).
