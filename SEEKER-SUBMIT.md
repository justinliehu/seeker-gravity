# Seeker Gravity — Solana dApp Store 上架包

> 跟 Seeker Heli 同一套流程,差別只有兩個:**這是 Godot 3.6.1**(不是 4),還有**簽名方式**
> (Godot 3 沒有環境變數餵密碼的功能,所以正式包是先用公開的 debug key 匯出、再用 apksigner
> 用你的金鑰重簽,密碼只在終端機輸入、不落地)。

## 0. 現況(2026-09-05 晚間更新)

| 項目 | 狀態 |
|---|---|
| 換皮(標題字標、開機畫面、圖標、致謝)| ✅ 完成,APK 內已無任何原作者字串 |
| Steam / itch / Flatpak 移除;暫停選單 Store Page 隱藏 | ✅ |
| 原地復活:每關每天免費 3 次 | ✅ 真機驗證 |
| 付費復活 100 SKR(App 內 Seeker 錢包一鍵,付款確認即復活) | ✅ 真機 5 筆真付款驗證;後端 Koyeb 零私鑰 |
| 手機版選項選單(藏鍵盤/手把/視窗項目) | ✅ |
| 建置方式 | gradle custom build(`android/build` 模板 + `android/plugins/SeekerWallet.aar`),JDK 17 |
| 正式包 | **1.4.5(versionCode 19)**,2026-09-09 加入遊戲內說明後升版(要重跑 build-release.ps1),release 簽名,73.8 MB,arm64-v8a,minSdk 23 / target 34 |
| 權限 | INTERNET、ACCESS_NETWORK_STATE(只用於付款;Portal 要如實填) |
| 商店素材 | ✅ `store-assets/`:icon-512、banner 1200×600、feature 1200×1200、截圖 |
| 上架文案 + 審核說明 | ✅ `store-assets/config.reference.yaml`(已含內購與權限說明) |
| 下載站 + 法律頁 | ✅ https://seeker-heli-seeker-doudizhu-126cd50d.koyeb.app/gravity(Privacy/Terms 已揭露內購);站上 game.apk 已換成 release 簽名版(手機上的 debug 測試版要先移除才能安裝) |
| release 簽名 | ✅ 2026-09-05 22:54 你的金鑰 `keys/seeker-gravity-release.keystore`(alias seekergravity,CN=Ehu Li),憑證 SHA-256 `cff7777f4833f302ae71d388f352dc67755fddfd00b84f63a831f379212da832`。**金鑰檔 + 密碼要備份,上架後不能換** |
| Portal 提交 | ⚠️ 2026-09-06 第一次送審被拒:「Publisher website 指向另一個已上架的 app(Seeker Heli 下載頁)」。已修:網站根目錄改成發行者總頁 https://seeker-heli-seeker-doudizhu-126cd50d.koyeb.app/ (列出所有遊戲),Heli 自己的頁面移到 /heli/。**要重新送審**(同一個 APK):Publisher 資料的 Website 填根目錄網址,App 的 Website 仍填 /gravity/ |

## 1. 一次性:把 Godot 3.6.1 的東西搬進你的帳號(跟 heli 那次一樣的原因)

我這邊的 `%APPDATA%` 是虛擬的,所以請在**你的 PowerShell** 跑一次:

```powershell
$t = Join-Path $env:APPDATA 'Godot\templates\3.6.1.stable'; New-Item -ItemType Directory -Force -Path $t | Out-Null; Copy-Item 'C:\Users\justi\godot3\templates\templates\android_debug.apk','C:\Users\justi\godot3\templates\templates\android_release.apk','C:\Users\justi\godot3\templates\templates\version.txt' $t -Force; $k = Join-Path $env:APPDATA 'Godot\keystores'; New-Item -ItemType Directory -Force -Path $k | Out-Null; Copy-Item 'C:\Users\justi\godot3\keys\debug.keystore' $k -Force; Get-ChildItem $t, $k | Select-Object Name, Length
```

要看到 `android_debug.apk`(≈56 MB)、`android_release.apk`(≈48 MB)、`version.txt`、`debug.keystore`。

## 2. 建 release 金鑰(只做一次)

```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\justi\Desktop\games\rota\tools\brand\new-release-key.ps1
```

密碼自己設、寫下來、備份兩份。金鑰在 `rota\keys\seeker-gravity-release.keystore`(已 gitignore)。
**這把跟 heli 的那把是不同的 app,可以用新的,也可以用同一把**(用同一把就把 `-Keystore`、`-Alias` 參數指過去)。

