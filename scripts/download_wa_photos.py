#!/usr/bin/env python3
"""
Download photos from Wild Apricot file storage via WebDAV.

Usage:
    # Download a single folder:
    python download_wa_photos.py --folder "Pictures/Fall 2025" --output ./downloaded_photos

    # Download ALL photos recursively:
    python download_wa_photos.py --folder "Pictures" --output ./all_photos --recursive

    # List what's available:
    python download_wa_photos.py --list --folder "Pictures"

Requirements:
    pip install webdavclient3
"""

import argparse
import os
import json
from pathlib import Path
from getpass import getpass
from datetime import datetime

try:
    from webdav3.client import Client
except ImportError:
    print("Please install webdavclient3: pip install webdavclient3")
    exit(1)


# Track statistics
stats = {
    'folders_scanned': 0,
    'files_found': 0,
    'files_downloaded': 0,
    'files_skipped': 0,
    'errors': 0,
    'total_size': 0
}


def download_wa_folder_recursive(client, remote_folder, local_folder, depth=0):
    """
    Recursively download all files from a folder and its subfolders.
    """
    global stats
    indent = "  " * depth

    # Ensure local folder exists
    local_path = Path(local_folder)
    local_path.mkdir(parents=True, exist_ok=True)

    try:
        items = client.list(remote_folder)
        stats['folders_scanned'] += 1
    except Exception as e:
        print(f"{indent}[ERROR] Cannot list {remote_folder}: {e}")
        stats['errors'] += 1
        return

    # Filter out the current directory marker
    items = [i for i in items if i and i != remote_folder.split('/')[-1] + '/']

    for item in items:
        # Build paths
        item_name = item.rstrip('/')
        remote_path = f"{remote_folder}/{item_name}".replace('//', '/')
        local_item_path = local_path / item_name

        if item.endswith('/'):
            # It's a directory - recurse
            print(f"{indent}📁 {item_name}/")
            download_wa_folder_recursive(client, remote_path, str(local_item_path), depth + 1)
        else:
            # It's a file
            stats['files_found'] += 1

            # Check if it's an image
            ext = Path(item_name).suffix.lower()
            if ext not in ['.jpg', '.jpeg', '.png', '.gif', '.heic', '.heif', '.webp', '.bmp']:
                continue  # Skip non-image files

            # Skip if already exists
            if local_item_path.exists():
                print(f"{indent}  ⏭️  {item_name} (exists)")
                stats['files_skipped'] += 1
                continue

            # Download
            print(f"{indent}  ⬇️  {item_name}...", end=' ', flush=True)
            try:
                client.download_sync(remote_path, str(local_item_path))
                size = local_item_path.stat().st_size if local_item_path.exists() else 0
                stats['files_downloaded'] += 1
                stats['total_size'] += size
                print(f"OK ({size // 1024} KB)")
            except Exception as e:
                print(f"ERROR: {e}")
                stats['errors'] += 1


def download_wa_folder(site_url, folder_path, output_dir, username, password, recursive=False):
    """
    Download all files from a Wild Apricot folder via WebDAV.
    """
    global stats

    # Configure WebDAV client
    options = {
        'webdav_hostname': f"https://{site_url}/resources",
        'webdav_login': username,
        'webdav_password': password,
    }

    client = Client(options)

    print(f"🔗 Connecting to {site_url}...")
    print(f"📂 Target folder: {folder_path}")
    print(f"💾 Output: {output_dir}")
    print(f"🔄 Recursive: {recursive}")
    print("-" * 50)

    try:
        # Check if folder exists
        if not client.check(folder_path):
            print(f"❌ Folder '{folder_path}' not found!")
            print("\nAvailable folders:")
            for item in client.list('/'):
                print(f"  - {item}")
            return

        if recursive:
            # Recursive download
            download_wa_folder_recursive(client, folder_path, output_dir)
        else:
            # Single folder download
            items = client.list(folder_path)
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)

            for item in items:
                if item.endswith('/'):
                    print(f"  📁 {item} (use --recursive to download)")
                    continue

                item_name = item.rstrip('/')
                ext = Path(item_name).suffix.lower()
                if ext not in ['.jpg', '.jpeg', '.png', '.gif', '.heic', '.heif', '.webp', '.bmp']:
                    continue

                stats['files_found'] += 1
                remote_path = f"{folder_path}/{item_name}"
                local_path = output_path / item_name

                if local_path.exists():
                    print(f"  ⏭️  {item_name} (exists)")
                    stats['files_skipped'] += 1
                    continue

                print(f"  ⬇️  {item_name}...", end=' ', flush=True)
                try:
                    client.download_sync(remote_path, str(local_path))
                    stats['files_downloaded'] += 1
                    print("OK")
                except Exception as e:
                    print(f"ERROR: {e}")
                    stats['errors'] += 1

        # Print summary
        print("-" * 50)
        print("📊 Summary:")
        print(f"   Folders scanned: {stats['folders_scanned']}")
        print(f"   Images found: {stats['files_found']}")
        print(f"   Downloaded: {stats['files_downloaded']}")
        print(f"   Skipped (existing): {stats['files_skipped']}")
        print(f"   Errors: {stats['errors']}")
        print(f"   Total size: {stats['total_size'] // (1024*1024)} MB")

        # Save manifest
        manifest_path = Path(output_dir) / '_download_manifest.json'
        manifest = {
            'source': f"https://{site_url}/resources/{folder_path}",
            'downloaded_at': datetime.now().isoformat(),
            'stats': stats
        }
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f, indent=2)
        print(f"\n📄 Manifest saved to: {manifest_path}")

    except Exception as e:
        print(f"❌ Error: {e}")
        print("\nTroubleshooting:")
        print("1. Verify you're using a full site administrator account")
        print("2. Check your site URL is correct")
        print("3. Try accessing via Finder first to verify credentials")


def list_wa_folders(site_url, username, password, path='/'):
    """List folders at a given path."""
    options = {
        'webdav_hostname': f"https://{site_url}/resources",
        'webdav_login': username,
        'webdav_password': password,
    }

    client = Client(options)

    print(f"Contents of '{path}':")
    try:
        for item in client.list(path):
            print(f"  {item}")
    except Exception as e:
        print(f"Error: {e}")


def main():
    parser = argparse.ArgumentParser(description='Download photos from Wild Apricot via WebDAV')
    parser.add_argument('--site', default='sbnc-website-redesign-playground.wildapricot.org',
                        help='WA site URL')
    parser.add_argument('--folder', default='Pictures',
                        help='Folder path within /resources (e.g., "Pictures/Fall 2025")')
    parser.add_argument('--output', default='./wa_photos',
                        help='Local directory to save files')
    parser.add_argument('--list', action='store_true',
                        help='Just list folder contents, don\'t download')
    parser.add_argument('--username', help='WA admin email (will prompt if not provided)')
    parser.add_argument('--password', help='WA admin password (will prompt if not provided)')

    args = parser.parse_args()

    # Get credentials
    username = args.username or input("WA Admin Email: ")
    password = args.password or getpass("WA Admin Password: ")

    if args.list:
        list_wa_folders(args.site, username, password, args.folder)
    else:
        download_wa_folder(args.site, args.folder, args.output, username, password)


if __name__ == '__main__':
    main()
