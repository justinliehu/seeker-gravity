package org.godotengine.plugin.seekerwallet;

import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.content.ComponentName;
import android.content.pm.ActivityInfo;
import android.content.pm.ResolveInfo;
import android.net.Uri;
import android.util.Base64;
import android.util.Log;

import androidx.annotation.NonNull;

import com.solana.mobilewalletadapter.clientlib.protocol.MobileWalletAdapterClient;
import com.solana.mobilewalletadapter.clientlib.protocol.JsonRpc20Client;
import com.solana.mobilewalletadapter.clientlib.scenario.LocalAssociationIntentCreator;
import com.solana.mobilewalletadapter.clientlib.scenario.LocalAssociationScenario;
import com.solana.mobilewalletadapter.clientlib.scenario.Scenario;

import org.godotengine.godot.Godot;
import org.godotengine.godot.plugin.GodotPlugin;
import org.godotengine.godot.plugin.SignalInfo;
import org.godotengine.godot.plugin.UsedByGodot;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Set;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicReference;

/**
 * Godot 3.x Android plugin: in-app payment through the phone's Mobile Wallet Adapter wallet
 * (Seed Vault / Seeker wallet, Phantom, Solflare...). One wallet session does everything:
 *
 *   authorize  ->  POST {base}/pay/tx {ref, wallet}  ->  signAndSendTransactions  ->  POST {base}/pay/confirm
 *
 * The transaction itself is built by our server (pay.py) so the plugin never needs a Solana SDK; it
 * only carries bytes between the server and the wallet. Signals (all strings):
 *   pay_done(ref, signature)      the server confirmed the payment on-chain
 *   pay_failed(ref, reason)       anything else (user declined, no wallet, network...)
 */
public class SeekerWallet extends GodotPlugin {
    private static final String TAG = "SeekerWallet";
    private static final String CHAIN = "solana:mainnet";
    // The wallet has to come up and accept our connection. Short, so a silent failure surfaces in
    // the game instead of looking like a hang.
    private static final long ASSOCIATION_TIMEOUT_MS = 25_000;
    private static final long APPROVAL_TIMEOUT_MS = 60_000;   // wallet must answer authorize
    private static final long SIGN_TIMEOUT_MS = 120_000;      // user reading the transaction sheet
    private static final int CLIENT_TIMEOUT_MS = 150_000;         // user reading the approval sheet (int: clientlib API)
    private static final int CONFIRM_ATTEMPTS = 30;              // 30 x 3s waiting for on-chain confirmation

    private final AtomicBoolean busy = new AtomicBoolean(false);
    // Polled by the game instead of relying on a signal arriving: "working|<step>", "done|<sig>", "failed|<reason>".
    private final AtomicReference<String> status = new AtomicReference<>("idle|");
    private volatile Thread worker;
    private volatile LocalAssociationScenario current;

    public SeekerWallet(Godot godot) {
        super(godot);
    }

    @NonNull
    @Override
    public String getPluginName() {
        return "SeekerWallet";
    }

    @NonNull
    @Override
    public List<String> getPluginMethods() {
        return Arrays.asList("isAvailable", "isBusy", "diagnose", "getStatus", "cancel", "pay");
    }

    @NonNull
    @Override
    public Set<SignalInfo> getPluginSignals() {
        return new java.util.HashSet<>(Arrays.asList(
                new SignalInfo("pay_done", String.class, String.class),
                new SignalInfo("pay_failed", String.class, String.class)));
    }

    /** True when an MWA-capable wallet app is installed on this phone. */
    @UsedByGodot
    public boolean isAvailable() {
        Activity activity = getActivity();
        if (activity == null) return false;
        try {
            return LocalAssociationIntentCreator.isWalletEndpointAvailable(activity.getPackageManager());
        } catch (Throwable t) {
            Log.w(TAG, "isWalletEndpointAvailable failed", t);
            return false;
        }
    }

    @UsedByGodot
    public boolean isBusy() {
        return busy.get();
    }

    /** State of the running/last payment: "working|<step>", "done|<sig>" or "failed|<reason>".
     *  The game polls this, so a payment can never look frozen even if a signal goes missing. */
    @UsedByGodot
    public String getStatus() {
        return status.get();
    }

