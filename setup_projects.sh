#!/bin/bash
# Run this once from ~/rcla_project_map to create the project folder structure.
# It will NOT overwrite any files.json that already exists.

PROJECT_IDS=(
  GG1871794
  GG2352598
  GG2346063
  GG2091778
  GG2125241
  GG1873788
  GG1870757
  Covid2020
  GG1985748
  BarAlto
  GG1529575
  Rostock_Patanatic
  GG2459764
  GG2567164
  GG2570080
  GG2574529
  GG2570516
  ADP_Panimaquip
  GG2684872
  GG2684482
)

for id in "${PROJECT_IDS[@]}"; do
  dir="projects/$id"
  mkdir -p "$dir"
  if [ ! -f "$dir/files.json" ]; then
    echo '{"files": [], "links": []}' > "$dir/files.json"
    echo "Created $dir/files.json"
  else
    echo "Skipped $dir/files.json (already exists)"
  fi
done

echo ""
echo "Done. Drop PDFs and photos into each projects/<id>/ folder,"
echo "then update files.json in that folder to list them."
