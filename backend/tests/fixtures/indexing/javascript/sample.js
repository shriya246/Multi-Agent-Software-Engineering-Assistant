import { readFile } from "node:fs/promises";

export class Greeter {
  constructor(prefix) {
    this.prefix = prefix;
  }

  render(name) {
    return `${this.prefix} ${name}`;
  }
}

export function greet(name) {
  return `Hello, ${name}`;
}
