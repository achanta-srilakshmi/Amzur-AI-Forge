# Utility Scripts

One-time maintenance scripts for Amzur AI Chat backend.

## backfill_generated_images.py

Backfill script to populate `storage_path` and `message_id` for older generated_images records.

### When to use

After deploying the disk-backed image storage feature, run this script once to migrate existing generated images that were stored as base64 in the database.

### Prerequisites

- Backend running environment set up (Python 3.11+, dependencies installed)
- `.env` file configured with `DATABASE_URL` and `UPLOAD_DIR`
- PostgreSQL database with existing generated_images records

### How to run

```bash
cd backend
python scripts/backfill_generated_images.py
```

### What it does

1. **Finds old records**: Queries for `generated_images` rows with `NULL storage_path`
2. **Saves images to disk**: 
   - Decodes base64 from `image_base64` column
   - Saves to: `{UPLOAD_DIR}/generated-images/{user_id}/{thread_id}/{image_id}.png`
   - Updates `storage_path` column with relative file path
   - Clears `image_base64` from DB to save space
3. **Links to messages**:
   - Finds the corresponding assistant message in the same thread
   - Sets `message_id` foreign key
4. **Commits progressively**: Each record is committed individually (safer if script is interrupted)

### Output

```
2026-05-08 12:00:00,123 [INFO] Starting backfill of generated_images...
2026-05-08 12:00:00,456 [INFO] Found 5 record(s) to backfill.
2026-05-08 12:00:00,789 [INFO] [1/5] Processing generated_image a1b2c3d4...
2026-05-08 12:00:01,012 [INFO]   ✓ Saved to disk: generated-images/user-1/thread-1/a1b2c3d4.png
2026-05-08 12:00:01,234 [INFO]   ✓ Linked to message m1n2o3p4
2026-05-08 12:00:01,456 [INFO]   ✓ Record updated and committed
...
2026-05-08 12:00:05,000 [INFO] ✓ Backfill complete. 5 record(s) processed.
```

### Error handling

- If an image fails to save to disk, that record is skipped (logged as error)
- If message linkage fails, the disk save is still kept and message linkage is skipped
- Each record is rolled back individually if commit fails
- Script can be safely re-run; it will skip records that already have `storage_path` set

### Verification

After running, verify the backfill:

```sql
-- Check how many records were migrated
SELECT COUNT(*) FROM generated_images WHERE storage_path IS NOT NULL;

-- Sample migrated records
SELECT id, storage_path, message_id, image_base64 
FROM generated_images 
WHERE storage_path IS NOT NULL 
LIMIT 5;
```

All successfully migrated records should have:
- ✅ Non-NULL `storage_path`
- ✅ NULL or valid `message_id`
- ✅ NULL `image_base64` (cleared to save DB space)
