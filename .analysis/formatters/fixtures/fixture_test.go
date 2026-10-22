// Copyright 2026 Example Corp. License: MIT.

// ^ hazard id=top.S removing nonce => replay attacks

//^ hazard id=top.L removing nonce => replay attacks

package fixture

import "testing"

// ^ invariant id=decl.S timeout > 0; #12
func alpha() int {
	return 1
}

//^ invariant id=decl.L timeout > 0; #12
func beta() int {
	return 2
}

type Config struct {
	// ^ invariant id=field.S timeout > 0
	Timeout int
	//^ invariant id=field.L retries >= 0
	Retries int
}

func work() int {
	// ^ order id=body.S lock before write => deadlock
	a := 1
	//^ order id=body.L lock before write => deadlock
	b := 2
	return a + b
}

func trailing() int {
	x := 1 // ^ hazard id=trailing.S keep timeout => hang
	y := 2 //^ hazard id=trailing.L keep timeout => hang
	return x + y
}

func TestAlpha(t *testing.T) {
	// ^ why id=test.S pins legacy output => regression
	if alpha() != 1 {
		t.Fatal("alpha")
	}
	//^ why id=test.L pins legacy output => regression
	if beta() != 2 {
		t.Fatal("beta")
	}
}
