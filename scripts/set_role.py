"""Set a registered account's role: python -m scripts.set_role EMAIL ROLE"""
import argparse
import sys
from typing import get_args

from app.repositories import customer_repo
from app.schemas.customer import Role


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Set the role of a registered account.")
    parser.add_argument("email", help="email the account was registered with")
    parser.add_argument("role", choices=get_args(Role))
    args = parser.parse_args(argv)
    try:
        account = customer_repo.set_role(args.email, args.role)
    except customer_repo.CustomerRecordNotFoundError:
        print(f"No account is registered with {args.email}.", file=sys.stderr)
        return 1
    print(f"{account['email']} is now {account['role']}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
