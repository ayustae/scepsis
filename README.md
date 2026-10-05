# Scepsis

**Scepsis** is a personal AI harness for managing work items locally. It includes `chreos`, a task, project and decision manager CLI, and a set of skill, agent, and tool definitions.

## Why Scepsis?

*Skepsis* is Greek for inquiry and doubt, the root of "sceptic". It names the place the AI is meant to have within this framework: the AI model will do most of the work and most of the time it will be correct, but it is never to be blindly trusted — it should always be challenged and verified before being accepted.

## Getting started

```sh
./installer/install.sh
```

This installs the `chreos` and `idion` CLIs, plus the skills and agents for every AI assistant it finds (Claude Code, Codex, OpenCode), without modifying existing files. Options are described in the [installation guide](docs/usage/installation.md). Then initialize `chreos` as described in [`tools/chreos/README.md`](tools/chreos/README.md).

## Documentation

See [`docs/`](docs/README.md): the system designs and the [chreos command reference](docs/cli/chreos/README.md). What changed in each version is in [`CHANGELOG.md`](CHANGELOG.md).

## License

MIT — see [`LICENSE`](LICENSE).
