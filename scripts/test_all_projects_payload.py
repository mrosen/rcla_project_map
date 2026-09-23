import sys, json, re
sys.path.insert(0, '/home/msr/rcla_project_map/scripts')
from migrate_to_spc import build_project_list

# Import current construct_spc_payload and test extraction
projects = build_project_list()
print(f"Total projects to inspect: {len(projects)}")

zero_count = 0
partner_count = 0

for p in projects:
    pid = p.get('id')
    # Count how many partners extracted
    from migrate_to_spc import extract_partner_organizations, construct_spc_payload
    orgs = extract_partner_organizations(p)
    payload = construct_spc_payload(p)
    fundings = payload.get('projectFundings', [])
    zero_rows = [f for f in fundings if str(f.get('fundingAmount')).strip() in ('0', '', 'None') or float(re.sub(r'[^0-9.]', '', str(f.get('fundingAmount', 0))) or 0) == 0]
    
    if orgs:
        partner_count += 1
        print(f"[{pid}] {len(orgs)} partner orgs: {[o['name'] for o in orgs]}")
    if zero_rows:
        zero_count += len(zero_rows)
        print(f"  🚨 [{pid}] Has {len(zero_rows)} ZERO ROWS: {zero_rows}")

print(f"\nSummary: {partner_count} projects have implementing partners. Total zero-dollar funding rows currently: {zero_count}")