## 3. 出正式包

```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\justi\Desktop\games\rota\tools\brand\build-release.ps1
```

流程:檢查模板 → 用 debug key 匯出 release 模板的 APK → **apksigner 問你密碼**重簽 → 驗證 → 複製到 `web/static/game.apk`。
產物:**`build/android/seeker-gravity-release.apk`**。

密碼被 apksigner 拒絕時(`keystore password was incorrect`):匯出已經完成,不必重編。先自己驗密碼(輸入的是建金鑰時**第一個**輸的 keystore 密碼):

```powershell
keytool -list -keystore C:\Users\justi\Desktop\games\rota\keys\seeker-gravity-release.keystore
```

列出 `seekergravity, ..., PrivateKeyEntry` 就代表密碼對;然後只重簽名:

```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\justi\Desktop\games\rota\tools\brand\build-release.ps1 -SignOnly
```

(腳本本身也會讓你連試 3 次。)密碼真的忘了、而且還沒上架過:把 `keys\seeker-gravity-release.keystore` 改名備份,重跑 `new-release-key.ps1` 建新金鑰,再 `-SignOnly`。**上架之後就不能換金鑰了。**密碼請只用英數字,避免中文輸入法或德文鍵盤 y/z 對調造成輸入不一致。

腳本 2026-09-05 踩過、已修掉的三個坑(再遇到同類錯誤先想這三個):
- **PowerShell 5.1 寫 UTF-8 會帶 BOM** → Godot 3 讀 `editor_settings-3.tres` / `export_presets.cfg` 報 `Parse Error: Expected '['`、`presets detected: (none)`。腳本改用 `UTF8Encoding($false)` 寫檔,並每次重寫一份最小的 editor settings(舊檔備份成 `.bak`)。
- **`&` 不會等 Godot 跑完**(Godot 的 Windows 版是視窗程式,20 ms 就回來)→ 腳本以為沒出 APK、把 preset 還原,背景的 Godot 讀到空的 release keystore → `Code-Signieren: Keystore konnte nicht gefunden werden`。腳本改用 `Start-Process -Wait`。
- **gradle 的搬檔步驟會被判 UP-TO-DATE 跳過**:重編出來的 APK 位元組完全相同、輸出資料夾又沒變時,`copyAndRenameReleaseApk` 直接略過(檔名不算它的輸入),Godot 仍印 `Successfully completed` 但沒檔案。腳本改成每次匯出到新的 `build/android/export-<時間>/` 再搬到正式檔名。Godot 匯出失敗時 exit code 也是 0,只有檢查 APK 檔案存在才可信。

## 3.5 重新送審(2026-09-08)

被拒原因是發行者網站,不是 App。Portal 要新的 release,所以版本升到 **1.4.4 / versionCode 18**:

1. 客服把 publisher Website 改成 https://seeker-heli-seeker-doudizhu-126cd50d.koyeb.app/(總頁,列 Olympian Intrigue + Seeker Gravity)。
2. 跑 `build-release.ps1`(輸入金鑰密碼)→ 產出 1.4.4 的正式包。
3. Portal「Upload Seeker Gravity release」上傳該 APK,What's New 用 `store-assets/portal-copy.txt` 裡的版本,再 Submit。

## 3.6 加入遊戲內說明(1.4.5,2026-09-09)

評論說 no in game tutorial or explanation。保留「自己摸索」的設計,只加兩樣不打擾的東西(`tools/brand/patch_howto.py`):

1. **HOW TO PLAY 頁**(`src/menu/MenuHowTo.tscn`):四個操作按鈕圖示 + 三行規則,標題選單和暫停選單都進得去,按 Back 或確認就關。玩家不點就看不到。
2. **第一關的一行提示**(`src/autoload/Tip.tscn`):新遊戲第一次站進第一關時,畫面上方淡入「Walk off an edge: gravity turns with you」,五秒後自己淡出,**一輩子只出現一次**(旗標存在 `user://tips.json`,刪存檔會重新教)。不用點、不擋操作。

測試:`tools/brand/test_howto.gd`(20 項)。畫面截圖:`store-assets/screenshots-howto/`。

## 4. Portal 表單(直接複製)

