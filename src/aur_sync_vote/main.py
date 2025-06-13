import argparse
import collections
import getpass
import os
import subprocess
import time
from pathlib import Path

import bs4
import requests
from typing_extensions import Set

EXIT_FAILURE = 1
LOGIN_URL = "https://aur.archlinux.org/login"
SEARCH_URL_TEMPLATE = "https://aur.archlinux.org/packages/?O=%d&SB=w&SO=d&PP=250&do_Search=Go"
PACKAGES_URL = "https://aur.archlinux.org/packages/%s"
VOTE_URL_TEMPLATE = "https://aur.archlinux.org/pkgbase/%s/vote/"
UNVOTE_URL_TEMPLATE = "https://aur.archlinux.org/pkgbase/%s/unvote/"
PACKAGES_PER_PAGE = 250
XDG_DATA_HOME = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
CREDS_FILE = XDG_DATA_HOME / "aur-sync-vote" / "credentials"

Package = collections.namedtuple(
    "Package",
    (
        "name",
        "version",
        "votes",
        "popularity",
        "voted",
        "notify",
        "description",
        "maintainer",
        "updated",
    ),
)


def validate_stored_credentials():
    try:
        with open(CREDS_FILE, "r") as f:
            return len(f.read().splitlines()) == 2
    except FileNotFoundError:
        return False


def load_credentials():
    with open(CREDS_FILE, "r") as f:
        username, password = f.read().splitlines()
        return username, password


def save_credentials(username, password):
    if not CREDS_FILE.parent.exists():
        CREDS_FILE.parent.mkdir(parents=True)
    if not CREDS_FILE.exists():
        CREDS_FILE.touch()
    with open(CREDS_FILE, "w") as f:
        f.write(f"{username}\n{password}")


def login(session, username, password):
    response = session.post(
        LOGIN_URL,
        {"user": username, "passwd": password, "next": "/"},
        headers={"referer": "https://aur.archlinux.org/login"},
    )
    soup = bs4.BeautifulSoup(response.text, "html5lib")
    return bool(
        soup.select_one("#archdev-navbar").find(
            "form", action=lambda h: h and h.rstrip("/").endswith("/logout")
        )
    )


def get_foreign_packages(explicitly_installed: bool = False) -> list[str]:
    if explicitly_installed:
        return subprocess.check_output(("pacman", "-Qqme"), universal_newlines=True).splitlines()
    return subprocess.check_output(("pacman", "-Qqm"), universal_newlines=True).splitlines()


def get_voted_packages(session):
    offset = 0
    while True:
        response = session.get(SEARCH_URL_TEMPLATE % offset)
        soup = bs4.BeautifulSoup(response.text, "html5lib")
        for row in soup.select(".results > tbody > tr"):
            package = Package(*(c.get_text(strip=True) for c in row.select(":scope > td")[1:]))
            if not package.voted:
                return
            yield package
        offset += PACKAGES_PER_PAGE


def get_package_base(session, package):
    response = session.get(PACKAGES_URL % package)
    soup = bs4.BeautifulSoup(response.text, "html5lib")

    table = soup.find("table", {"id": "pkginfo"})
    if not table:
        return None
    for row in table.find_all("tr"):
        header = row.find("th")
        if header and header.text.strip() == "Package Base:":
            td = row.find("td")
            if td:
                return td.text.strip()
    return None


def vote_package(session, package):
    response = session.post(
        VOTE_URL_TEMPLATE % package,
        {"do_Vote": "Vote for this package"},
        allow_redirects=True,
    )
    return response.status_code == requests.codes.ok


def unvote_package(session, package):
    response = session.post(
        UNVOTE_URL_TEMPLATE % package,
        {"do_UnVote": "Remove vote"},
        allow_redirects=True,
    )
    return response.status_code == requests.codes.ok


def cli():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--explicit",
        "-e",
        action="store_true",
        help="Sync votes for explicitly installed packages only",
    )
    parser.add_argument(
        "--delay",
        "-d",
        type=float,
        default=0,
        help="Delay between voting actions (seconds).",
    )
    parser.add_argument("--remember", "-r", action="store_true", help="Remember login credentials")
    arguments = parser.parse_args()

    if validate_stored_credentials():
        username, password = load_credentials()
    else:
        username = input("Username: ")
        password = getpass.getpass("Password: ")
    if arguments.remember:
        save_credentials(username, password)

    session = requests.Session()
    if not login(session, username, password):
        raise SystemExit("Could not login.")
    print("Collecting voted packages...")
    voted_packages = tuple(p.name for p in sorted(get_voted_packages(session)))

    if arguments.explicit:
        foreign_packages = set(get_foreign_packages(explicitly_installed=True))
    else:
        foreign_packages = set(get_foreign_packages())
    voted_packages = set(voted_packages)
    for package in sorted(foreign_packages.difference(voted_packages)):
        print("Voting for package: %s... " % package, end="", flush=True)
        package_base = get_package_base(session, package)
        if vote_package(session, package_base):
            print("done.")
        else:
            print("failed.")
        time.sleep(arguments.delay)
    for package in sorted(voted_packages.difference(foreign_packages)):
        package_base = get_package_base(session, package)
        if package_base in foreign_packages:
            continue
        print("Unvoting for package: %s... " % package, end="", flush=True)
        if unvote_package(session, package_base):
            print("done.")
        else:
            print("failed.")
        time.sleep(arguments.delay)
    print("Sync done!")


def main():
    try:
        cli()
    except KeyboardInterrupt:
        raise SystemExit("\nInterrupted!")
    except Exception as e:
        raise SystemExit(f"Unexpected error: {e}")
