-- Run once against an existing database that was created before image_url existed.
ALTER TABLE Territory ADD COLUMN IF NOT EXISTS image_url TEXT;
