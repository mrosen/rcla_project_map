# rcla_project_map
map of projects for Rotary Club of Lake Atitlan


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
  
  *** Don't forget to modify index.html to reference the local copy of main.js! ***
