using System;

namespace Sample;

public class Greeter
{
    public const string Constant = "value";

    public string Render(string name)
    {
        return $"Hello, {name}";
    }
}
