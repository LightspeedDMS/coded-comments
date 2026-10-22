#!/usr/bin/env -S node --disable-warning=ExperimentalWarning
import { main } from "./cli.js";

process.exitCode = main(process.argv.slice(2), process.env, {
  out: (line) => process.stdout.write(`${line}\n`),
  err: (line) => process.stderr.write(`${line}\n`),
});
