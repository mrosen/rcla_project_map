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

