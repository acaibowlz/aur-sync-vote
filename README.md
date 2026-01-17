# aur-sync-vote

![screenshot](https://raw.githubusercontent.com/acaibowlz/aur-sync-vote/refs/heads/master/.github/Screenshot%20From%202026-01-17%2016-01-12.png)

## Achievements

- **2026-01-17** — We are featured among the **Top 20 trending AUR packages** and **#1 AUR voting tool**.
  Thanks to everyone who supported the project ❤️

## Intro

This is a fork of [aur-auto-vote](https://github.com/cryzed/bin/blob/master/aur-auto-vote), with the focus of syncing votes to currently installed AUR packages.

While dropping the redundant options from the original script, `aur-sync-vote` implemented a new feature that lets you decide to sync all the AUR packages or the ones that are explicitly installed only.

Beside that, `aur-sync-vote` also handles split packages better, as it will vote for the correct package base and will not attempt to unvote a split package that is not installed.

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