| 欄位 | 值 |
|---|---|
| dApp Name | `Seeker Gravity` |
| Package Name | `com.justinliehu.seekergravity` |
| Subtitle | `Bend gravity. Push blocks. Find 50 gems.` |
| Description / Headline / What's New | `store-assets/config.reference.yaml` |
| Icon 512 | `store-assets/icon-512.png` |
| Banner 1200×600 | `store-assets/banner-1200x600.png` |
| Graphic 1200×1200 | `store-assets/feature-1200x1200.png` |
| Previews(≥4,全 1920×1080)| `store-assets/screenshots/` 裡的 `level*.png`、`world1.png`、`world3.png`、`title.png` |
| Website / Privacy / Terms / License | 部署後的網址 + `/legal/privacy` `/legal/terms` `/legal/license` |
| Contact / Support | `justinliehu@gmail.com` |
| Review Notes | `config.reference.yaml` 的 `testing_instructions` 整段 |

## 5. 之後出新版本

`export_presets.cfg` 的 `version/code` +1、`version/name` 升 → 用**同一把**金鑰跑 `build-release.ps1` → Portal New Version。

## 6. 這一版跟原作差在哪

| 改動 | 原因 |
|---|---|
| 名稱 / 包名 / 字標 / 圖標 / 開機畫面全換 | 不能用原作者的品牌與套件身份;她的 logo 與網址圖都已移除 |
| 標題畫面寫 BASED ON ROTA,致謝畫面寫 ROTA by Harmony Monroe + MIT | MIT 只要求保留版權聲明,這比要求的多,是刻意的 |
| 移除 `addons/steam_api`、成就、Steam 商店連結、itch 上傳腳本、Flatpak 檔 | 手機版用不到,而且 GDNative 沒有 Android 版函式庫 |
| 刪掉未使用字型(Fontopo、KodomoRounded、Alexandria 其他字重) | 沒被引用,省體積 |
| 只出 arm64 | Seeker 是 arm64;少一半體積 |

保留的第三方素材與授權都列在 `NOTICE.md`;`LICENSE` 是原作者的 MIT 原檔,一字未改。

## 版本紀錄

| 版本 | versionCode | 內容 |
|---|---|---|
| 1.0.0 | 1 | 首發(reskin + 觸控) — 只在網站提供過測試 APK,未送 Portal |
| 1.1.0 | 2 | 原地復活:死掉後可從最後站穩的位置繼續,每關每天免費 3 次;重開關卡永遠免費。測試:`tools/brand/test_revive_rota.gd`(見 HANDOFF/NOTICE) |
| 1.2.0 | 3 | **付費復活**:免費 3 次用完後可付 100 SKR 原地復活(Seeker 錢包一鍵付款)。新增 INTERNET 權限(只用於付款狀態查詢)。測試:`test_paid_revive_rota.gd` + `heli/web/test_pay.py` |

## 原地復活(1.1.0)怎麼測

```powershell
& 'C:/Users/justi/godot3/Godot_v3.6.1-stable_win64.exe' --no-window --path 'C:/Users/justi/Desktop/games/rota' --script res://tools/brand/test_revive_rota.gd res://tools/brand/TestDummy.tscn
```

最後一個參數(空場景)不能省:Shared 的 `onready var csfn := get_tree().current_scene.filename` 需要一個 current scene,純 `--script` 模式沒有 → Shared 整個初始化失敗。測試走遊戲自己的 `wipe_scene` 路徑(wipe 出→換關→wipe 入),因為玩家 sprite 只有在 wipe 入之後才 `show`,物理循環才會跑。26 項全綠才算過。

規則:死掉 → 0.7 秒死亡動畫 → 若本關今天還有免費次數就跳出 REVIVE HERE / RESTART LEVEL;REVIVE 回到最後**站穩 ≥0.2 秒**的位置,1.5 秒無敵閃爍,方塊與計時不重置;免費次數用完就直接重載關卡(付費層以後接在這裡)。次數存在存檔 `revives` 欄位,按裝置本地日期歸零。

## 付費復活(1.2.0)怎麼運作、怎麼測

**架構(Godot 3 沒有錢包 SDK,所以付款在網頁完成):**
1. 免費 3 次用完 → 死亡選單顯示 `REVIVE - 100 SKR`。按下去遊戲產生一個隨機訂單號 ref(存在存檔裡),
   用瀏覽器打開 `https://seeker-heli-seeker-doudizhu-126cd50d.koyeb.app/gravity/pay?ref=…&level=…`。