    /** Abandon a stuck attempt so the player can tap REVIVE again. */
    @UsedByGodot
    public void cancel() {
        LocalAssociationScenario c = current;
        if (c != null) {
            try {
                c.close();
            } catch (Throwable ignored) {
            }
        }
        Thread t = worker;
        if (t != null) t.interrupt();
        busy.set(false);
        status.set("idle|");
        Log.i(TAG, "cancelled");
    }

    private void step(String name) {
        Log.i(TAG, "step: " + name);
        status.set("working|" + name);
    }

    private void fail(String ref, String reason) {
        Log.w(TAG, "failed: " + reason);
        status.set("failed|" + reason);
        emitSignal("pay_failed", ref, reason);
    }

    /** Which apps actually answer solana-wallet: on this phone, plus the cleartext policy. A
     *  screenshot of this line is enough to tell a missing wallet from a refused connection. */
    @UsedByGodot
    public String diagnose() {
        StringBuilder sb = new StringBuilder("wallets: ");
        Activity activity = getActivity();
        try {
            Intent probe = new Intent(Intent.ACTION_VIEW, Uri.parse("solana-wallet:/v1/associate/local"));
            List<ResolveInfo> found = activity.getPackageManager().queryIntentActivities(probe, 0);
            if (found.isEmpty()) {
                sb.append("NONE");
            } else {
                for (ResolveInfo ri : found) sb.append(ri.activityInfo.packageName).append(' ');
            }
        } catch (Throwable t) {
            sb.append("lookup error ").append(t.getClass().getSimpleName());
        }
        sb.append("| cleartext=")
          .append(android.security.NetworkSecurityPolicy.getInstance().isCleartextTrafficPermitted("127.0.0.1"));
        return sb.toString();
    }

    /**
     * Start a payment. Returns immediately; the outcome arrives as pay_done / pay_failed.
     * @param baseUrl      e.g. https://host/gravity (no trailing slash)
     * @param ref          the order reference generated by the game (hex)
     * @param product      e.g. "revive"
     * @param identityName shown by the wallet, e.g. "Seeker Gravity"
     * @param identityUri  https URL of the dApp (the wallet shows/verifies it)
     * @param iconUri      absolute or identityUri-relative icon URL
     */
    @UsedByGodot
    public void pay(final String baseUrl, final String ref, final String product,
                    final String identityName, final String identityUri, final String iconUri) {
        if (!busy.compareAndSet(false, true)) {
            // not an error: the game polls getStatus() and shows the live step instead
            return;
        }
        status.set("working|starting");
        final Activity activity = getActivity();
        if (activity == null) {
            busy.set(false);
            fail(ref, "No activity.");
            return;
        }
        if (!isAvailable()) {
            busy.set(false);
            fail(ref, "No wallet app on this phone. " + diagnose());
            return;
        }
        Log.i(TAG, "pay start ref=" + ref + " " + diagnose());
        worker = new Thread(() -> {
            try {
                String signature = runPayment(activity, baseUrl, ref, product, identityName, identityUri, iconUri);
                Log.i(TAG, "pay done ref=" + ref + " sig=" + signature);
                status.set("done|" + signature);
                emitSignal("pay_done", ref, signature);
            } catch (UserDeclined e) {
                fail(ref, "Payment cancelled.");
            } catch (PayException e) {
                fail(ref, e.getMessage());
            } catch (Throwable t) {
                Log.e(TAG, "payment failed", t);
                fail(ref, "Payment failed: " + describe(t));
            } finally {
                busy.set(false);
                worker = null;
            }
        }, "SeekerWallet-pay");
        worker.start();
    }

