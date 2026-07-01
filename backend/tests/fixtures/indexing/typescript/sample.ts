export interface GreeterOptions {
  prefix: string;
}

export type Greeting = string;

export class Greeter {
  constructor(private readonly prefix: string) {}

  render(name: string): Greeting {
    return `${this.prefix} ${name}`;
  }
}
