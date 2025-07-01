#!/usr/bin/env python3
"""
Backup and restore email settings for WireGuard Gateway.
This script is used by install.sh to preserve email settings across reinstalls.
"""

import os
import sys
import json
import sqlite3
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def backup_email_settings(db_path, backup_path):
    """
    Backup email settings from the database to a JSON file.
    
    Args:
        db_path: Path to the SQLite database file
        backup_path: Path where the backup JSON will be saved
    
    Returns:
        True if backup successful, False otherwise
    """
    try:
        # Check if database exists
        if not os.path.exists(db_path):
            logger.warning(f"Database not found at {db_path}")
            return False
        
        # Connect to database
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Check if email_settings table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='email_settings'
        """)
        
        if not cursor.fetchone():
            logger.info("email_settings table not found - nothing to backup")
            conn.close()
            return False
        
        # Get email settings
        cursor.execute("SELECT * FROM email_settings ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        
        if not row:
            logger.info("No email settings found to backup")
            conn.close()
            return False
        
        # Convert row to dictionary
        settings = dict(row)
        
        # Add backup metadata
        backup_data = {
            'backup_version': '1.0',
            'backup_timestamp': datetime.utcnow().isoformat(),
            'email_settings': settings
        }
        
        # Save to JSON file
        os.makedirs(os.path.dirname(backup_path), exist_ok=True)
        with open(backup_path, 'w') as f:
            json.dump(backup_data, f, indent=2)
        
        logger.info(f"Email settings backed up successfully to {backup_path}")
        logger.info(f"Backed up settings for SMTP host: {settings.get('smtp_host')}")
        
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"Error backing up email settings: {e}")
        return False

def restore_email_settings(db_path, backup_path):
    """
    Restore email settings from a JSON backup file to the database.
    
    Args:
        db_path: Path to the SQLite database file
        backup_path: Path to the backup JSON file
    
    Returns:
        True if restore successful, False otherwise
    """
    try:
        # Check if backup exists
        if not os.path.exists(backup_path):
            logger.info(f"No backup found at {backup_path}")
            return False
        
        # Load backup data
        with open(backup_path, 'r') as f:
            backup_data = json.load(f)
        
        # Validate backup version
        if backup_data.get('backup_version') != '1.0':
            logger.error(f"Unsupported backup version: {backup_data.get('backup_version')}")
            return False
        
        settings = backup_data.get('email_settings', {})
        if not settings:
            logger.warning("No email settings in backup file")
            return False
        
        # Connect to database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if email_settings table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='email_settings'
        """)
        
        if not cursor.fetchone():
            logger.error("email_settings table not found in database")
            conn.close()
            return False
        
        # Delete existing settings (should be none after fresh install)
        cursor.execute("DELETE FROM email_settings")
        
        # Prepare insert query
        columns = []
        values = []
        placeholders = []
        
        # Skip id, created_at, and updated_at - let database handle these
        skip_fields = ['id', 'created_at', 'updated_at']
        
        for key, value in settings.items():
            if key not in skip_fields:
                columns.append(key)
                values.append(value)
                placeholders.append('?')
        
        # Insert restored settings
        if columns:
            query = f"INSERT INTO email_settings ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"
            cursor.execute(query, values)
            conn.commit()
            
            logger.info(f"Email settings restored successfully from {backup_path}")
            logger.info(f"Restored settings for SMTP host: {settings.get('smtp_host')}")
            logger.info(f"Alert recipients: {settings.get('alert_recipients')}")
        else:
            logger.warning("No valid settings to restore")
            conn.close()
            return False
        
        conn.close()
        
        # Clean up backup file after successful restore
        try:
            os.remove(backup_path)
            logger.info("Backup file removed after successful restore")
        except Exception as e:
            logger.warning(f"Could not remove backup file: {e}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error restoring email settings: {e}")
        return False

def main():
    """Main function to handle command line arguments."""
    if len(sys.argv) < 4:
        print("Usage: backup-restore-email.py <backup|restore> <db_path> <backup_path>")
        sys.exit(1)
    
    action = sys.argv[1]
    db_path = sys.argv[2]
    backup_path = sys.argv[3]
    
    if action == 'backup':
        success = backup_email_settings(db_path, backup_path)
        sys.exit(0 if success else 1)
    elif action == 'restore':
        success = restore_email_settings(db_path, backup_path)
        sys.exit(0 if success else 1)
    else:
        print(f"Unknown action: {action}")
        print("Use 'backup' or 'restore'")
        sys.exit(1)

if __name__ == '__main__':
    main()