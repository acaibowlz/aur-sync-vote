import argparse
import getpass
import subprocess
import sys
import time
from dataclasses import dataclass

import bs4
import keyring
import requests
from keyring.errors import KeyringError, NoKeyringError

SERVICE_NAME = "aur-sync-vote"

LOGIN_URL = "https://aur.archlinux.org/login"
SEARCH_URL_TEMPLATE = "https://aur.archlinux.org/packages/?O=%d&SB=w&SO=d&PP=250&do_Search=Go"
PACKAGES_URL = "https://aur.archlinux.org/packages/%s"
VOTE_URL_TEMPLATE = "https://aur.archlinux.org/pkgbase/%s/vote"
UNVOTE_URL_TEMPLATE = "https://aur.archlinux.org/pkgbase/%s/unvote"
PACKAGES_PER_PAGE = 250


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
    try:
        keyring.get_credential(SERVICE_NAME, None)
        return True
    except NoKeyringError:
        return False
    except KeyringError:
        return False


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
    response = session.post(
        LOGIN_URL,
        {"user": username, "passwd": password, "next": "/"},
        headers={"referer": "https://aur.archlinux.org/login"},
    )
    soup = bs4.BeautifulSoup(response.text, "html5lib")
    return bool(
        soup.select_one("#archdev-navbar").find("form", action=lambda h: h and h.rstrip("/").endswith("/logout"))
    )


def get_installed_packages(explicitly_installed: bool = False) -> list[str]:
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


def get_pkgbase(session: requests.Session, package: str) -> str:
    response = session.get(PACKAGES_URL % package)
    soup = bs4.BeautifulSoup(response.text, "html5lib")

    table = soup.find("table", {"id": "pkginfo"})
    if not table:
        raise RuntimeError(f"pkginfo table not found for {package}")
    for row in table.find_all("tr"):
        header = row.find("th")
        if header and header.text.strip() == "Package Base:":
            td = row.find("td")
            if td:
                return td.text.strip()
    raise RuntimeError(f"pkgbase not found for {package}")


def vote_package(session: requests.Session, package: str) -> bool:
    response = session.post(
        VOTE_URL_TEMPLATE % package, {"do_Vote": "Vote for this package"}, allow_redirects=True, timeout=30
    )
    return response.status_code == requests.codes.ok


def unvote_package(session: requests.Session, package: str) -> bool:
    response = session.post(
        UNVOTE_URL_TEMPLATE % package, {"do_UnVote": "Remove vote"}, allow_redirects=True, timeout=30
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
    args = parser.parse_args()

    if (args.remember or args.clear) and not keyring_available():
        print(
            "⚠️  No secure keyring backend available.\n\nTo enable credential storage, install a Secret Service provider (e.g. GNOME Keyring or KWallet) that implements org.freedesktop.secrets."
        )
        sys.exit(1)
    if args.clear:
        if not credentials_exist():
            print("⚠️ No saved credentials found")
            sys.exit(0)
        clear_credentials()
        print("✅ Credentials cleared")
        sys.exit(0)

    if keyring_available() and credentials_exist():
        username, password = load_credentials()
    else:
        username = input("🔐 Username: ")
        password = getpass.getpass("🔐 Password: ")
    if args.remember:
        save_credentials(username, password)
        print("💾 Credentials saved")

    session = requests.Session()
    if not login(session, username, password):
        print("❌ Could not login")
        sys.exit(1)
    print("ℹ️  Collecting voted packages...")
    voted_packages = set(p.name for p in get_voted_packages(session))

    if args.explicit:
        foreign_packages = set(get_installed_packages(explicitly_installed=True))
    else:
        foreign_packages = set(get_installed_packages())
    for package in sorted(foreign_packages.difference(voted_packages)):
        print("🗳️ Voting for package: %s... " % package, end="", flush=True)
        package_base = get_pkgbase(session, package)
        if vote_package(session, package_base):
            print("✅ done")
        else:
            print("❌ failed")
        time.sleep(args.delay)
    for package in sorted(voted_packages.difference(foreign_packages)):
        package_base = get_pkgbase(session, package)
        if package_base in foreign_packages:
            continue
        print("🗳️ Unvoting for package: %s... " % package, end="", flush=True)
        if unvote_package(session, package_base):
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
