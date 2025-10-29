#!/usr/bin/env python3
"""
Data Backup Strategy for MySQL Shards and Cassandra
Automated backup with restore procedures
"""

import os
import subprocess
import json
import time
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import schedule
from pathlib import Path

logger = logging.getLogger(__name__)

class BackupConfig:
    """Configuration for backup operations"""
    def __init__(self):
        self.backup_root = os.getenv("BACKUP_ROOT", "/backup")
        self.retention_days = int(os.getenv("BACKUP_RETENTION_DAYS", "30"))
        self.mysql_host_prefix = "mysql-shard-"
        self.mysql_port = 3306
        self.mysql_user = "root"
        self.mysql_password = "rootpassword"
        self.mysql_database = "paytm_shard"
        self.cassandra_host = "cassandra"
        self.cassandra_port = 9042
        self.cassandra_keyspace = "paytm_style"
        
class BackupManager:
    """Manages backup operations for all data stores"""
    
    def __init__(self, config: BackupConfig):
        self.config = config
        self.ensure_backup_directories()
    
    def ensure_backup_directories(self):
        """Create backup directories if they don't exist"""
        backup_path = Path(self.config.backup_root)
        backup_path.mkdir(parents=True, exist_ok=True)
        
        for subdir in ["mysql", "cassandra", "logs"]:
            (backup_path / subdir).mkdir(exist_ok=True)
    
    def backup_mysql_shard(self, shard_id: int) -> Dict:
        """Backup a single MySQL shard"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"shard_{shard_id}_{timestamp}.sql"
        backup_path = Path(self.config.backup_root) / "mysql" / backup_filename
        
        host = f"{self.config.mysql_host_prefix}{shard_id}"
        
        # Construct mysqldump command
        cmd = [
            "mysqldump",
            f"--host={host}",
            f"--port={self.config.mysql_port}",
            f"--user={self.config.mysql_user}",
            f"--password={self.config.mysql_password}",
            "--single-transaction",
            "--routines",
            "--triggers",
            "--add-drop-database",
            "--create-options",
            self.config.mysql_database
        ]
        
        try:
            logger.info(f"Starting MySQL backup for shard {shard_id}")
            start_time = time.time()
            
            with open(backup_path, 'w') as backup_file:
                result = subprocess.run(
                    cmd,
                    stdout=backup_file,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=3600  # 1 hour timeout
                )
            
            if result.returncode == 0:
                duration = time.time() - start_time
                file_size = backup_path.stat().st_size
                
                logger.info(f"MySQL shard {shard_id} backup completed successfully")
                
                return {
                    "success": True,
                    "shard_id": shard_id,
                    "backup_file": str(backup_path),
                    "duration_seconds": round(duration, 2),
                    "file_size_bytes": file_size,
                    "timestamp": timestamp
                }
            else:
                logger.error(f"MySQL backup failed for shard {shard_id}: {result.stderr}")
                # Clean up failed backup file
                if backup_path.exists():
                    backup_path.unlink()
                
                return {
                    "success": False,
                    "shard_id": shard_id,
                    "error": result.stderr,
                    "timestamp": timestamp
                }
                
        except subprocess.TimeoutExpired:
            logger.error(f"MySQL backup timeout for shard {shard_id}")
            return {
                "success": False,
                "shard_id": shard_id,
                "error": "Backup timeout after 1 hour",
                "timestamp": timestamp
            }
        except Exception as e:
            logger.error(f"MySQL backup error for shard {shard_id}: {str(e)}")
            return {
                "success": False,
                "shard_id": shard_id,
                "error": str(e),
                "timestamp": timestamp
            }
    
    def backup_all_mysql_shards(self, num_shards: int = 4) -> Dict:
        """Backup all MySQL shards"""
        logger.info(f"Starting backup of {num_shards} MySQL shards")
        results = []
        
        for shard_id in range(num_shards):
            result = self.backup_mysql_shard(shard_id)
            results.append(result)
        
        successful_backups = [r for r in results if r["success"]]
        failed_backups = [r for r in results if not r["success"]]
        
        summary = {
            "total_shards": num_shards,
            "successful_backups": len(successful_backups),
            "failed_backups": len(failed_backups),
            "results": results,
            "timestamp": datetime.now().isoformat()
        }
        
        logger.info(f"MySQL backup summary: {len(successful_backups)}/{num_shards} successful")
        return summary
    
    def backup_cassandra(self) -> Dict:
        """Backup Cassandra keyspace"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"cassandra_{timestamp}.cql"
        backup_path = Path(self.config.backup_root) / "cassandra" / backup_filename
        
        # Use cqlsh to dump the keyspace
        cmd = [
            "docker", "exec", "paytm-style-cassandra-1",
            "cqlsh", "-e", f"DESC KEYSPACE {self.config.cassandra_keyspace};"
        ]
        
        try:
            logger.info("Starting Cassandra backup")
            start_time = time.time()
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=1800  # 30 minutes timeout
            )
            
            if result.returncode == 0:
                # Write schema to file
                with open(backup_path, 'w') as backup_file:
                    backup_file.write(result.stdout)
                
                # Also backup data using COPY commands
                data_backup_path = backup_path.with_suffix('.data.cql')
                self._backup_cassandra_data(data_backup_path)
                
                duration = time.time() - start_time
                file_size = backup_path.stat().st_size
                
                logger.info("Cassandra backup completed successfully")
                
                return {
                    "success": True,
                    "schema_backup_file": str(backup_path),
                    "data_backup_file": str(data_backup_path),
                    "duration_seconds": round(duration, 2),
                    "file_size_bytes": file_size,
                    "timestamp": timestamp
                }
            else:
                logger.error(f"Cassandra backup failed: {result.stderr}")
                return {
                    "success": False,
                    "error": result.stderr,
                    "timestamp": timestamp
                }
                
        except Exception as e:
            logger.error(f"Cassandra backup error: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": timestamp
            }
    
    def _backup_cassandra_data(self, backup_path: Path):
        """Backup Cassandra data using COPY commands"""
        tables = ["features", "events"]  # Known tables from schema
        
        with open(backup_path, 'w') as backup_file:
            backup_file.write(f"USE {self.config.cassandra_keyspace};\\n")
            
            for table in tables:
                copy_cmd = [
                    "docker", "exec", "paytm-style-cassandra-1",
                    "cqlsh", "-e", 
                    f"COPY {self.config.cassandra_keyspace}.{table} TO '/tmp/{table}.csv' WITH HEADER=TRUE;"
                ]
                
                try:
                    subprocess.run(copy_cmd, check=True, capture_output=True)
                    backup_file.write(f"-- Data backup for table {table}\\n")
                    backup_file.write(f"COPY {table} FROM '/tmp/{table}.csv' WITH HEADER=TRUE;\\n")
                except subprocess.CalledProcessError as e:
                    logger.warning(f"Failed to backup table {table}: {e}")
    
    def cleanup_old_backups(self):
        """Remove backup files older than retention period"""
        cutoff_date = datetime.now() - timedelta(days=self.config.retention_days)
        
        backup_dirs = [
            Path(self.config.backup_root) / "mysql",
            Path(self.config.backup_root) / "cassandra"
        ]
        
        total_removed = 0
        total_size_freed = 0
        
        for backup_dir in backup_dirs:
            if not backup_dir.exists():
                continue
                
            for backup_file in backup_dir.iterdir():
                if backup_file.is_file():
                    # Check file modification time
                    file_time = datetime.fromtimestamp(backup_file.stat().st_mtime)
                    if file_time < cutoff_date:
                        file_size = backup_file.stat().st_size
                        backup_file.unlink()
                        total_removed += 1
                        total_size_freed += file_size
                        logger.info(f"Removed old backup: {backup_file}")
        
        logger.info(f"Cleanup completed: {total_removed} files removed, {total_size_freed / (1024*1024):.2f} MB freed")
        
        return {
            "files_removed": total_removed,
            "bytes_freed": total_size_freed,
            "cutoff_date": cutoff_date.isoformat()
        }
    
    def full_backup(self) -> Dict:
        """Perform full system backup"""
        logger.info("Starting full system backup")
        start_time = time.time()
        
        # Backup MySQL shards
        mysql_result = self.backup_all_mysql_shards()
        
        # Backup Cassandra
        cassandra_result = self.backup_cassandra()
        
        # Cleanup old backups
        cleanup_result = self.cleanup_old_backups()
        
        duration = time.time() - start_time
        
        result = {
            "backup_type": "full",
            "start_time": datetime.fromtimestamp(start_time).isoformat(),
            "duration_seconds": round(duration, 2),
            "mysql": mysql_result,
            "cassandra": cassandra_result,
            "cleanup": cleanup_result,
            "overall_success": mysql_result.get("successful_backups", 0) > 0 and cassandra_result.get("success", False)
        }
        
        # Write backup report
        report_path = Path(self.config.backup_root) / "logs" / f"backup_report_{int(start_time)}.json"
        with open(report_path, 'w') as report_file:
            json.dump(result, report_file, indent=2)
        
        logger.info(f"Full backup completed in {duration:.2f} seconds")
        return result