    private String runPayment(Activity activity, String baseUrl, String ref, String product,
                              String identityName, String identityUri, String iconUri) throws Exception {
        step("opening wallet");
        LocalAssociationScenario scenario = new LocalAssociationScenario(CLIENT_TIMEOUT_MS);
        current = scenario;
        Intent intent = LocalAssociationIntentCreator.createAssociationIntent(null, scenario.getPort(), scenario.getSession());
        ComponentName target = intent.resolveActivity(activity.getPackageManager());
        String walletPkg = target != null ? target.getPackageName() : "?";
        Log.i(TAG, "association intent " + intent.getData() + " port=" + scenario.getPort() + " wallet=" + target);
        step("opening wallet " + walletPkg);

        try {
            return runWithWallet(activity, scenario, intent, baseUrl, ref, identityName, identityUri, iconUri);
        } finally {
            current = null;
            try {
                scenario.close();
            } catch (Throwable ignored) {
            }
        }
    }

    private String runWithWallet(Activity activity, LocalAssociationScenario scenario, Intent intent, String baseUrl,
                                 String ref, String identityName, String identityUri, String iconUri) throws Exception {

        // A launch failure has to be reported, not swallowed, or the game just looks frozen.
        final AtomicReference<Throwable> launchError = new AtomicReference<>();
        final java.util.concurrent.CountDownLatch launched = new java.util.concurrent.CountDownLatch(1);
        activity.runOnUiThread(() -> {
            try {
                // startActivity, not ...ForResult: the wallet sheet is launchMode=singleTask with its
                // own taskAffinity, and startActivityForResult forces it into OUR task where it never
                // draws. We never use the result anyway.
                activity.startActivity(intent);
            } catch (ActivityNotFoundException e) {
                launchError.set(new PayException("No wallet app answered (step: launch). Is the Seeker wallet set up?"));
            } catch (Throwable t) {
                launchError.set(t);
            } finally {
                launched.countDown();
            }
        });
        launched.await(10, TimeUnit.SECONDS);
        if (launchError.get() != null) {
            scenario.close();
            Throwable t = launchError.get();
            Log.e(TAG, "could not launch the wallet", t);
            throw (t instanceof PayException) ? (PayException) t : new PayException("Could not open the wallet: " + describe(t));
        }

        step("connecting to wallet");
        MobileWalletAdapterClient client;
        try {
            client = scenario.start().get(ASSOCIATION_TIMEOUT_MS, TimeUnit.MILLISECONDS);
            Log.i(TAG, "associated with the wallet");
        } catch (TimeoutException e) {
            scenario.close();
            throw new PayException("The wallet did not accept our connection (step: connect). " + diagnose());
        } catch (ExecutionException e) {
            scenario.close();
            throw new PayException("Could not connect to the wallet (step: connect): " + describe(e.getCause() != null ? e.getCause() : e));
        }
        String signature;
        try {
            // 1) who pays
            // MWA: identity_uri is absolute; icon_uri MUST be relative to it (the clientlib throws
            // IllegalArgumentException otherwise, which closed the session before the wallet drew anything).
            Uri identity = Uri.parse(identityUri);
            Uri icon = Uri.parse(iconUri == null ? "" : iconUri);
            if (!icon.isRelative()) {
                String path = icon.getPath();
                icon = Uri.parse(path == null || path.isEmpty() ? "icon.png" : path.replaceFirst("^/", ""));
            }
            step("waiting for approval");
            Log.i(TAG, "authorize identity=" + identity + " icon=" + icon);
            MobileWalletAdapterClient.AuthorizationResult auth = client.authorize(identity, icon, identityName, CHAIN, null, null, null, null).get(APPROVAL_TIMEOUT_MS, TimeUnit.MILLISECONDS)  /* 8-arg v2: 4th arg is the CHAIN id; the 4-arg overload sends a legacy CLUSTER and the Seeker wallet throws 'input is not a valid solana cluster' */;
            if (auth.accounts == null || auth.accounts.length == 0) {
                throw new PayException("The wallet returned no account (step: authorize).");
            }
            String wallet = Base58.encode(auth.accounts[0].publicKey);
            Log.i(TAG, "authorized wallet=" + wallet);
            // 2) our server builds the unsigned transaction for this wallet + order
            JSONObject txReq = new JSONObject().put("ref", ref).put("wallet", wallet);
            step("building transaction");
            JSONObject txRes = postJson(baseUrl + "/pay/tx", txReq);
            if (txRes.has("error")) throw new PayException(txRes.optString("error", "could not build the transaction"));
            byte[] tx = Base64.decode(txRes.getString("tx"), Base64.DEFAULT);
            // 3) the wallet signs and broadcasts it
            step("waiting for signature");
            MobileWalletAdapterClient.SignAndSendTransactionsResult sent =
                    client.signAndSendTransactions(new byte[][]{tx}, null).get(SIGN_TIMEOUT_MS, TimeUnit.MILLISECONDS);
            if (sent.signatures == null || sent.signatures.length == 0 || sent.signatures[0] == null) {
                throw new PayException("The wallet returned no signature (step: sign).");
            }
            signature = Base58.encode(sent.signatures[0]);
        } catch (ExecutionException e) {
            throw unwrap(e);
        } catch (TimeoutException e) {
            throw new PayException("The wallet did not answer in time (step: approval). Tap CANCEL and try again.");
        } catch (java.util.concurrent.CancellationException e) {
            throw new UserDeclined();
        } finally {
            try {
                scenario.close();
            } catch (Throwable ignored) {
            }
        }
        // 4) our server verifies it on-chain (polls while the transaction propagates)
        step("confirming on-chain");
        for (int i = 0; i < CONFIRM_ATTEMPTS; i++) {
            JSONObject res = postJson(baseUrl + "/pay/confirm", new JSONObject().put("ref", ref).put("signature", signature));
            if (res.optBoolean("paid", false)) return signature;
            if (!res.optBoolean("pending", false)) {
                throw new PayException(res.optString("error", "The payment could not be verified."));
            }
            Thread.sleep(3000);
        }
        throw new PayException("Sent (" + signature.substring(0, 8) + "...), but not confirmed yet. The game keeps checking.");
    }

