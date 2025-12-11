#!/usr/bin/env python3
"""
Wild Apricot File Manager - Upload and download photos via WebDAV.

Usage:
    # Download photos:
    python wa_file_manager.py download --folder "Pictures/Fall 2025" --output ./local_photos

    # Upload photos:
    python wa_file_manager.py upload --source ./processed_photos --folder "Pictures/Gallery Export"

    # Upload single photo:
    python wa_file_manager.py upload --source ./photo.jpg --folder "Pictures/Events"

    # List folders:
    python wa_file_manager.py list --folder "Pictures"

    # Create folder:
    python wa_file_manager.py mkdir --folder "Pictures/New Event 2025"

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


# Supported image extensions
IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.gif', '.heic', '.heif', '.webp', '.bmp']


def get_webdav_client(site_url, username, password):
    """Create and return a WebDAV client."""
    options = {
        'webdav_hostname': f"https://{site_url}/resources",
        'webdav_login': username,
        'webdav_password': password,
    }
    return Client(options)


def upload_file(client, local_path, remote_folder, overwrite=False):
    """Upload a single file to WA."""
    local_path = Path(local_path)
    if not local_path.exists():
        print(f"  [ERROR] File not found: {local_path}")
        return False

    filename = local_path.name
    remote_path = f"{remote_folder}/{filename}".replace('//', '/')

    # Check if file exists on remote
    try:
        if client.check(remote_path) and not overwrite:
            print(f"  [SKIP] {filename} (already exists, use --overwrite)")
            return False
    except:
        pass  # File doesn't exist, OK to upload

    print(f"  [UPLOAD] {filename}...", end=' ', flush=True)
    try:
        client.upload_sync(str(local_path), remote_path)
        size = local_path.stat().st_size
        print(f"OK ({size // 1024} KB)")
        return True
    except Exception as e:
        print(f"ERROR: {e}")
        return False


def upload_folder(client, local_folder, remote_folder, recursive=False, overwrite=False):
    """Upload all images from a local folder to WA."""
    local_path = Path(local_folder)
    if not local_path.exists():
        print(f"[ERROR] Folder not found: {local_folder}")
        return {'uploaded': 0, 'skipped': 0, 'errors': 0}

    stats = {'uploaded': 0, 'skipped': 0, 'errors': 0, 'total_size': 0}

    # Ensure remote folder exists
    try:
        if not client.check(remote_folder):
            print(f"[CREATE] Remote folder: {remote_folder}")
            client.mkdir(remote_folder)
    except:
        try:
            client.mkdir(remote_folder)
        except:
            pass

    # Get files to upload
    if recursive:
        files = list(local_path.rglob('*'))
    else:
        files = list(local_path.iterdir())

    # Filter to images only
    image_files = [f for f in files if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS]

    print(f"Found {len(image_files)} images to upload")
    print("-" * 50)

    for local_file in image_files:
        # Calculate remote path preserving subfolder structure if recursive
        if recursive:
            rel_path = local_file.relative_to(local_path)
            if len(rel_path.parts) > 1:
                # Has subfolder - create it
                subfolder = f"{remote_folder}/{'/'.join(rel_path.parts[:-1])}"
                try:
                    if not client.check(subfolder):
                        client.mkdir(subfolder)
                except:
                    try:
                        client.mkdir(subfolder)
                    except:
                        pass
                target_folder = subfolder
            else:
                target_folder = remote_folder
        else:
            target_folder = remote_folder

        if upload_file(client, local_file, target_folder, overwrite):
            stats['uploaded'] += 1
            stats['total_size'] += local_file.stat().st_size
        else:
            if client.check(f"{target_folder}/{local_file.name}"):
                stats['skipped'] += 1
            else:
                stats['errors'] += 1

    return stats


def download_folder_recursive(client, remote_folder, local_folder, stats, depth=0):
    """Recursively download all files from a folder and its subfolders."""
    indent = "  " * depth

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
        item_name = item.rstrip('/')
        remote_path = f"{remote_folder}/{item_name}".replace('//', '/')
        local_item_path = local_path / item_name

        if item.endswith('/'):
            print(f"{indent}[FOLDER] {item_name}/")
            download_folder_recursive(client, remote_path, str(local_item_path), stats, depth + 1)
        else:
            ext = Path(item_name).suffix.lower()
            if ext not in IMAGE_EXTENSIONS:
                continue

            stats['files_found'] += 1

            if local_item_path.exists():
                print(f"{indent}  [SKIP] {item_name} (exists)")
                stats['files_skipped'] += 1
                continue

            print(f"{indent}  [DOWNLOAD] {item_name}...", end=' ', flush=True)
            try:
                client.download_sync(remote_path, str(local_item_path))
                size = local_item_path.stat().st_size if local_item_path.exists() else 0
                stats['files_downloaded'] += 1
                stats['total_size'] += size
                print(f"OK ({size // 1024} KB)")
            except Exception as e:
                print(f"ERROR: {e}")
                stats['errors'] += 1


def cmd_upload(args, client):
    """Handle upload command."""
    source = Path(args.source)

    print(f"[UPLOAD] Source: {args.source}")
    print(f"[UPLOAD] Target: {args.folder}")
    print("-" * 50)

    if source.is_file():
        # Single file upload
        if upload_file(client, source, args.folder, args.overwrite):
            print("\n[SUCCESS] File uploaded")
        else:
            print("\n[FAILED] Upload failed")
    else:
        # Folder upload
        stats = upload_folder(client, args.source, args.folder, args.recursive, args.overwrite)

        print("-" * 50)
        print("[SUMMARY]")
        print(f"  Uploaded: {stats['uploaded']}")
        print(f"  Skipped: {stats['skipped']}")
        print(f"  Errors: {stats['errors']}")
        print(f"  Total size: {stats['total_size'] // (1024*1024)} MB")


def cmd_download(args, client):
    """Handle download command."""
    stats = {
        'folders_scanned': 0,
        'files_found': 0,
        'files_downloaded': 0,
        'files_skipped': 0,
        'errors': 0,
        'total_size': 0
    }

    print(f"[DOWNLOAD] Source: {args.folder}")
    print(f"[DOWNLOAD] Target: {args.output}")
    print(f"[DOWNLOAD] Recursive: {args.recursive}")
    print("-" * 50)

    try:
        if not client.check(args.folder):
            print(f"[ERROR] Folder '{args.folder}' not found!")
            print("\nAvailable folders:")
            for item in client.list('/'):
                print(f"  - {item}")
            return
    except Exception as e:
        print(f"[ERROR] Cannot access folder: {e}")
        return

    if args.recursive:
        download_folder_recursive(client, args.folder, args.output, stats)
    else:
        local_path = Path(args.output)
        local_path.mkdir(parents=True, exist_ok=True)

        items = client.list(args.folder)
        for item in items:
            if item.endswith('/'):
                print(f"  [FOLDER] {item} (use --recursive)")
                continue

            item_name = item.rstrip('/')
            ext = Path(item_name).suffix.lower()
            if ext not in IMAGE_EXTENSIONS:
                continue

            stats['files_found'] += 1
            remote_path = f"{args.folder}/{item_name}"
            local_file = local_path / item_name

            if local_file.exists():
                print(f"  [SKIP] {item_name} (exists)")
                stats['files_skipped'] += 1
                continue

            print(f"  [DOWNLOAD] {item_name}...", end=' ', flush=True)
            try:
                client.download_sync(remote_path, str(local_file))
                stats['files_downloaded'] += 1
                print("OK")
            except Exception as e:
                print(f"ERROR: {e}")
                stats['errors'] += 1

    print("-" * 50)
    print("[SUMMARY]")
    print(f"  Folders scanned: {stats['folders_scanned']}")
    print(f"  Images found: {stats['files_found']}")
    print(f"  Downloaded: {stats['files_downloaded']}")
    print(f"  Skipped: {stats['files_skipped']}")
    print(f"  Errors: {stats['errors']}")
    print(f"  Total size: {stats['total_size'] // (1024*1024)} MB")

    # Save manifest
    manifest_path = Path(args.output) / '_download_manifest.json'
    manifest = {
        'source': f"https://{args.site}/resources/{args.folder}",
        'downloaded_at': datetime.now().isoformat(),
        'stats': stats
    }
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)
    print(f"\n[MANIFEST] Saved to: {manifest_path}")


def cmd_list(args, client):
    """Handle list command."""
    print(f"Contents of '{args.folder}':")
    print("-" * 50)
    try:
        items = client.list(args.folder)
        folders = []
        files = []

        for item in items:
            if item.endswith('/'):
                folders.append(item.rstrip('/'))
            else:
                files.append(item)

        for folder in sorted(folders):
            print(f"  [DIR]  {folder}/")
        for file in sorted(files):
            ext = Path(file).suffix.lower()
            icon = "[IMG]" if ext in IMAGE_EXTENSIONS else "[FILE]"
            print(f"  {icon} {file}")

        print("-" * 50)
        print(f"Total: {len(folders)} folders, {len(files)} files")
    except Exception as e:
        print(f"[ERROR] {e}")


def cmd_mkdir(args, client):
    """Handle mkdir command."""
    print(f"Creating folder: {args.folder}")
    try:
        client.mkdir(args.folder)
        print("[SUCCESS] Folder created")
    except Exception as e:
        print(f"[ERROR] {e}")


def main():
    parser = argparse.ArgumentParser(
        description='Wild Apricot File Manager - Upload/download photos via WebDAV',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s download --folder "Pictures/Fall 2025" --output ./photos
  %(prog)s upload --source ./processed --folder "Pictures/Gallery"
  %(prog)s list --folder "Pictures"
  %(prog)s mkdir --folder "Pictures/New Event"
"""
    )

    parser.add_argument('--site', default='sbnc-website-redesign-playground.wildapricot.org',
                        help='WA site URL')
    parser.add_argument('--username', help='WA admin email')
    parser.add_argument('--password', help='WA admin password')

    subparsers = parser.add_subparsers(dest='command', help='Command to run')

    # Download command
    dl_parser = subparsers.add_parser('download', help='Download photos from WA')
    dl_parser.add_argument('--folder', required=True, help='Remote folder path')
    dl_parser.add_argument('--output', required=True, help='Local output directory')
    dl_parser.add_argument('--recursive', '-r', action='store_true', help='Download recursively')

    # Upload command
    ul_parser = subparsers.add_parser('upload', help='Upload photos to WA')
    ul_parser.add_argument('--source', required=True, help='Local file or folder to upload')
    ul_parser.add_argument('--folder', required=True, help='Remote folder path')
    ul_parser.add_argument('--recursive', '-r', action='store_true', help='Upload subfolders too')
    ul_parser.add_argument('--overwrite', action='store_true', help='Overwrite existing files')

    # List command
    ls_parser = subparsers.add_parser('list', help='List folder contents')
    ls_parser.add_argument('--folder', default='/', help='Folder to list')

    # Mkdir command
    mk_parser = subparsers.add_parser('mkdir', help='Create a folder')
    mk_parser.add_argument('--folder', required=True, help='Folder path to create')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Get credentials
    username = args.username or os.environ.get('WA_USERNAME') or input("WA Admin Email: ")
    password = args.password or os.environ.get('WA_PASSWORD') or getpass("WA Admin Password: ")

    # Create client
    print(f"[CONNECT] {args.site}")
    client = get_webdav_client(args.site, username, password)

    # Run command
    if args.command == 'download':
        cmd_download(args, client)
    elif args.command == 'upload':
        cmd_upload(args, client)
    elif args.command == 'list':
        cmd_list(args, client)
    elif args.command == 'mkdir':
        cmd_mkdir(args, client)


if __name__ == '__main__':
    main()