def restore_mysql_shard(backup_file: str, shard_id: int, config: BackupConfig) -> bool:
    """Restore a MySQL shard from backup"""
    host = f"{config.mysql_host_prefix}{shard_id}"
    
    cmd = [
        "mysql",
        f"--host={host}",
        f"--port={config.mysql_port}",
        f"--user={config.mysql_user}",
        f"--password={config.mysql_password}",
    ]
    
    try:
        with open(backup_file, 'r') as backup:
            result = subprocess.run(
                cmd,
                stdin=backup,
                capture_output=True,
                text=True
            )
        
        if result.returncode == 0:
            logger.info(f"Successfully restored MySQL shard {shard_id} from {backup_file}")
            return True
        else:
            logger.error(f"Failed to restore MySQL shard {shard_id}: {result.stderr}")
            return False
            
    except Exception as e:
        logger.error(f"Error restoring MySQL shard {shard_id}: {str(e)}")
        return False

def schedule_backups(backup_manager: BackupManager):
    """Schedule automated backups"""
    # Daily full backup at 2 AM
    schedule.every().day.at("02:00").do(backup_manager.full_backup)
    
    # Weekly cleanup on Sundays at 3 AM
    schedule.every().sunday.at("03:00").do(backup_manager.cleanup_old_backups)
    
    logger.info("Backup schedule configured: Daily at 2:00 AM, Cleanup on Sundays at 3:00 AM")

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Initialize backup manager
    config = BackupConfig()
    backup_manager = BackupManager(config)
    
    # Schedule automated backups
    schedule_backups(backup_manager)
    
    # Run immediate backup if requested
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--backup-now":
        backup_manager.full_backup()
    else:
        # Run scheduler
        logger.info("Backup scheduler started. Press Ctrl+C to stop.")
        try:
            while True:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
        except KeyboardInterrupt:
            logger.info("Backup scheduler stopped.")