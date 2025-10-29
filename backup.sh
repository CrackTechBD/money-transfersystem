#!/bin/bash
"""
Simple Backup Script for MySQL Shards and Cassandra
Basic backup implementation without Python dependencies
"""

set -e

# Configuration
BACKUP_ROOT="${BACKUP_ROOT:-/tmp/backup}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

# Create backup directories
mkdir -p "$BACKUP_ROOT/mysql"
mkdir -p "$BACKUP_ROOT/cassandra" 
mkdir -p "$BACKUP_ROOT/logs"

echo "🔄 Starting backup at $(date)"

# Function to backup MySQL shard
backup_mysql_shard() {
    local shard_id=$1
    local host="mysql-shard-${shard_id}"
    local backup_file="$BACKUP_ROOT/mysql/shard_${shard_id}_${TIMESTAMP}.sql"
    
    echo "📁 Backing up MySQL shard $shard_id..."
    
    if docker exec "paytm-style-mysql-shard-${shard_id}-1" mysqldump \
        --user=root \
        --password=rootpassword \
        --single-transaction \
        --routines \
        --triggers \
        paytm_shard > "$backup_file" 2>/dev/null; then
        
        local file_size=$(du -h "$backup_file" | cut -f1)
        echo "✅ Shard $shard_id backup completed: $file_size"
        return 0
    else
        echo "❌ Shard $shard_id backup failed"
        rm -f "$backup_file"
        return 1
    fi
}

# Function to backup Cassandra
backup_cassandra() {
    local schema_file="$BACKUP_ROOT/cassandra/cassandra_schema_${TIMESTAMP}.cql"
    local data_file="$BACKUP_ROOT/cassandra/cassandra_data_${TIMESTAMP}.cql"
    
    echo "📁 Backing up Cassandra..."
    
    # Backup schema
    if docker exec paytm-style-cassandra-1 cqlsh -e "DESC KEYSPACE paytm_style;" > "$schema_file" 2>/dev/null; then
        echo "✅ Cassandra schema backup completed"
        
        # Backup data
        echo "USE paytm_style;" > "$data_file"
        
        # Export features table
        if docker exec paytm-style-cassandra-1 cqlsh -e "COPY paytm_style.features TO STDOUT WITH HEADER=TRUE;" >> "$data_file" 2>/dev/null; then
            echo "✅ Features table exported"
        fi
        
        # Export events table  
        if docker exec paytm-style-cassandra-1 cqlsh -e "COPY paytm_style.events TO STDOUT WITH HEADER=TRUE;" >> "$data_file" 2>/dev/null; then
            echo "✅ Events table exported"
        fi
        
        return 0
    else
        echo "❌ Cassandra backup failed"
        rm -f "$schema_file" "$data_file"
        return 1
    fi
}

# Function to cleanup old backups
cleanup_old_backups() {
    echo "🧹 Cleaning up backups older than $RETENTION_DAYS days..."
    
    local removed_count=0
    
    # Find and remove old files
    if command -v find >/dev/null 2>&1; then
        removed_count=$(find "$BACKUP_ROOT" -name "*.sql" -o -name "*.cql" -type f -mtime +$RETENTION_DAYS -exec rm {} \; -print | wc -l)
    fi
    
    echo "🗑️  Removed $removed_count old backup files"
}

# Main backup execution
main() {
    local mysql_success=0
    local cassandra_success=0
    
    echo "🚀 Starting full backup to $BACKUP_ROOT"
    
    # Backup all MySQL shards
    for shard_id in {0..3}; do
        if backup_mysql_shard $shard_id; then
            ((mysql_success++))
        fi
    done
    
    # Backup Cassandra
    if backup_cassandra; then
        cassandra_success=1
    fi
    
    # Cleanup old backups
    cleanup_old_backups
    
    # Generate summary
    local total_shards=4
    echo ""
    echo "📊 Backup Summary:"
    echo "   MySQL Shards: $mysql_success/$total_shards successful"
    echo "   Cassandra: $([ $cassandra_success -eq 1 ] && echo "✅ Success" || echo "❌ Failed")"
    echo "   Backup Location: $BACKUP_ROOT"
    echo "   Timestamp: $TIMESTAMP"
    
    # Write summary to log
    cat > "$BACKUP_ROOT/logs/backup_${TIMESTAMP}.log" << EOF
Backup completed at $(date)
MySQL Shards: $mysql_success/$total_shards successful
Cassandra: $([ $cassandra_success -eq 1 ] && echo "Success" || echo "Failed")
Total Duration: $(date)
EOF

    if [ $mysql_success -gt 0 ] && [ $cassandra_success -eq 1 ]; then
        echo "✅ Backup completed successfully"
        exit 0
    else
        echo "⚠️  Backup completed with some failures"
        exit 1
    fi
}

# Run backup
main "$@"