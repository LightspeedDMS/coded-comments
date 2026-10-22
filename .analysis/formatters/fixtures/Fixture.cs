/* Copyright 2026 Example Corp. License: MIT. */

// ^ hazard id=top.S removing nonce => replay attacks

//^ hazard id=top.L removing nonce => replay attacks

using Xunit;

namespace Fixture;

// ^ invariant id=decl.S timeout > 0; #12
public class Alpha
{
    public int Value()
    {
        return 1;
    }
}

//^ invariant id=decl.L timeout > 0; #12
public class Beta
{
    public int Value()
    {
        return 2;
    }
}

public class Config
{
    // ^ invariant id=field.S timeout > 0
    public int Timeout = 1;
    //^ invariant id=field.L retries >= 0
    public int Retries = 1;

    public int Work()
    {
        // ^ order id=body.S lock before write => deadlock
        int a = 1;
        //^ order id=body.L lock before write => deadlock
        int b = 2;
        return a + b;
    }

    public int Trailing()
    {
        int x = 1; // ^ hazard id=trailing.S keep timeout => hang
        int y = 2; //^ hazard id=trailing.L keep timeout => hang
        return x + y;
    }
}

public class ConfigTest
{
    [Fact]
    public void TestAlpha()
    {
        // ^ why id=test.S pins legacy output => regression
        Assert.Equal(1, new Alpha().Value());
        //^ why id=test.L pins legacy output => regression
        Assert.Equal(2, new Beta().Value());
    }
}
