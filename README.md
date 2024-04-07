# Map of Projects for Rotary Club of Lake Atitlan (rcla_project_map)

## Project Map Maintenance Notes
To facilitate discussions about club projects, we maintain an online map of those projects.  It shows where and what they are.  You can visit the map directly here:  https://mrosen.github.io/rcla_project_map/index.html.  It is integrated into the club's website also.

The map is a custom application built  using the GoogleMaps API.  It runs out of my github account.  This is important because that dictates how we update the map.  All the projects the map shows come from a “CSV” file that lists one row for each project displayed.  To maintain that file, we use an excel spreadsheet. Both of those files are stored in github.  To update the map:
- Use Excel or Calc to update the RCLA_Projects_Formatted.xlsx  as needed.  Each row is a different project.
- Export the excel spreadsheet as “RCLA_Projects.csv”  Use the UTF8 option.
- “Add” both of these changes to git
- “Push” your changes back to the github server.

From there on, it’s all automatic.  If you make a mistake, you’ll see it on the map.  

### How to Get Started
- Create a GitHub Account.  It’s free
- Clone this rcla_project_map repo:  https://github.com/mrosen/rcla_project_map

The result of cloning the repo is that you'll have all those files locally.  Do your editing in Excel, save your work (overwritting the earlier version of the file) and when you're done, export to CSV (again overwriting)

### How to "push" the changes back to github
  - "git add RCLA_Projects.csv RCLA_Projects_Formatted.xlsx"
  - "git commit -m 'udate ...'"
  - "git push"


========================================================

Currently uses my personal Google Maps API key.

Here's where I can see the billing
  https://console.cloud.google.com/billing/0166F7-B38A06-FF1322?project=elite-hangar-388623

Here's the Github Repo where I keep all this.
  https://github.com/mrosen/rcla_project_map

It uses GitHub Pages to host the site:
  https://mrosen.github.io/rcla_project_map/index.html
  After you push, you may need to visit the file on repo to coax a refresh.  For example, https://github.com/mrosen/rcla_project_map/blob/main/RCLA_Projects.csv

To reference from Windows assuming checkout via WSL:
  \\wsl.localhost\Ubuntu\home\mrosen\rcla_project_map

To test locally, 
  python3 -m http.server
  http://localhost:8000/
  
  **********************************
  Don't forget to modify index.html to reference the local copy of main.js!

  The data is managed in the Excel spreadsheet.  That we export to the CSV file (Unicode, UTF8)
