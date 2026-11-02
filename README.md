# meridian-terrapin

Terrapin's bond data in an [Open Meridian](https://open-meridian.dev)
deployment: an Apache-2.0 plugin, in Python on the open-meridian SDK 0.35.3
(contract v29), built from Terrapin's public API documentation.

It holds two roles:

- **`data`** -- government par yield curves (US, UK, Germany), inflation
  index levels, and municipal bonds' prints as MSRB disseminates them, into
  the deployment's lake;
- **`reference`** -- the terms of the bonds and CDs a deployment lists,
  offered to its instrument records under the `bond` and
  `certificate_of_deposit` templates, the issuer by its LEI.

Terrapin's end-of-day prices are not recorded until Terrapin states their
source and whether they are clean or dirty; see
[docs/overview.md](docs/overview.md).

You need a Terrapin API key on the subscription your use calls for; the
terms are yours and Terrapin's to settle ([docs/terms.md](docs/terms.md)).

## Using it

[docs/setup.md](docs/setup.md) says how to launch it, its settings and its
datasets; [docs/pages.md](docs/pages.md) its pages;
[docs/troubleshooting.md](docs/troubleshooting.md) what each state means.

## Developing it

`AGENTS.md` is the plugin's guide for people and coding agents alike.

    make ci-remote     # lint and tests, in a container
    make check         # meridian plugin check --verified --run-tests
    make e2e           # the plugin on the plugin harness, on sample data
    make preview SHOTS=<dir>   # its pages in a browser, at 375, 582 and 1280 px

Changes land through a pull request; CI (`ci`, `check`, `e2e`) is the gate.
