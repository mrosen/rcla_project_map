-- ==============================================================================
-- RCLA Project Map: Schema Migration for SPC Alignment & Enhanced Project Data
-- ==============================================================================
-- Run this script in the Supabase Cloud SQL Editor (Dashboard > SQL Editor)
-- Project: rqhmsincnmxrgtipvkif.supabase.co
-- ==============================================================================

-- 1. Add new columns to the 'projects' table
ALTER TABLE projects 
  ADD COLUMN IF NOT EXISTS brief_overview text,
  ADD COLUMN IF NOT EXISTS complete_overview text,
  ADD COLUMN IF NOT EXISTS start_date text,
  ADD COLUMN IF NOT EXISTS end_date text,
  ADD COLUMN IF NOT EXISTS timeline jsonb DEFAULT '{"backstory": "", "milestones": []}'::jsonb,
  ADD COLUMN IF NOT EXISTS details jsonb DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS sync_status jsonb DEFAULT '{}'::jsonb;

-- 2. Add comments describing field constraints and purposes
COMMENT ON COLUMN projects.brief_overview IS '100-character brief overview for Rotary Service Project Center (prjOverview)';
COMMENT ON COLUMN projects.complete_overview IS '1,000-character detailed project description for Rotary Service Project Center (prjDetailedDescription)';
COMMENT ON COLUMN projects.start_date IS 'ISO date (YYYY-MM-DD or YYYY-MM) marking when the club initiated/conceived the project';
COMMENT ON COLUMN projects.end_date IS 'ISO date (YYYY-MM-DD or YYYY-MM) marking when the project concluded';
COMMENT ON COLUMN projects.timeline IS 'JSON object containing backstory narrative and array of milestones [{id, name, date, notes}]';
COMMENT ON COLUMN projects.details IS 'JSON object containing budget breakdown, TRF match, DDF, club cash, partners, and personnel';
COMMENT ON COLUMN projects.sync_status IS 'JSON object tracking Grant Center file presence and SPC export synchronization state';

-- 3. Backfill brief_overview and complete_overview from existing description/narrative
-- (Truncated to fit within SPC hard constraints: 100 chars and 1,000 chars)
UPDATE projects
SET 
  brief_overview = CASE 
    WHEN brief_overview IS NOT NULL AND brief_overview != '' THEN brief_overview
    WHEN description IS NOT NULL AND description != '' THEN substring(trim(description) from 1 for 100)
    ELSE substring(trim(COALESCE(narrative, title, '')), 1, 100)
  END,
  complete_overview = CASE 
    WHEN complete_overview IS NOT NULL AND complete_overview != '' THEN complete_overview
    WHEN narrative IS NOT NULL AND narrative != '' THEN substring(trim(narrative) from 1 for 1000)
    ELSE substring(trim(COALESCE(description, title, '')), 1, 1000)
  END
WHERE brief_overview IS NULL OR complete_overview IS NULL;

-- 4. Initial backfill of start_date from start_year if start_date is empty
UPDATE projects
SET start_date = start_year::text || '-01-01'
WHERE start_date IS NULL AND start_year IS NOT NULL;

-- ==============================================================================
-- 5. Multi-Club Platform Schema (Clubs Registry & Project Ownership)
-- ==============================================================================

CREATE TABLE IF NOT EXISTS clubs (
  id text PRIMARY KEY,                      -- URL-friendly slug, e.g. 'lake-atitlan', 'annapolis'
  name text NOT NULL,                       -- Full display name, e.g. 'Rotary Club of Lake Atitlán'
  short_name text,                          -- Short name for matching, e.g. 'Lake Atitlán'
  rotary_club_id text,                      -- Rotary International Club ID, e.g. '84633'
  spc_club_key text,                        -- Rotary SPC Organization GUID, e.g. '7de94f72-4330-4015-9ba9-5fac50225049'
  district text,                            -- Rotary District number, e.g. '4250'
  country text DEFAULT 'Guatemala',
  default_city text DEFAULT 'Panajachel',
  default_state text DEFAULT 'Sololá Department',
  default_language text DEFAULT 'Spanish',
  default_lat numeric DEFAULT 14.703454,
  default_lng numeric DEFAULT -91.191623,
  default_zoom integer DEFAULT 11,
  created_at timestamptz DEFAULT now()
);

-- Enable Row Level Security with open read/write policies matching 'projects'
ALTER TABLE clubs ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE tablename = 'clubs' AND policyname = 'Allow public read access on clubs'
  ) THEN
    CREATE POLICY "Allow public read access on clubs" ON clubs FOR SELECT USING (true);
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE tablename = 'clubs' AND policyname = 'Allow anon insert/update on clubs'
  ) THEN
    CREATE POLICY "Allow anon insert/update on clubs" ON clubs FOR ALL USING (true) WITH Check (true);
  END IF;
END $$;

-- Seed initial clubs (Lake Atitlán + key partner clubs that can be selected immediately)
INSERT INTO clubs (id, name, short_name, rotary_club_id, spc_club_key, district, country, default_city, default_state, default_language, default_lat, default_lng, default_zoom)
VALUES
  ('lake-atitlan', 'Rotary Club of Lake Atitlán', 'Lake Atitlán', '84633', '7de94f72-4330-4015-9ba9-5fac50225049', '4250', 'Guatemala', 'Panajachel', 'Sololá Department', 'Spanish', 14.703454, -91.191623, 11),
  ('annapolis', 'Rotary Club of Annapolis', 'Annapolis', '5853', '6ef2a008-17d8-424b-b280-c59dfdaedce3', '7620', 'United States', 'Annapolis', 'MD', 'English', 38.9784, -76.4922, 11),
  ('northfield', 'Rotary Club of Northfield', 'Northfield', '2157', 'bc4485ed-daef-494e-b006-97c0b22a4ee7', '5960', 'United States', 'Northfield', 'MN', 'English', 44.4583, -93.1616, 11),
  ('fort-collins', 'Rotary Club of Fort Collins', 'Fort Collins', '1100', 'cb49c6f4-80fe-4221-bd35-c265bba54167', '5440', 'United States', 'Fort Collins', 'CO', 'English', 40.5853, -105.0844, 11)
ON CONFLICT (id) DO UPDATE SET
  name = EXCLUDED.name,
  short_name = EXCLUDED.short_name,
  rotary_club_id = COALESCE(clubs.rotary_club_id, EXCLUDED.rotary_club_id),
  spc_club_key = COALESCE(clubs.spc_club_key, EXCLUDED.spc_club_key),
  district = COALESCE(clubs.district, EXCLUDED.district);

-- Add club_id to projects and backfill existing RCLA projects
ALTER TABLE projects
  ADD COLUMN IF NOT EXISTS club_id text DEFAULT 'lake-atitlan';

UPDATE projects
SET club_id = 'lake-atitlan'
WHERE club_id IS NULL OR club_id = '';


