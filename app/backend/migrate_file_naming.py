#!/usr/bin/env python3
"""
Migration script: Fix #95 - Add hash prefix to processed files and .pdf extension to symlinks

Migrates legacy file naming to new format:
- Processed files: {filename} → {short_hash}_{filename}
- Symlinks: {document_id} → {document_id}.pdf

SAFE: Only migrates files that don't already have the new format.
Preserves legacy files for backward compatibility.

Usage:
    python migrate_file_naming.py [--dry-run] [--uploads-dir /path] [--processed-dir /path]
"""

import os
import sys
import argparse
import logging
from pathlib import Path
from typing import Dict, List, Tuple

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def is_sha256_hash(filename: str) -> bool:
    """Check if filename looks like a SHA256 hash (64 hex chars)."""
    name_without_ext = filename.replace('.pdf', '')
    return len(name_without_ext) == 64 and all(c in '0123456789abcdef' for c in name_without_ext)


def has_hash_prefix(filename: str) -> bool:
    """Check if filename already has hash prefix (8 hex chars + underscore)."""
    parts = filename.split('_', 1)
    if len(parts) < 2:
        return False
    prefix = parts[0]
    return len(prefix) == 8 and all(c in '0123456789abcdef' for c in prefix)


def migrate_symlinks(uploads_dir: str, dry_run: bool = False) -> Tuple[int, int]:
    """
    Migrate symlinks in uploads dir to add .pdf extension.
    
    Returns: (migrated_count, skipped_count)
    """
    logger.info(f"📂 Scanning symlinks in: {uploads_dir}")
    
    migrated = 0
    skipped = 0
    errors = 0
    
    for entry in os.listdir(uploads_dir):
        old_path = os.path.join(uploads_dir, entry)
        
        # Skip if not a symlink
        if not os.path.islink(old_path):
            continue
        
        # Skip if already has .pdf extension
        if entry.endswith('.pdf'):
            skipped += 1
            continue
        
        # Skip if not a SHA256 hash (e.g., timestamp-based names)
        if not is_sha256_hash(entry):
            logger.debug(f"⏭️  Skipping non-hash symlink: {entry}")
            skipped += 1
            continue
        
        # New path with .pdf extension
        new_path = f"{old_path}.pdf"
        
        # Get target of symlink
        target = os.readlink(old_path)
        
        # Check if new symlink already exists
        if os.path.exists(new_path):
            logger.warning(f"⚠️  Target already exists: {new_path}")
            skipped += 1
            continue
        
        logger.info(f"🔗 Migrating symlink: {entry} → {entry}.pdf")
        logger.debug(f"   Target: {target}")
        
        if not dry_run:
            try:
                # Create new symlink with .pdf extension
                os.symlink(target, new_path)
                
                # Remove old symlink
                os.unlink(old_path)
                
                migrated += 1
                logger.info(f"   ✅ Migrated")
            except Exception as e:
                logger.error(f"   ❌ Error: {e}")
                errors += 1
        else:
            logger.info(f"   [DRY RUN] Would migrate")
            migrated += 1
    
    return migrated, skipped, errors


def migrate_processed_files(processed_dir: str, dry_run: bool = False) -> Tuple[int, int]:
    """
    Migrate files in processed dir to add hash prefix.
    
    Returns: (migrated_count, skipped_count)
    """
    logger.info(f"📂 Scanning processed files in: {processed_dir}")
    
    migrated = 0
    skipped = 0
    errors = 0
    
    for entry in os.listdir(processed_dir):
        old_path = os.path.join(processed_dir, entry)
        
        # Skip if not a regular file
        if not os.path.isfile(old_path):
            continue
        
        # Skip if already has hash prefix
        if has_hash_prefix(entry):
            skipped += 1
            continue
        
        # Skip timestamp-based names (contain dots before extension)
        basename_without_ext = entry.replace('.pdf', '')
        if '.' in basename_without_ext:
            logger.debug(f"⏭️  Skipping timestamp-based file: {entry}")
            skipped += 1
            continue
        
        # Calculate short hash from file content
        try:
            import hashlib
            with open(old_path, 'rb') as f:
                file_hash = hashlib.sha256()
                for chunk in iter(lambda: f.read(8192), b""):
                    file_hash.update(chunk)
            short_hash = file_hash.hexdigest()[:8]
        except Exception as e:
            logger.error(f"❌ Error calculating hash for {entry}: {e}")
            errors += 1
            continue
        
        # New path with hash prefix
        new_filename = f"{short_hash}_{entry}"
        new_path = os.path.join(processed_dir, new_filename)
        
        # Check if new file already exists
        if os.path.exists(new_path):
            logger.warning(f"⚠️  Target already exists: {new_filename}")
            skipped += 1
            continue
        
        logger.info(f"📄 Migrating file: {entry} → {new_filename}")
        
        if not dry_run:
            try:
                # Rename file to add hash prefix
                os.rename(old_path, new_path)
                
                migrated += 1
                logger.info(f"   ✅ Migrated")
            except Exception as e:
                logger.error(f"   ❌ Error: {e}")
                errors += 1
        else:
            logger.info(f"   [DRY RUN] Would migrate")
            migrated += 1
    
    return migrated, skipped, errors


