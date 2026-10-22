import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { LedgerError } from "../src/errors.js";
import { MAX_AMOUNT_MINOR, formatAmount, parseAmount } from "../src/money.js";

function assertInvalid(input: string): void {
  assert.throws(
    () => parseAmount(input),
    (e: unknown) => e instanceof LedgerError && e.code === "INVALID_AMOUNT",
    `expected ${JSON.stringify(input)} to be rejected`,
  );
}

describe("parseAmount", () => {
  it("parses decimal strings exactly into integer minor units", () => {
    assert.equal(parseAmount("12.34"), 1234);
    assert.equal(parseAmount("0.01"), 1);
    assert.equal(parseAmount("0.10"), 10);
    assert.equal(parseAmount("12.3"), 1230);
    assert.equal(parseAmount("12"), 1200);
    assert.equal(parseAmount("1"), 100);
    assert.equal(parseAmount("007.05"), 705);
  });

  it("is exact where binary floating point is not", () => {
    assert.equal(parseAmount("0.07"), 7);
    assert.equal(parseAmount("1.15"), 115);
    assert.equal(parseAmount("19.99"), 1999);
    assert.equal(parseAmount("4.35"), 435);
    assert.equal(parseAmount("90071992547409.91"), 9007199254740991);
  });

  it("rejects more than 2 decimal places, even when the extras are zeros", () => {
    for (const s of ["1.001", "0.123", "1.230", "1.000", "5.999999"]) assertInvalid(s);
  });

  it("rejects exponents, NaN, Infinity and hex", () => {
    for (const s of ["1e3", "1E3", "1e-2", "NaN", "Infinity", "-Infinity", "0x10", "1_000"]) {
      assertInvalid(s);
    }
  });

  it("rejects empty, whitespace-only and padded input", () => {
    for (const s of ["", " ", " 1.00", "1.00 ", "1 .00", "\t1", "1\n"]) assertInvalid(s);
  });

  it("rejects malformed numbers", () => {
    for (const s of [".", ".5", "5.", "1..2", "1.2.3", "+1.00", "--1", "1,00", "1,000.00", "abc", "１２"]) {
      assertInvalid(s);
    }
  });

  it("rejects negative amounts with a clear message", () => {
    for (const s of ["-1", "-0.01", "-12.34", "-0"]) {
      assert.throws(
        () => parseAmount(s),
        (e: unknown) =>
          e instanceof LedgerError && e.code === "INVALID_AMOUNT" && /negative/i.test(e.message),
      );
    }
  });

  it("rejects zero because a transfer of nothing is meaningless", () => {
    for (const s of ["0", "0.00", "0.0", "000"]) {
      assert.throws(
        () => parseAmount(s),
        (e: unknown) =>
          e instanceof LedgerError && e.code === "INVALID_AMOUNT" && /positive/i.test(e.message),
      );
    }
  });

  it("rejects amounts above the supported maximum", () => {
    assert.equal(parseAmount("90071992547409.91"), MAX_AMOUNT_MINOR);
    assertInvalid("90071992547409.92");
    assertInvalid("99999999999999999999999.99");
  });
});

describe("formatAmount", () => {
  it("renders minor units as a 2-decimal string", () => {
    assert.equal(formatAmount(1234), "12.34");
    assert.equal(formatAmount(1), "0.01");
    assert.equal(formatAmount(10), "0.10");
    assert.equal(formatAmount(0), "0.00");
    assert.equal(formatAmount(100000), "1000.00");
  });

  it("renders negatives with a leading minus", () => {
    assert.equal(formatAmount(-1234), "-12.34");
    assert.equal(formatAmount(-5), "-0.05");
  });

  it("round-trips with parseAmount", () => {
    for (const minor of [1, 99, 100, 101, 123456789, MAX_AMOUNT_MINOR]) {
      assert.equal(parseAmount(formatAmount(minor)), minor);
    }
  });

  it("rejects non-integers", () => {
    assert.throws(() => formatAmount(1.5), RangeError);
    assert.throws(() => formatAmount(Number.NaN), RangeError);
  });
});
