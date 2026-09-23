# Implementation Plan: Dynamic Extraction & Migration of Non-Financial Partner Organizations to Rotary SPC

Dynamically extract cooperating and implementing partner organizations directly from source data (Supabase `details.cooperating_organizations`, `details.implementing_partners`, `partner`, and markdown narrative) and export them to Rotary SPC as Implementing Partners, eliminating fragile per-project hardcoded profiles and preventing unwanted `$0 USD` funding lines.

## User Review Required

> [!IMPORTANT]
> - **Elimination of Fragile Profiles**: `DETAILED_PROJECT_PROFILES` will no longer be used as a hardcoded source for partner organizations. The migration engine will dynamically extract and categorize partner organizations across all projects from the database and grant narratives.
> - **Partner Type Classification on Rotary SPC**:
>   - **Partner Clubs**: Mapped to Rotary's live Organization directory and assigned `partnerCategoryId: "09b7b3de-56b4-4d12-95b1-eaa58b53f573"` (Funding partner).
>   - **Host Club (Lake Atitlán)**: Assigned `partnerCategoryId: "8881284b-572b-4247-8546-6f5a9ead9ae8"` (Funding & Implementing partner).
>   - **Non-Rotary Partners (NGOs, Government, Community Groups)**: Passed in `projectPartnerClubMembers` with `partnerCategoryId: "b8d43fa6-15a2-4398-b60e-ef07a3f09f16"` (Implementing Partner) and their appropriate `fundTypeId` (e.g. NonGovernmentalOrganization, GovernmentEntity, LocalCommunityGroup).
>   - **No $0 USD Rows**: Organizations that did not contribute money will not be placed in `projectFundings`, preventing unwanted `$0 USD` rows in the financial breakdown table.

---

## Proposed Changes

### Dynamic Partner Extractor & Payload Builder

#### [MODIFY] [scripts/migrate_to_spc.py](file://wsl.localhost/Ubuntu/home/msr/rcla_project_map/scripts/migrate_to_spc.py) & [migrate_to_spc.py](file://wsl.localhost/Ubuntu/home/msr/rcla_project_map/migrate_to_spc.py)

1. **Implement `extract_partner_organizations(project)`**:
   - Extract partner organizations from:
     - `details.cooperating_organizations` (handles strings, lists, and comma-separated lists)
     - `details.implementing_partners`
     - `project.partner` field
     - `project.narrative` under `### Partner Organizations` (NGOs & Local Organizations section)
   - Clean names, remove markdown formatting, and deduplicate.
   - Infer organization classification (`GovernmentEntity`, `LocalCommunityGroup`, `Foundation`, `NonGovernmentalOrganization`).
   - Map each to Rotary SPC's standard `fundTypeId` UUIDs:
     - NonGovernmentalOrganization: `123456be-cece-4096-ab1b-4a554f213f14`
     - GovernmentEntity: `123456be-cece-4096-ab1b-4a554f213f13`
     - LocalCommunityGroup: `123456be-cece-4096-ab1b-4a554f213f16`
     - Foundation: `123456be-cece-4096-ab1b-4a554f213f15`
     - Other: `123456be-cece-4096-ab1b-4a554f213f07`

2. **Update `construct_spc_payload`**:
   - Include extracted non-Rotary implementing partners in `payload["projectPartnerClubMembers"]` with `partnerCategoryId: "b8d43fa6-15a2-4398-b60e-ef07a3f09f16"` (Implementing Partner).
   - Only add financial contributors with `fundingAmount > 0` to `payload["projectFundings"]`.
   - Ensure `payload["description"]` includes the `Cooperating Partner(s): ...` callout so partners are prominently credited in the narrative.
   - Include partner names in project `tags`.

3. **Improve Browser In-Page Partner Reconciliation**:
   - In `UpdateProject` evaluation inside `main()`, match existing partners in `ProjectDetail` by either `partnerKey` or `organizationName` / `clubName` to preserve existing references without creating duplicates or dropping non-Rotary partners.

---

## Verification Plan

### Automated / Syntax Verification
- Run python compilation check on `scripts/migrate_to_spc.py` and `migrate_to_spc.py`.
- Run payload test for `GG2578692` and verify all partner organizations appear in `projectPartnerClubMembers` and that `projectFundings` contains zero $0 rows.

### Live Rotary SPC Verification
1. Run `python3 scripts/migrate_to_spc.py GG2578692 --headless`.
2. Fetch `https://spc.rotary.org/api/Project/ProjectDetail/en/0c101fff-43ee-41ea-97bc-22fd018d4cff`.
3. Verify:
   - `partners`: Contains all partner organizations (`AdP`, `Municipality of Santa Lucia Utatlan`, `Guatemala Federal Department of Education`, `Vista Hermosa Water & Sanitation Committee / COCODE`) as Implementing Partners.
   - `fundingSources`: Contains only the valid financial contributions (World Fund, District 7620 DDF, and contributing Rotary clubs). No $0 USD entries.