2. 付款頁(`heli/web/pay.html` + `static-gravity/pay/pay.mjs`,MWA = Seeker 錢包一鍵)向後端要一筆**未簽名**交易:
   `transfer_checked` 100 SKR 玩家 ATA → 平台 ATA(`G49cN5KNnVfakMBFa7RLbHq1TZv1T86kR1Sp2bGKtoGG`,跟 mines/plinko/crash 共用),
   外加一條 Memo `seekergravity:revive:<ref>`;玩家錢包簽名並廣播。
3. 付款頁把簽名 POST 到 `/gravity/pay/confirm`,後端 `getTransaction` 驗證(無錯誤、平台 SKR 增加 ≥100、memo 帶 ref、6 小時內),
   記錄 ref=已付(JSON 檔;一個簽名只能付一個 ref)。
4. 遊戲每 3 秒輪詢 `/gravity/pay/status?ref=`(回到遊戲時立刻查一次),拿到 paid 就多一次 `REVIVE HERE (paid)`。
   店的存檔丟了(重新部署)也不怕:status 會掃平台 ATA 最近 40 筆簽名找 memo 補回。
- 後端**沒有任何私鑰**,只收款;收款地址可用 Koyeb 環境變數 `PLATFORM_WALLET` 覆蓋,RPC 用 `SOLANA_RPC_URL`(預設公共主網節點)。
- 價格在 `pay.py` 的 `REVIVE_PRICE_SKR`(環境變數)和 `src/autoload/Revive.gd` 的 `PRICE_SKR` 兩處,改價要一起改。

**測試:**
```powershell
# 遊戲端(先起 mock 付款伺服器,再跑 Godot 無頭測試)
python tools/brand/mock_pay_server.py 8765 2
& 'C:/Users/justi/godot3/Godot_v3.6.1-stable_win64.exe' --no-window --path 'C:/Users/justi/Desktop/games/rota' --script res://tools/brand/test_paid_revive_rota.gd res://tools/brand/TestDummy.tscn
# 後端(在 heli/web,需要 solders/solana 的 venv)
python test_pay.py --chain
```

**上架資料要改的地方(Portal):** 權限從「無」改成 INTERNET + ACCESS_NETWORK_STATE(gradle 建置 + 錢包函式庫帶進來的,只用於付款);要勾/填「含應用內購買」;
Privacy/Terms 頁面已更新(`/gravity/legal/privacy`、`/gravity/legal/terms`);What's New 見 `store-assets/config.reference.yaml`。

## App 內付款(1.3.0,Seeker 內建錢包彈窗,不跳網頁)

使用者要求付款要在 App 裡完成 → 加了一個 Godot 3 Android 插件 **SeekerWallet**(`tools/seekerwallet-plugin/`,Java,
依賴 Solana Mobile 的 `mobile-wallet-adapter-clientlib` 2.0.3)。流程跟斗地主 App 一樣是 MWA 一鍵:
`Revive.begin_purchase()` → 插件 `pay(base_url, ref, "revive", 身分名, 身分 URL, 圖示)` → 一個錢包 session 內做完
authorize → POST `/gravity/pay/tx` 拿未簽名交易 → `signAndSendTransactions` → POST `/gravity/pay/confirm` 鏈上驗證 →
signal `pay_done(ref, signature)` → 遊戲加一次付費復活。失敗/取消 → `pay_failed(ref, reason)`,選單回到 BUY 並顯示原因。
沒有插件(桌機)或手機上沒有 MWA 錢包時,才退回原本的瀏覽器付款頁;後端輪詢 `/pay/status` 仍是保險。

**建置改變(重要):** export preset 改成 `custom_build/use_custom_build=true`(Godot 的 gradle 建置)、`min_sdk=23`、
`plugins/SeekerWallet=true`。需要:
- `android/build/`:Godot 3.6.1 Android 建置模板(從 `android_source.zip` 解開到 `android/build/`,並在 `android/.build_version` 寫入 `3.6.1.stable`,不能有換行);
- `android/plugins/SeekerWallet.aar` + `SeekerWallet.gdap`(改插件原始碼後跑 `tools/brand/build-plugin.ps1` 重建);
- JDK 17(`JAVA_HOME`)+ Android SDK;第一次 gradle 會下載相依套件(幾分鐘)。
`build-release.ps1` 已加 preflight 檢查這些。版本 1.3.0(versionCode 4)。

