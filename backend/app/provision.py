"""Local administrative CLI. No seeded identity or password; prompt without echo."""
import argparse
from getpass import getpass, GetPassWarning
import os
import re
import sys
import warnings
from .auth import hash_password
from .store import PostgresStore


def main():
    parser = argparse.ArgumentParser(description="Provision or revoke local app users")
    parser.add_argument("command", choices=["create-user", "set-role", "block-user", "unblock-user", "revoke-sessions"])
    parser.add_argument("username")
    parser.add_argument("--role", choices=["admin", "viewer"])
    parser.add_argument("--display-name")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9][a-z0-9_.-]{2,63}", args.username):
        parser.error("Username must be 3-64 lowercase letters/digits, underscore, dot or hyphen")
    if args.command in {"create-user", "set-role"} and not args.role:
        parser.error("An explicit role is required")
    try:
        store = PostgresStore(os.environ.get("DATABASE_URL", ""))
        store.ready()
        if args.command == "create-user":
            if not args.display_name or not 1 <= len(args.display_name) <= 80:
                parser.error("An explicit display name of 1-80 characters is required")
            if not sys.stdin.isatty():
                parser.error("Password provisioning requires an interactive terminal; no echo fallback")
            with warnings.catch_warnings():
                warnings.simplefilter("error", GetPassWarning)
                password = getpass("New password (16-256 characters): ")
                confirmation = getpass("Confirm password: ")
            if password != confirmation:
                parser.error("Passwords do not match")
            store.create_user(args.username, args.display_name, args.role, hash_password(password))
        else:
            store.change_user(args.username, role=args.role if args.command == "set-role" else None,
                              blocked=True if args.command == "block-user" else False if args.command == "unblock-user" else None)
    except Exception:
        parser.exit(1, "Administrative operation failed; inspect local database configuration and user state.\n")
    print("Administrative operation completed; affected sessions revoked where applicable")


if __name__ == "__main__":
    main()
