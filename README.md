# aur-sync-vote

`aur-sync-vote` is a fork of [aur-auto-vote](https://github.com/cryzed/bin/blob/master/aur-auto-vote), focused on syncing votes with the currently installed AUR packages.

![screenshot](https://raw.githubusercontent.com/acaibowlz/aur-sync-vote/refs/heads/master/.github/Screenshot%20From%202026-01-17%2016-01-12.png)

## Achievements

- **2026-01-17** — `aur-sync-vote` was featured among the **Top 20 trending AUR packages** and the **most popular AUR voting tool**. Thanks to everyone who supported the project ❤️

## Features

- Securely stores login credentials via `org.freedesktop.secrets.service`
- Syncs votes for installed AUR packages and unvotes removed ones
- Supports syncing either all installed packages or explicitly installed ones
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