**1.3.2 修掉的兩個真原因(都是用 `aapt dump xmltree <apk> AndroidManifest.xml` 看合併後的 manifest 才找到的,猜不出來):**
1. Godot 3 的主 Activity 是 `launchMode="singleInstance"`。從這種 Activity 呼叫 `startActivityForResult()`,目標會被丟到另一個 task 並立刻回傳 CANCELED;我原本只把啟動失敗寫進 log,所以畫面就停在等待。改用 `startActivity()`(我們根本不需要結果),失敗即時回報。
2. MWA 的本機配對是 **cleartext websocket `ws://127.0.0.1:<port>`(錢包是 server,我們是 client)**,而 targetSdk 34 預設禁止 cleartext,Godot 模板和錢包函式庫都沒開 → 連線永遠開不起來。插件 manifest 現在加上`android:usesCleartextTraffic="true"`。

另外:配對逾時 60s→25s、每個失敗都標出是哪一步(lookup/launch/connect/authorize/sign/server)、死亡選單會顯示 `diagnose()` 一行狀態、等待畫面多一顆 **PAY IN BROWSER**,同一張訂單可改用網頁付款,不會卡死。

**真機除錯:** 錢包畫面一閃(螢幕轉一下)就回遊戲 = 連線成功但我們這邊的呼叫立刻失敗;先看死亡選單上的錯誤文字,再用
`adb logcat -s SeekerWallet` 看原因。1.3.0 就是這樣死的:MWA 規定 `icon_uri` 必須是相對於 `identity_uri` 的相對路徑
(clientlib 會丟 `iconRelativeUri must be a relative Uri`),1.3.1 起插件會自動把絕對網址轉成路徑。

**測試:** `test_paid_revive_rota.gd` 現在 44 項,Part B 用一個假的錢包物件(`Revive.wallet_override`)驗證插件呼叫參數、
拒絕付款回到選單、成功後直接加次數。真錢包只能在 Seeker 手機上測。

## 1.3.3:只走 App 內錢包,沒有任何網頁付款

使用者明確要求:**不要瀏覽器、不要網頁付款**。1.3.3 起遊戲裡沒有任何 `OS.shell_open`、沒有 PAY IN BROWSER;付款只有一條路 = SeekerWallet 插件
(Mobile Wallet Adapter)。後端的 `/pay/tx`、`/pay/confirm`、`/pay/status` 是插件在用的 API,不是網頁。`/gravity/pay` 那個結帳網頁還在伺服器上但遊戲不會開它。

**真機證據怎麼讀(1.3.2 的截圖):**
- 「A payment is already in progress」這句是插件透過 Godot 訊號傳回來的 → 訊號機制正常,插件也載入了。
- 它同時代表上一次 pay() 的執行緒還沒結束 → 錢包被叫起來了,但**我們連不上它**。
- 反編譯 clientlib 確認:遊戲端是 WebSocket **client**,連 `ws://127.0.0.1:<port>/solana-wallet`;錢包是 server。錢包在收到 authorize 之前不畫任何畫面,
  所以「什麼視窗都沒有」= 連線沒建立,不是插件沒啟動。
- 對照 seeker-mines 的 JS 程式庫(`vendor/mwa.js`):它也是 `ws://localhost:<port>/solana-wallet`、同樣的埠範圍與重試表。機制一樣,沒有可抄的秘密參數;差別只可能在**手機上是哪個 App 在接 `solana-wallet:`**。

**1.3.3 做了什麼:**
- 插件 `getStatus()` 回傳 `working|<step>` / `done|<sig>` / `failed|<reason>`,遊戲每 0.5 秒輪詢,等待畫面即時顯示步驤(opening wallet → connecting to wallet → waiting for approval → building transaction → waiting for signature → confirming on-chain)。訊號仍會發,但不再依賴它。
- 插件 `diagnose()` 列出**實際回應 `solana-wallet:` 的套件名稱** + cleartext 狀態,失敗時顯示在死亡選單上 → 截圖就能判斷是沒有錢包、錢包不對、還是連線被拒。
- 插件 `cancel()`:CANCEL 或再按 REVIVE 會放棄卡住的嘗試,不會再出現「already in progress」。
- 回到 `startActivityForResult`(launchMode 其實是 `singleInstancePerTask`=0x4,允許;而且這是官方範例的做法,錢包可用 `getCallingPackage()` 辨識我們)。
- GDScript 不再對插件單例用 `has_method()`:Godot 3 對原生註冊的插件方法一律回傳 false(這就是之前畫面出現 "wallet plugin present" 而不是診斷字串的原因)。

