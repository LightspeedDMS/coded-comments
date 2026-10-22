-- Copyright 2026 Example Corp. License: MIT.

-- ^ hazard id=top.S removing nonce => replay attacks

--^ hazard id=top.L removing nonce => replay attacks

-- ^ invariant id=decl.S timeout > 0; #12
CREATE TABLE config (
    -- ^ invariant id=field.S timeout > 0
    timeout INTEGER,
    --^ invariant id=field.L retries >= 0
    retries INTEGER
);

--^ invariant id=decl.L timeout > 0; #12
CREATE TABLE other (
    id INTEGER,
    name VARCHAR(10) -- ^ hazard id=trailing.S keep timeout => hang
);

CREATE TABLE third (
    id INTEGER,
    name VARCHAR(10) --^ hazard id=trailing.L keep timeout => hang
);

SELECT
    -- ^ order id=body.S lock before write => deadlock
    timeout,
    --^ order id=body.L lock before write => deadlock
    retries
FROM config;

-- ^ why id=test.S pins legacy output => regression
SELECT COUNT(*) AS n FROM config;

--^ why id=test.L pins legacy output => regression
SELECT COUNT(*) AS m FROM other;
