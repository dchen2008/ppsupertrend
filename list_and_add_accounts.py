#!/usr/bin/env python3
"""
List all OANDA accounts under an API key and optionally add them to src/config.py

Usage:
    # List all accounts under a specific API key
    python3 list_and_add_accounts.py key="your-api-key-here"

    # List accounts for an existing account in config (uses its API key)
    python3 list_and_add_accounts.py at=account1

    # List accounts and add new ones to config with a prefix
    python3 list_and_add_accounts.py key="your-api-key" prefix=demo add

    # List accounts from all unique API keys in config
    python3 list_and_add_accounts.py all

    # Dry run - show what would be added without modifying config
    python3 list_and_add_accounts.py key="your-api-key" prefix=newacct add dry-run

Options:
    key=        API key to query (required unless 'at=' or 'all' is used)
    at=         Use API key from existing account in config (e.g., at=account1)
    prefix=     Prefix for new account names (default: 'sub')
    add         Add new accounts to src/config.py
    dry-run     Show what would be done without making changes
    all         List accounts for all unique API keys in config
"""

import os
import sys
import re
import requests

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def get_accounts_from_api(api_key: str, is_practice: bool = True) -> list:
    """
    Fetch all accounts associated with an API key.

    Args:
        api_key: OANDA API key
        is_practice: If True, use practice API; else use live API

    Returns:
        List of account dictionaries with 'id' and 'tags' keys
    """
    base_url = "https://api-fxpractice.oanda.com" if is_practice else "https://api-fxtrade.oanda.com"
    url = f"{base_url}/v3/accounts"

    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data.get('accounts', [])
    except requests.exceptions.HTTPError as e:
        if response.status_code == 401:
            print(f"Error: Invalid or unauthorized API key")
        else:
            print(f"HTTP Error: {e}")
        return []
    except Exception as e:
        print(f"Error fetching accounts: {e}")
        return []


def get_existing_accounts_from_config():
    """Read existing accounts from src/config.py"""
    config_path = os.path.join(os.path.dirname(__file__), 'src', 'config.py')

    # Import config to get existing accounts
    try:
        from src.config import OANDAConfig
        return OANDAConfig.ACCOUNTS.copy()
    except Exception as e:
        print(f"Error reading config: {e}")
        return {}


def get_unique_api_keys(accounts: dict) -> dict:
    """Get unique API keys and their account names"""
    api_keys = {}
    for name, acc in accounts.items():
        key = acc['api_key']
        if key not in api_keys:
            api_keys[key] = {
                'example_account': name,
                'is_practice': acc.get('is_practice', True)
            }
    return api_keys


def find_new_accounts(api_accounts: list, existing_accounts: dict, api_key: str) -> list:
    """Find accounts from API that aren't in config"""
    existing_ids = {acc['account_id'] for acc in existing_accounts.values()}

    new_accounts = []
    for acc in api_accounts:
        if acc['id'] not in existing_ids:
            new_accounts.append({
                'account_id': acc['id'],
                'api_key': api_key,
                'tags': acc.get('tags', [])
            })
    return new_accounts


def generate_account_name(prefix: str, existing_accounts: dict, account_id: str) -> str:
    """Generate a unique account name"""
    # Extract numeric suffix from account_id (e.g., 101-001-35749385-005 -> 5)
    match = re.search(r'-(\d+)$', account_id)
    if match:
        suffix = int(match.group(1))
        name = f"{prefix}{suffix}"
        if name not in existing_accounts:
            return name

    # Fallback: find next available number
    i = 1
    while f"{prefix}{i}" in existing_accounts:
        i += 1
    return f"{prefix}{i}"


