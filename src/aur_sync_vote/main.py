import argparse
import getpass
import subprocess
import sys
import time
from dataclasses import dataclass
from importlib.metadata import version

import bs4
import keyring
import random
import requests
from keyring.backends import fail
from keyring.errors import NoKeyringError

SERVICE_NAME = "aur-sync-vote"

LOGIN_URL = "https://aur.archlinux.org/login"
SEARCH_URL_TEMPLATE = "https://aur.archlinux.org/packages/?O=%d&SB=w&SO=d&PP=250&do_Search=Go"
PACKAGES_URL = "https://aur.archlinux.org/packages/%s"
VOTE_URL_TEMPLATE = "https://aur.archlinux.org/pkgbase/%s/vote"
UNVOTE_URL_TEMPLATE = "https://aur.archlinux.org/pkgbase/%s/unvote"
PACKAGES_PER_PAGE = 250

# Rate Limiting settings
MAX_RETRIES = 5
BASE_DELAY = 1
MAX_DELAY = 60


def calculate_delay(attempt: int) -> float:
    delay = BASE_DELAY * (2 ** attempt)
    delay = min(delay, MAX_DELAY)
    jitter = random.uniform(0.75, 1.25)
    return delay * jitter


def request_with_retry(
    session: requests.Session,
    method: str,
    url: str,
    max_retries: int = MAX_RETRIES,
    **kwargs,
) -> requests.Response:
    for attempt in range(max_retries + 1):
        request_method = getattr(session, method.lower())
        response = request_method(url, **kwargs)

        if response.status_code != 429:
            return response

        if attempt >= max_retries:
            return response

        delay = calculate_delay(attempt)
        time.sleep(delay)

class PackageNotFoundError(Exception):
    pass


class AURPageContentError(Exception):
    pass


@dataclass
class Package:
    name: str
    version: str
    votes: str
    popularity: str
    voted: str
    notify: str
    description: str
    maintainer: str
    updated: str


def keyring_available() -> bool:
    keyring_backend = keyring.get_keyring()
    if isinstance(keyring_backend, fail.Keyring):
        return False
    return True


def credentials_exist() -> bool:
    creds = keyring.get_credential(SERVICE_NAME, None)
    if creds is None or creds.username is None:
        return False
    password = keyring.get_password(SERVICE_NAME, creds.username)
    if password is None:
        return False
    return True


def load_credentials() -> tuple[str, str]:
    creds = keyring.get_credential(SERVICE_NAME, None)
    if creds is None or creds.username is None:
        raise NoKeyringError("No stored credentials found.")

    password = keyring.get_password(SERVICE_NAME, creds.username)
    if password is None:
        raise NoKeyringError("Stored credentials are incomplete.")

    return creds.username, password


def save_credentials(username: str, password: str) -> None:
    keyring.set_password(SERVICE_NAME, username, password)


def clear_credentials() -> None:
    creds = keyring.get_credential(SERVICE_NAME, None)
    if creds is None or creds.username is None:
        raise NoKeyringError("No stored credentials found.")
    keyring.delete_password(SERVICE_NAME, creds.username)


def login(session: requests.Session, username: str, password: str):
    print("📦 Logging in to AUR...")
    response = request_with_retry(
        session,
        "post",
        LOGIN_URL,
        data={"user": username, "passwd": password, "next": "/"},
        headers={"referer": "https://aur.archlinux.org/login"},
    )
    soup = bs4.BeautifulSoup(response.text, "html5lib")
    return bool(
        soup.select_one("#archdev-navbar").find("form", action=lambda h: h and h.rstrip("/").endswith("/logout"))
    )


def get_foreign_pkgs(explicitly_installed: bool = False) -> list[str]:
    if explicitly_installed:
        return subprocess.check_output(("pacman", "-Qqme"), universal_newlines=True).splitlines()
    return subprocess.check_output(("pacman", "-Qqm"), universal_newlines=True).splitlines()


def get_voted_pkgs(session):
    offset = 0
    while True:
        response = request_with_retry(session, "get", SEARCH_URL_TEMPLATE % offset)
        soup = bs4.BeautifulSoup(response.text, "html5lib")
        for row in soup.select(".results > tbody > tr"):
            pkg = Package(*(c.get_text(strip=True) for c in row.select(":scope > td")[1:]))
            if not pkg.voted:
                return
            yield pkg
        offset += PACKAGES_PER_PAGE