def update_symlink_targets(uploads_dir: str, processed_dir: str, dry_run: bool = False) -> int:
    """
    Update symlinks that point to old filenames (without hash prefix) to point to new filenames.
    
    Returns: updated_count
    """
    logger.info(f"🔗 Updating symlink targets...")
    
    updated = 0
    errors = 0
    
    # Build mapping of old → new filenames
    old_to_new: Dict[str, str] = {}
    for entry in os.listdir(processed_dir):
        if has_hash_prefix(entry):
            # Extract original filename
            parts = entry.split('_', 1)
            if len(parts) == 2:
                original_name = parts[1]
                old_to_new[original_name] = entry
    
    logger.info(f"📋 Found {len(old_to_new)} filename mappings")
    
    # Update symlinks
    for entry in os.listdir(uploads_dir):
        symlink_path = os.path.join(uploads_dir, entry)
        
        if not os.path.islink(symlink_path):
            continue
        
        try:
            target = os.readlink(symlink_path)
            target_basename = os.path.basename(target)
            
            # Check if target needs updating
            if target_basename in old_to_new:
                new_target_basename = old_to_new[target_basename]
                new_target = target.replace(target_basename, new_target_basename)
                
                logger.info(f"🔄 Updating symlink target: {entry}")
                logger.debug(f"   Old target: {target}")
                logger.debug(f"   New target: {new_target}")
                
                if not dry_run:
                    try:
                        # Remove old symlink
                        os.unlink(symlink_path)
                        
                        # Create new symlink with updated target
                        os.symlink(new_target, symlink_path)
                        
                        updated += 1
                        logger.info(f"   ✅ Updated")
                    except Exception as e:
                        logger.error(f"   ❌ Error: {e}")
                        errors += 1
                else:
                    logger.info(f"   [DRY RUN] Would update")
                    updated += 1
        except Exception as e:
            logger.error(f"❌ Error processing symlink {entry}: {e}")
            errors += 1
    
    return updated, errors


def main():
    parser = argparse.ArgumentParser(
        description="Migrate file naming to Fix #95 format (hash prefix + .pdf extension)"
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without actually doing it'
    )
    parser.add_argument(
        '--uploads-dir',
        default='/app/uploads',
        help='Path to uploads directory (default: /app/uploads)'
    )
    parser.add_argument(
        '--processed-dir',
        default='/app/inbox/processed',
        help='Path to processed directory (default: /app/inbox/processed)'
    )
    
    args = parser.parse_args()
    
    if args.dry_run:
        logger.info("🧪 DRY RUN MODE - No changes will be made")
    
    logger.info("=" * 70)
    logger.info("MIGRATION: Fix #95 - File naming with hash prefix + .pdf extension")
    logger.info("=" * 70)
    
    # Verify directories exist
    if not os.path.isdir(args.uploads_dir):
        logger.error(f"❌ Uploads directory not found: {args.uploads_dir}")
        sys.exit(1)
    
    if not os.path.isdir(args.processed_dir):
        logger.error(f"❌ Processed directory not found: {args.processed_dir}")
        sys.exit(1)
    
    # Step 1: Migrate processed files (add hash prefix)
    logger.info("\n" + "=" * 70)
    logger.info("STEP 1: Migrate processed files (add hash prefix)")
    logger.info("=" * 70)
    migrated_files, skipped_files, errors_files = migrate_processed_files(
        args.processed_dir,
        dry_run=args.dry_run
    )
    
    # Step 2: Update symlink targets to point to new filenames
    logger.info("\n" + "=" * 70)
    logger.info("STEP 2: Update symlink targets")
    logger.info("=" * 70)
    updated_targets, errors_targets = update_symlink_targets(
        args.uploads_dir,
        args.processed_dir,
        dry_run=args.dry_run
    )
    
    # Step 3: Migrate symlinks (add .pdf extension)
    logger.info("\n" + "=" * 70)
    logger.info("STEP 3: Migrate symlinks (add .pdf extension)")
    logger.info("=" * 70)
    migrated_links, skipped_links, errors_links = migrate_symlinks(
        args.uploads_dir,
        dry_run=args.dry_run
    )
    
    # Summary
    logger.info("\n" + "=" * 70)
    logger.info("MIGRATION SUMMARY")
    logger.info("=" * 70)
    logger.info(f"Processed files:")
    logger.info(f"  - Migrated: {migrated_files}")
    logger.info(f"  - Skipped: {skipped_files}")
    logger.info(f"  - Errors: {errors_files}")
    logger.info(f"\nSymlink targets:")
    logger.info(f"  - Updated: {updated_targets}")
    logger.info(f"  - Errors: {errors_targets}")
    logger.info(f"\nSymlinks:")
    logger.info(f"  - Migrated: {migrated_links}")
    logger.info(f"  - Skipped: {skipped_links}")
    logger.info(f"  - Errors: {errors_links}")
    
    total_errors = errors_files + errors_targets + errors_links
    if total_errors > 0:
        logger.warning(f"\n⚠️  Migration completed with {total_errors} errors")
        sys.exit(1)
    else:
        logger.info(f"\n✅ Migration completed successfully")
        if args.dry_run:
            logger.info("💡 Run without --dry-run to apply changes")


if __name__ == '__main__':
    main()
