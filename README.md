# aur-sync-vote

![PyPI Python Version](https://img.shields.io/badge/python-3.10+-3776AB?style=flat&logo=python&logoColor=white)
![AUR Version](https://img.shields.io/aur/version/aur-sync-vote?style=flat&logo=archlinux&logoColor=white&color=1793D1)
![AUR Votes](https://img.shields.io/aur/votes/aur-sync-vote?style=flat&logo=archlinux&logoColor=white&color=1793D1)
![AUR Popularity](https://img.shields.io/aur/popularity/aur-sync-vote?style=flat&logo=archlinux&logoColor=white&color=1793D1)
![GitHub License](https://img.shields.io/github/license/acaibowlz/aur-sync-vote?style=flat&color=28A745)

`aur-sync-vote` is a fork of [aur-auto-vote](https://github.com/cryzed/bin/blob/master/aur-auto-vote), focused on syncing votes with the currently installed AUR packages.

![screenshot](https://raw.githubusercontent.com/acaibowlz/aur-sync-vote/refs/heads/master/.github/Screenshot%20From%202026-01-17%2016-01-12.png)

## Latest News

- **2026-06-23** - We've made it to the 1st place 🎉 Thank you all for the support 🥹
- **2026-04-06** - We have now surpassed `paru`, `visual-studio-code-bin` and come to the 2nd place 🥹
- **2026-02-21** - We got into the Top 10 🎉
- **2026-01-17** - `aur-sync-vote` was featured among the **Top 20 trending AUR packages** and the **most popular AUR voting tool**. Thanks to everyone who supported the project ❤️

## Features

- Securely stores login credentials via `org.freedesktop.secrets.service`
- Syncs votes for installed AUR packages and unvotes removed ones
- Supports syncing either all installed packages or explicitly installed ones
- Supports local repos for AUR helpers that build into one (e.g. `aurutils`)
- Avoids voting for non-installed split packages

## Usage

To vote for all installed AUR packages, and unvote for all uninstalled packages, run:

```
aur-sync-vote
```

To vote for all explicitly installed AUR packages, and unvote for the uninstalled ones, run:

```
aur-sync-vote --explicit
# or just aur-sync-vote -e
```

To remember credentials, run:

```
aur-sync-vote --remember
# or just aur-sync-vote -r
```

Wiping out stored credentials:

```
aur-sync-vote --clear
# or just aur-sync-vote -c
```

If your AUR helper builds packages into a local repo (e.g. `aurutils`), pacman does not report them as foreign, so they are not picked up by default. Name the repo to read the installed packages from it instead:

```
aur-sync-vote --database custom
# or just aur-sync-vote -D custom
```

Repeat the flag to use more than one local repo:

```
aur-sync-vote -D custom -D custom-testing
```

## Installation

### AUR

```
yay -S aur-sync-vote
```

### pipx

```
pipx install aur-sync-vote
```

### uv

```
uv tool install aur-sync-vote
```

## License

MIT