**測試:** `test_paid_revive_rota.gd` 改為純錢包流程(mock 伺服器用 `8765 999` 讓它永不回 paid,確保只有錢包路徑能加次數):無插件→立即失敗有原因;拒絕→回選單顯示原因+診斷;卡住→CANCEL 呼叫插件 cancel()→再買→靠輪詢 getStatus 拿到 done→REVIVE (paid)→原地復活;存檔往返;離線行為。

## 1.3.4:先轉直式再叫錢包

1.3.3 真機截圖:等待畫面走到 **Waiting For Approval** → 叫起、連線、送出授權都成功,錢包卻沒畫確認視窗;截圖是直式、遊戲橫著露在底下 = 錢包的直式
Activity 在最上面但是空的。跟斗地主/seeker-mines(都是直式 App)唯一的結構差別:Gravity 是橫式,錢包一出現螢幕就旋轉,錢包畫面在啟動當下被重建。
1.3.4 的插件在叫錢包前先把遊戲 Activity 轉成直式(Godot 有 configChanges,不會重建)、等 700ms、再送 intent;付款結束還原方向。
等待畫面第一步會顯示實際回應的錢包套件名(`opening wallet <package>`);CANCEL 會關閉配對 session。圖示路徑改成 root-relative(`/gravity/static/icon-512.png`),
之前的 `static/icon-512.png` 相對 `https://host/gravity` 會解析到 404。

## 1.3.6:真正的原因(錢包端日誌抓到的)

用 USB + adb 錄手機日誌,錢包(`com.solanamobile.wallet`,pid 用 `adb shell pidof com.solanamobile.wallet`)在收到我們授權請求的那一毫秒寫下:
```
W/c: mobile-wallet-adapter WebSocket exception
W/c: java.lang.IllegalArgumentException: input is not a valid solana cluster
```
錢包把請求丟掉、不回應、不畫面,我們 90 秒後逾時。原因:`MobileWalletAdapterClient.authorize` 有兩個版本——
四參數版最後一個參數是**舊式 cluster 名稱**(`mainnet-beta`),八參數版第四個參數才是新式鏈 ID(`solana:mainnet`)。
我用四參數版卻傳 `solana:mainnet`。修正:`client.authorize(identity, icon, name, "solana:mainnet", null, null, null, null)`。
斗地主/seeker-mines 的 JS 程式庫本來就送新式格式,所以它們正常。

之前六版追的東西(工作區、cleartext、轉向、圖示)都不是主因;其中 **startActivity(而非 ForResult)** 是對的、保留
(錢包的 MWABottomSheetActivity 是 singleTask + 自己的 taskAffinity);轉直式的 hack 已拿掉。

**除錯方法(以後別再猜):** 手機開 USB 偵錯接電腦 → `adb logcat -c` → 觸發 → `adb logcat -v time` 存檔 → 看錢包 pid 的行。
錢包的 tag 被混淆成單字母(c/t/n/s/e),但例外訊息是明文。`dumpsys activity activities` 可看錢包 sheet 在哪個 task、是否 RESUMED。

## 1.3.7:App 內錢包流程真機通過(授權成功)

1.3.6 其實沒把修正編進去(補丁失敗但舊 AAR 仍被複製),1.3.7 用 `javap`/`dexdump` 驗過位元碼才裝機。真機日誌:
`associated → waiting for approval → authorized wallet=HGGcc…`(錢包視窗出現、使用者按了同意),接著卡在我們後端的餘額預檢
「not enough SKR: this wallet holds 0 SKR」——鏈上查證該帳戶 SKR 餘額確實為 0(SKR 是傳統 Token program、6 位小數,ATA 查法正確),
SOL 有 0.0218。下一步是使用者把 SKR 放進該帳戶(或在錢包裡選有 SKR 的帳戶),再測真實轉帳與 `/pay/confirm`。
建置紀律:裝機前一定用 `javap -p -c` 看 AAR、`dexdump -d` 看 APK 內的呼叫描述符;`;` 串接的複製步驟會把失敗的建置蓋過去。

## 1.3.8:第一次進遊戲的玩法提示卡(中/EN)