def update_config_file(new_accounts: list, prefix: str, is_practice: bool, dry_run: bool = False):
    """Add new accounts to src/config.py"""
    config_path = os.path.join(os.path.dirname(__file__), 'src', 'config.py')

    with open(config_path, 'r') as f:
        content = f.read()

    existing = get_existing_accounts_from_config()

    # Find the position to insert new accounts (before the closing }} of ACCOUNTS)
    # Look for the pattern that ends the ACCOUNTS dict
    pattern = r"(\s*}\s*}\s*\n\s*# Currently active account)"
    match = re.search(pattern, content)

    if not match:
        # Try alternative pattern
        pattern = r"(\s*'[^']+'\s*:\s*\{[^}]+\}\s*\n\s*}\s*})"
        match = re.search(pattern, content, re.DOTALL)
        if match:
            # Find the last account entry
            last_entry_end = match.end() - 2  # Before the }}
        else:
            print("Error: Could not find insertion point in config.py")
            return False
    else:
        last_entry_end = match.start()

    # Generate new account entries
    new_entries = []
    for acc in new_accounts:
        name = generate_account_name(prefix, existing, acc['account_id'])
        existing[name] = acc  # Track to avoid duplicates

        entry = f"""        '{name}': {{
            'api_key': '{acc['api_key']}',
            'account_id': '{acc['account_id']}',
            'is_practice': {is_practice}
        }},"""
        new_entries.append(entry)
        print(f"  + {name}: {acc['account_id']}")

    if not new_entries:
        print("No new accounts to add.")
        return True

    if dry_run:
        print("\n[DRY RUN] Would add the above accounts to src/config.py")
        return True

    # Insert new entries before the closing braces
    # Find the last account entry and add after it
    insert_text = "\n" + "\n".join(new_entries)

    # Find where to insert - before the final "    }\n    }" pattern
    final_pattern = r'(\n    \}\n    \})'
    match = re.search(final_pattern, content)
    if match:
        new_content = content[:match.start()] + insert_text + content[match.start():]
    else:
        # Fallback: find last account entry
        last_entry = re.findall(r"        '[^']+': \{[^}]+\},?\n", content)
        if last_entry:
            last_pos = content.rfind(last_entry[-1]) + len(last_entry[-1])
            new_content = content[:last_pos] + insert_text + "\n" + content[last_pos:]
        else:
            print("Error: Could not find insertion point")
            return False

    with open(config_path, 'w') as f:
        f.write(new_content)

    print(f"\nSuccessfully added {len(new_entries)} account(s) to src/config.py")
    return True


def main():
    args = sys.argv[1:]

    # Parse arguments
    api_key = None
    account_name = None
    prefix = 'sub'
    add_to_config = False
    dry_run = False
    list_all = False

    for arg in args:
        if arg.startswith('key='):
            api_key = arg.split('=', 1)[1]
        elif arg.startswith('at='):
            account_name = arg.split('=', 1)[1]
        elif arg.startswith('prefix='):
            prefix = arg.split('=', 1)[1]
        elif arg == 'add':
            add_to_config = True
        elif arg == 'dry-run':
            dry_run = True
        elif arg == 'all':
            list_all = True

    existing_accounts = get_existing_accounts_from_config()

    if not api_key and not account_name and not list_all:
        print(__doc__)
        print("\nExisting accounts in config:")
        for name in sorted(existing_accounts.keys()):
            print(f"  {name}: {existing_accounts[name]['account_id']}")
        return

    # Determine which API keys to query
    keys_to_query = {}

    if list_all:
        keys_to_query = get_unique_api_keys(existing_accounts)
        print(f"Found {len(keys_to_query)} unique API key(s) in config\n")
    elif account_name:
        if account_name not in existing_accounts:
            print(f"Error: Account '{account_name}' not found in config")
            print(f"Available accounts: {', '.join(existing_accounts.keys())}")
            return
        acc = existing_accounts[account_name]
        keys_to_query = {acc['api_key']: {
            'example_account': account_name,
            'is_practice': acc.get('is_practice', True)
        }}
    else:
        keys_to_query = {api_key: {
            'example_account': 'new',
            'is_practice': True
        }}

    # Query each API key
    all_new_accounts = []

    for key, info in keys_to_query.items():
        masked_key = key[:8] + '...' + key[-4:]
        print(f"Querying API key: {masked_key} (from {info['example_account']})")

        accounts = get_accounts_from_api(key, info['is_practice'])

        if not accounts:
            print("  No accounts found or error occurred\n")
            continue

        print(f"  Found {len(accounts)} account(s):")
        for acc in accounts:
            account_id = acc['id']
            tags = acc.get('tags', [])

            # Check if already in config
            in_config = any(
                existing_accounts[name]['account_id'] == account_id
                for name in existing_accounts
            )

            status = " (in config)" if in_config else " [NEW]"
            tag_str = f" tags={tags}" if tags else ""
            print(f"    {account_id}{tag_str}{status}")

        # Collect new accounts
        new_accs = find_new_accounts(accounts, existing_accounts, key)
        for acc in new_accs:
            acc['is_practice'] = info['is_practice']
        all_new_accounts.extend(new_accs)
        print()

    # Add new accounts if requested
    if add_to_config and all_new_accounts:
        print(f"\nAdding {len(all_new_accounts)} new account(s) with prefix '{prefix}':")
        update_config_file(all_new_accounts, prefix, True, dry_run)
    elif all_new_accounts and not add_to_config:
        print(f"\nFound {len(all_new_accounts)} new account(s). Use 'add' flag to add them to config.")
        print(f"Example: python3 {sys.argv[0]} at={account_name or 'account1'} prefix={prefix} add")


if __name__ == '__main__':
    main()
