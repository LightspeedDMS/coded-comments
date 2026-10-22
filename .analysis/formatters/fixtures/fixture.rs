// Copyright 2026 Example Corp. License: MIT.

// ^ hazard id=top.S removing nonce => replay attacks

//^ hazard id=top.L removing nonce => replay attacks

// ^ invariant id=decl.S timeout > 0; #12
pub fn alpha() -> i32 {
    1
}

//^ invariant id=decl.L timeout > 0; #12
pub fn beta() -> i32 {
    2
}

pub struct Config {
    // ^ invariant id=field.S timeout > 0
    pub timeout: i32,
    //^ invariant id=field.L retries >= 0
    pub retries: i32,
}

pub fn work() -> i32 {
    // ^ order id=body.S lock before write => deadlock
    let a = 1;
    //^ order id=body.L lock before write => deadlock
    let b = 2;
    a + b
}

pub fn trailing() -> i32 {
    let x = 1; // ^ hazard id=trailing.S keep timeout => hang
    let y = 2; //^ hazard id=trailing.L keep timeout => hang
    x + y
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_alpha() {
        // ^ why id=test.S pins legacy output => regression
        assert_eq!(alpha(), 1);
        //^ why id=test.L pins legacy output => regression
        assert_eq!(beta(), 2);
    }
}
