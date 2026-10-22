#!/usr/bin/env python3
# Copyright 2026 Example Corp. License: MIT.

# ^ hazard id=top.S removing nonce => replay attacks

#^ hazard id=top.L removing nonce => replay attacks

from dataclasses import dataclass


# ^ invariant id=decl.S timeout > 0; #12
def alpha():
    return 1


#^ invariant id=decl.L timeout > 0; #12
def beta():
    return 2


@dataclass
class Config:
    # ^ invariant id=field.S timeout > 0
    timeout: int = 1
    #^ invariant id=field.L retries >= 0
    retries: int = 1


def work():
    # ^ order id=body.S lock before write => deadlock
    a = 1
    #^ order id=body.L lock before write => deadlock
    b = 2
    return a + b


def trailing():
    x = 1  # ^ hazard id=trailing.S keep timeout => hang
    y = 2  #^ hazard id=trailing.L keep timeout => hang
    return x + y


def test_alpha():
    # ^ why id=test.S pins legacy output => regression
    assert alpha() == 1
    #^ why id=test.L pins legacy output => regression
    assert beta() == 2
