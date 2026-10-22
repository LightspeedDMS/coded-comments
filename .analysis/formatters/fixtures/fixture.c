/* Copyright 2026 Example Corp. License: MIT. */

// ^ hazard id=top.S removing nonce => replay attacks

//^ hazard id=top.L removing nonce => replay attacks

#include <assert.h>

// ^ invariant id=decl.S timeout > 0; #12
int alpha(void) {
  return 1;
}

//^ invariant id=decl.L timeout > 0; #12
int beta(void) {
  return 2;
}

struct config {
  // ^ invariant id=field.S timeout > 0
  int timeout;
  //^ invariant id=field.L retries >= 0
  int retries;
};

int work(void) {
  // ^ order id=body.S lock before write => deadlock
  int a = 1;
  //^ order id=body.L lock before write => deadlock
  int b = 2;
  return a + b;
}

int trailing(void) {
  int x = 1; // ^ hazard id=trailing.S keep timeout => hang
  int y = 2; //^ hazard id=trailing.L keep timeout => hang
  return x + y;
}

static void test_alpha(void) {
  // ^ why id=test.S pins legacy output => regression
  assert(alpha() == 1);
  //^ why id=test.L pins legacy output => regression
  assert(beta() == 2);
}
