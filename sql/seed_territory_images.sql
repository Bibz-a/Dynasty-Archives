-- Optional: set default image paths for bundled files in images/territories/
-- Run after migrate_territory_image_url.sql. Adjust names if yours differ.

UPDATE Territory SET image_url = '/images/territories/anatolia.jpg' WHERE name ILIKE '%Anatolia%' AND image_url IS NULL;
UPDATE Territory SET image_url = '/images/territories/balkans.jpg' WHERE name ILIKE '%Balkan%' AND image_url IS NULL;
UPDATE Territory SET image_url = '/images/territories/central_asia.jpg' WHERE (name ILIKE '%Central Asia%' OR name ILIKE '%Central Asian%') AND image_url IS NULL;
UPDATE Territory SET image_url = '/images/territories/constantinople.png' WHERE name ILIKE '%Constantinople%' AND image_url IS NULL;
UPDATE Territory SET image_url = '/images/territories/egypt.jpg' WHERE name ILIKE '%Egypt%' AND image_url IS NULL;
UPDATE Territory SET image_url = '/images/territories/gaul.jpg' WHERE name ILIKE '%Gaul%' AND image_url IS NULL;
UPDATE Territory SET image_url = '/images/territories/mesopotamia.jpg' WHERE name ILIKE '%Mesopotamia%' AND image_url IS NULL;
UPDATE Territory SET image_url = '/images/territories/north_africa.jpg' WHERE (name ILIKE '%North Africa%' OR name ILIKE '%North African%') AND image_url IS NULL;
UPDATE Territory SET image_url = '/images/territories/persia.jpg' WHERE name ILIKE '%Persia%' AND image_url IS NULL;
UPDATE Territory SET image_url = '/images/territories/syria_palestine.jpg' WHERE (name ILIKE '%Syria%' OR name ILIKE '%Palestine%' OR name ILIKE '%Levant%' OR name ILIKE '%Sham%') AND image_url IS NULL;
