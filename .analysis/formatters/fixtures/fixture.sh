#!/usr/bin/env bash
# Copyright 2026 Example Corp. License: MIT.

# ^ hazard id=top.S removing nonce => replay attacks

#^ hazard id=top.L removing nonce => replay attacks

# ^ invariant id=decl.S timeout > 0; #12
alpha() {
	return 0
}

#^ invariant id=decl.L timeout > 0; #12
beta() {
	return 1
}

work() {
	# ^ order id=body.S lock before write => deadlock
	local a=1
	#^ order id=body.L lock before write => deadlock
	local b=2
	echo $((a + b))
}

trailing() {
	local x=1 # ^ hazard id=trailing.S keep timeout => hang
	local y=2 #^ hazard id=trailing.L keep timeout => hang
	echo $((x + y))
}

test_alpha() {
	# ^ why id=test.S pins legacy output => regression
	[ "$(alpha; echo $?)" = "0" ] || return 1
	#^ why id=test.L pins legacy output => regression
	[ "$(beta; echo $?)" = "1" ] || return 1
}