def get_pkgbase(session: requests.Session, pkg: str) -> str:
    response = request_with_retry(session, "get", PACKAGES_URL % pkg)
    soup = bs4.BeautifulSoup(response.text, "html5lib")

    error_page = soup.find("div", {"id": "error-page"})
    if error_page:
        raise PackageNotFoundError(f"Package not found in AUR: {pkg}")

    table = soup.find("table", {"id": "pkginfo"})
    if table is None:
        raise AURPageContentError(f"pkginfo table not found for {pkg}")

    a = table.select_one('a[href^="/pkgbase/"]')
    if not a or not a.get("href"):
        raise AURPageContentError(f"pkgbase not shown in pkginfo table for {pkg}")

    href = a["href"].rstrip("/")
    pkgbase = href.split("/")[-1].strip()
    if not pkgbase:
        raise AURPageContentError(f"pkgbase not shown in pkginfo table for {pkg}")

    return pkgbase


def vote_pkg(session: requests.Session, pkg: str) -> bool:
    response = request_with_retry(
        session,
        "post",
        VOTE_URL_TEMPLATE % pkg,
        data={"do_Vote": "Vote for this package"},
        allow_redirects=True,
        timeout=30,
    )
    return response.status_code == requests.codes.ok


def unvote_pkg(session: requests.Session, pkg: str) -> bool:
    response = request_with_retry(
        session,
        "post",
        UNVOTE_URL_TEMPLATE % pkg,
        data={"do_UnVote": "Remove vote"},
        allow_redirects=True,
        timeout=30,
    )
    return response.status_code == requests.codes.ok


def cli():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--explicit",
        "-e",
        action="store_true",
        help="sync votes for explicitly installed packages only",
    )
    parser.add_argument(
        "--delay",
        "-d",
        type=float,
        default=0,
        help="delay between voting actions (seconds)",
    )
    parser.add_argument("--remember", "-r", action="store_true", help="remember login credentials")
    parser.add_argument("--clear", "-c", action="store_true", help="clear stored credentials and exit")
    parser.add_argument("--version", "-v", action="store_true", help="show version and exit")
    args = parser.parse_args()

    if args.version:
        print(version("aur-sync-vote"))
        sys.exit(0)
    if (args.remember or args.clear) and not keyring_available():
        print(
            "⚠️ No secure keyring backend available.\n\nTo enable credential storage, install a Secret Service provider (e.g. GNOME Keyring or KWallet) that implements org.freedesktop.secrets."
        )
        sys.exit(1)
    if args.clear:
        if not credentials_exist():
            print("⚠️ No saved credentials found")
            sys.exit(0)
        clear_credentials()
        print("✅ Credentials cleared")
        sys.exit(0)

    if args.remember and credentials_exist():
        print("⚠️ Saved credentials exist. Overwrite? (Y/n) ", end="", flush=True)
        resp = input()
        if not resp or resp.lower() == "y":
            username = input("🔐 Username: ")
            password = getpass.getpass("🔐 Password: ")
            save_credentials(username, password)
            print("💾 Credentials saved")
        elif resp.lower() == "n":
            username, password = load_credentials()
            print("💾 Using saved credentials")
        else:
            print("❌ Invalid response, exiting")
            sys.exit(1)
    elif args.remember and not credentials_exist():
        username = input("🔐 Username: ")
        password = getpass.getpass("🔐 Password: ")
        save_credentials(username, password)
        print("💾 Credentials saved")
    elif credentials_exist():
        username, password = load_credentials()
        print("💾 Using saved credentials")
    else:
        username = input("🔐 Username: ")
        password = getpass.getpass("🔐 Password: ")

    session = requests.Session()
    if not login(session, username, password):
        print("❌ Could not login (invalid credentials)")
        sys.exit(1)
    print("ℹ️ Collecting voted packages...")
    voted_pkgs = set(p.name for p in get_voted_pkgs(session))

    if args.explicit:
        foreign_pkgs = set(get_foreign_pkgs(explicitly_installed=True))
    else:
        foreign_pkgs = set(get_foreign_pkgs())
    for pkg in sorted(foreign_pkgs.difference(voted_pkgs)):
        print("🗳️ Voting for package: %s... " % pkg, end="", flush=True)
        try:
            pkgbase = get_pkgbase(session, pkg)
        except PackageNotFoundError:
            print("⚠️ not found in AUR, skipping")
            continue
        if vote_pkg(session, pkgbase):
            print("✅ done")
        else:
            print("❌ failed")
        time.sleep(args.delay)
    for pkg in sorted(voted_pkgs.difference(foreign_pkgs)):
        # voted packages must be in AUR
        pkgbase = get_pkgbase(session, pkg)
        if pkgbase in foreign_pkgs:
            continue
        print("🗳️ Unvoting for package: %s... " % pkg, end="", flush=True)
        if unvote_pkg(session, pkgbase):
            print("✅ done")
        else:
            print("❌ failed")
        time.sleep(args.delay)
    print("🎉 Sync done!")


def main():
    try:
        cli()
    except KeyboardInterrupt:
        raise SystemExit("\n🛑 Interrupted!")
    except Exception as e:
        raise SystemExit(f"❌ Unexpected error: {e}")