原作沒有任何文字教學。新增自動載入 `HintCard`(`src/menu/HintCard.tscn`):第一次進入第 1 世界以後的非 hub 關卡時顯示一次,
三個圖示(搖桿=移動、靴子=跳、手=抓/放方塊)+「走出邊緣,整個世界會跟著你轉」+「收集寶石可以開門」,按鈕「點一下開始 · TAP TO START」,
任意點擊關閉;顯示期間用 `Cutscene.is_playing` 擋掉玩家輸入。看過的旗標存在 `user://hints.cfg`(不在存檔槽,換存檔不會重出)。
中文字型 = Noto Sans CJK TC 的子集(只含提示卡用到的字,42 KB,OFL,授權全文在 `media/font/OFL-NotoSansCJK.txt`,NOTICE 已加)。
測試:`tools/brand/test_hint_card.gd`。**要拿掉這張卡:刪掉 `project.godot` 裡 `HintCard="*res://src/menu/HintCard.tscn"` 那一行即可**,其他檔案留著無害。

## 1.3.9:提示卡拿掉

使用者看過 1.3.8 的提示卡後決定不要(「這是要玩家自己摸索怎麼玩的」)。HintCard 自動載入、場景、腳本、字型子集、測試全部移除,遊戲回到原作的無教學設計。

**2026-09-05 20:46 真機真付款成功(1.3.7):** 交易 `5Nk7c824jpPEaAgmTvrEAdHpgAfAdHyPhgw2ND2e17yGvMD1SCfZ3s6ncMZHp9dsAfMqPtL1p5ExQ5HBpFphpEXo`,100 SKR 從玩家帳戶 HGGcc… 轉入平台錢包 G49cN5…(664.922 → 764.922),memo `seekergravity:revive:<ref>`,後端 `/pay/status` 回 paid。App 內錢包付款整條路正式跑通。

## 1.4.0:選項選單改成手機版

`Shared.is_mobile`(Android 為 true)。Options 在手機上隱藏:Keyboard Setup、Fullscreen、Borderless、Window Size、Mouse、V-Sync;
保留:Controller Setup(藍牙手把)、Grab Toggle、Touch Screen(TOGGLE/ALWAYS)+ Margin X/Y、音量、Interpolate/Frame Limit/Physics Step/
Radial Blur/Dynamic Light/Shadows/Shadow Quality/Weather、Speedrun 計時。暫停選單隱藏沒作用的 Store Page。
`MenuOptions.row()` 原本用寫死的游標索引決定滑桿音效,改成看該列是否有 `axis_x`(隱藏列後索引會變)。
補丁 `tools/brand/patch_mobile_options.py`,測試 `tools/brand/test_mobile_options.gd`。

## 1.4.1:Controller Setup 也藏掉

使用者把手機版定義為純觸控,所以 Options 的 Input 區在手機上只剩 Touch Screen 與 Margin X/Y;Controller Setup(A/B/X/Y 重綁)一併隱藏。

## 1.4.2:防誤付款 + 錢包等待有上限

真機事故:付款成功後再死,使用者要 RESTART 卻又跳錢包、CANCEL 按不動。原因:(1) 觸控按鍵層(layer 19)在死亡選單(layer 7)上面,
C/X 觸控鍵在選單中就是 accept/back,而死亡選單把 ui_accept 對到 BUY → 按到跳躍鍵就等於購買;(2) 第二次叫起的錢包視窗停在背景不可見,
而 authorize 的等待沒有 timeout → 無限卡住。修正:BUY 先進確認頁「Pay 100 SKR with your Seeker wallet? [PAY 100 SKR] [BACK]」,只有 PAY 會開錢包;
ui_accept 永不購買;選單開啟時隱藏遊戲觸控鍵(同 MenuPause 的 `TouchScreen.set_game(false)`);失敗/取消後 1.5 秒內忽略 BUY;
插件等待上限 authorize 60 秒、簽名 120 秒,超時回選單;我們自己 CANCEL 造成的 CancellationException 顯示為「Payment cancelled.」。

## 1.4.3:付款成功立刻復活

使用者付款後選單同時有 REVIVE HERE (paid) 與 RESTART LEVEL,誤觸且沒道理。現在付款一確認就直接原地復活(扣掉那次付費次數),不再出現第二個選單。
晚到的付款(App 關掉後才確認)會存成一次付費次數,下次死亡顯示 REVIVE HERE (paid),那時仍保留 RESTART,以免付費次數被卡住。
