package org.godotengine.plugin.seekerwallet;

import java.math.BigInteger;

/** Bitcoin/Solana base58 (no checksum). Enough to print wallet addresses and transaction signatures. */
final class Base58 {
    private static final String ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz";
    private static final BigInteger FIFTY_EIGHT = BigInteger.valueOf(58);

    private Base58() {}

    static String encode(byte[] input) {
        if (input == null || input.length == 0) return "";
        int zeros = 0;
        while (zeros < input.length && input[zeros] == 0) zeros++;
        BigInteger num = new BigInteger(1, input);
        StringBuilder sb = new StringBuilder();
        while (num.signum() > 0) {
            BigInteger[] qr = num.divideAndRemainder(FIFTY_EIGHT);
            sb.append(ALPHABET.charAt(qr[1].intValue()));
            num = qr[0];
        }
        for (int i = 0; i < zeros; i++) sb.append('1');
        return sb.reverse().toString();
    }
}
