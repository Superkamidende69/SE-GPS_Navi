# Spatial Atlas prototype

Open `index.html` in a browser. The current build is a self-contained visual prototype with demo data derived from `se_gps_navigator.py`.

Included now:

- orbitable 3D perspective map with grid, stars, cluster volumes, and labeled nodes
- search and filters for all, ore, and station records
- node inspector with coordinates and notes
- zoom, reset view, and “locate” controls
- add-location modal for local browser-session data

## Importing the MySQL GPS list

1. Install the Python driver if needed: `pip install pymysql`
2. Start the local bridge from this folder by double-clicking `start-server.bat` (or run `C:\Users\kami\AppData\Local\Programs\Python\Python313\python.exe server.py`)
3. Open or refresh `index.html`.

The bridge reads the same `~/.se_gps_navigator/db_config.json` file and `SE_GPS_DB_*` environment variables as the original navigator. It exposes a read-only local endpoint, so database credentials never enter the browser. The map shows `MYSQL CONNECTED` when the import succeeds and `DEMO FALLBACK` otherwise.