    private static Exception unwrap(ExecutionException e) {
        Throwable cause = e.getCause() != null ? e.getCause() : e;
        if (cause instanceof JsonRpc20Client.JsonRpc20RemoteException) {
            int code = ((JsonRpc20Client.JsonRpc20RemoteException) cause).code;
            // -3 = ERROR_AUTHORIZATION_FAILED (user declined), -1 = ERROR_NOT_SIGNED (declined signing)
            if (code == -3 || code == -1) return new UserDeclined();
            return new PayException("Wallet error " + code + ": " + cause.getMessage());
        }
        if (cause instanceof MobileWalletAdapterClient.InvalidPayloadsException) {
            return new PayException("The wallet rejected the transaction.");
        }
        if (cause instanceof MobileWalletAdapterClient.NotSubmittedException) {
            return new PayException("The wallet could not send the transaction.");
        }
        return new PayException("Wallet error: " + describe(cause));
    }

    private static String describe(Throwable t) {
        String m = t.getMessage();
        return (m == null || m.isEmpty()) ? t.getClass().getSimpleName() : m;
    }

    private static JSONObject postJson(String url, JSONObject body) throws Exception {
        HttpURLConnection conn = (HttpURLConnection) new URL(url).openConnection();
        conn.setConnectTimeout(15_000);
        conn.setReadTimeout(60_000);
        conn.setRequestMethod("POST");
        conn.setDoOutput(true);
        conn.setRequestProperty("Content-Type", "application/json");
        byte[] payload = body.toString().getBytes(StandardCharsets.UTF_8);
        try (OutputStream out = conn.getOutputStream()) {
            out.write(payload);
        }
        int code = conn.getResponseCode();
        InputStream in = code >= 400 ? conn.getErrorStream() : conn.getInputStream();
        String text = "";
        if (in != null) {
            ByteArrayOutputStream buf = new ByteArrayOutputStream();
            byte[] chunk = new byte[4096];
            int n;
            while ((n = in.read(chunk)) > 0) buf.write(chunk, 0, n);
            text = new String(buf.toByteArray(), StandardCharsets.UTF_8);
        }
        conn.disconnect();
        try {
            return new JSONObject(text.isEmpty() ? "{}" : text);
        } catch (Exception e) {
            throw new PayException("Server error " + code + " (step: server).");
        }
    }

    static class PayException extends Exception {
        PayException(String message) {
            super(message);
        }
    }

    static class UserDeclined extends PayException {
        UserDeclined() {
            super("declined");
        }
    }
}
