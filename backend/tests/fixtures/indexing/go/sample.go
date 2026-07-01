package sample

import "fmt"

type Greeter struct {
    Prefix string
}

func (g Greeter) Render(name string) string {
    return fmt.Sprintf("%s %s", g.Prefix, name)
}
