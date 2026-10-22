// Copyright 2026 Example Corp. License: MIT.

// ^ hazard id=top.S removing nonce => replay attacks

//^ hazard id=top.L removing nonce => replay attacks

// ^ invariant id=decl.S timeout > 0; #12
export function alpha(): number {
  return 1;
}

//^ invariant id=decl.L timeout > 0; #12
export function beta(): number {
  return 2;
}

export class Config {
  // ^ invariant id=field.S timeout > 0
  timeout = 1;
  //^ invariant id=field.L retries >= 0
  retries = 1;
}

export function work(): number {
  // ^ order id=body.S lock before write => deadlock
  const a = 1;
  //^ order id=body.L lock before write => deadlock
  const b = 2;
  return a + b;
}

export function trailing(): number {
  const x = 1; // ^ hazard id=trailing.S keep timeout => hang
  const y = 2; //^ hazard id=trailing.L keep timeout => hang
  return x + y;
}

declare function test(name: string, fn: () => void): void;

test("alpha", () => {
  // ^ why id=test.S pins legacy output => regression
  if (alpha() !== 1) throw new Error("alpha");
  //^ why id=test.L pins legacy output => regression
  if (beta() !== 2) throw new Error("beta");
});
