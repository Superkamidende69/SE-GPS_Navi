# Spatial Atlas — SE GPS Navigator

Spatial Atlas is a local web map for Space Engineers GPS data. It turns the GPS entries in the Navigator MySQL database into an interactive 3D map with regions, clusters, permissions, nearby scanning, and navigation tools.

## Start the atlas

### Requirements

- Windows
- Python 3 available as `py` or `python`
- The MySQL driver:

  ```powershell
  py -m pip install pymysql
  ```

### Run locally

1. Open this folder in Windows Explorer.
2. Double-click [start-server.bat](start-server.bat).
3. Keep that command window open while using the atlas.
4. Open [http://127.0.0.1:8765/index.html](http://127.0.0.1:8765/index.html) in your browser.
5. On the first visit, create the administrator account. After that, sign in with an Atlas account.

Do not open `index.html` directly with `file:///`. The local server provides sign-in, permissions, and the MySQL bridge.

To stop the atlas, close the server window or press `Ctrl+C` in it.

## Connect MySQL

After signing in as a **Leader** or **Admin**, select **Connect MySQL** in the top bar. Enter the database host/IP, port, username, password, and database name.

The map expects the existing Navigator tables:

- `entries` — GPS entries, including `id`, `name`, `x`, `y`, `z`, `ore_type`, `description`, `cluster_id`, `report_count`, and `location_type`.
- `clusters` — cluster names and centres (`id`, `name`, `center_x`, `center_y`, `center_z`).

If `entries` has a `created_at`, `added_at`, or `created` column, Spatial Atlas displays it as the GPS-added timestamp. No database table is altered just to display that date.

The web map checks MySQL for updates every 10 seconds while the browser tab is visible. The current view, selected item, measurement origin, and map position are kept during sync.

### Credentials and local files

Credentials entered in the connection window are used for the active local server session. They are not stored in this repository. Optional local configuration and Atlas access data live under your Windows user profile in `.se_gps_navigator`, outside the project folder.

## Features

### 3D spatial map

- 3D map projection with mouse rotation, middle-mouse panning, wheel zoom, reset/centre controls, and a Blender-style view cube.
- Rotating deep-space skybox with nebula haze, dust, and layered stars.
- Optional map layers for the skybox, grid planes, regions, clusters, GPS signals, and your temporary location.
- Account-synced route hazard volumes for danger, pirate patrols, gravity wells, no-fly zones, and cautions. Add a GPS centre and radius, then toggle them with the **Route hazards** map layer.
- Hover cards for regions, clusters, and individual GPS markers.
- Click through the hierarchy: **region → cluster → GPS**. Use the back control to return to the wider map.
- Main-map switch between regional grouping and an all-clusters view.

### Regions and clusters

- Clusters are automatically gathered into regions within a 1,000 km range.
- Each generated region receives its own distinct place name. Legacy repeated generated names are automatically replaced.
- Region editing supports name, description, color, point symbol, visibility, owner/faction, and ownership status.
- Cluster editing supports name, description, color, point symbol, and visibility.
- Region and cluster descriptions can show a resource summary based on asteroid GPS entries.
- Selected regions include a statistics panel for clusters, GPS signals, asteroid signals, distinct resources, mapped span, and the newest timestamped GPS entry.
- Shared notes are available on regions, clusters, and individual GPS points. Everyone permitted to view an item can read its notes; **Trusted** users and above can add timestamped notes under their Atlas identity.

Region and cluster presentation details—such as names, descriptions, colors, symbols, and ownership—are saved with the signed-in Atlas account on the local server. They follow that account between browsers connected to the same Atlas server. Visibility rules are also stored by the local Atlas server. Neither rewrites the MySQL GPS tables.

### GPS atlas

- Search and filter GPS points by **All**, **Asteroid**, **Station**, **Planet**, **Base**, **Unknown** (including Strong), and **Other**.
- Add a local temporary GPS by pasting a Space Engineers GPS string, choosing its type, and adding a description. New local GPS points receive an added timestamp; they are not saved to MySQL.
- Edit imported GPS name, coordinates, type, description, color, symbol, and visibility. When MySQL is connected, coordinate/type/description edits are written back to MySQL; color/symbol settings follow the signed-in Atlas account and visibility stays in Atlas access data.
- Copy a selected GPS to the clipboard.
- Remove a GPS marker from the current map session. Imported MySQL records return after the next sync or page reload unless deleted from the source database.
- Measure the straight-line distance between two GPS points in kilometres.
- Add GPS points to an account-synced favorites list.
- Auto-group coded ore GPS names such as `P3X-664 Ice` and `P3X-664 Fe` only when they are within 1 km of the first GPS position; distant signals remain separate.
- Resource Finder lists every imported asteroid resource, filters the atlas to that material, and focuses the nearest matching GPS once a temporary current location is set. The regular search also recognizes common ore names and symbols, such as `iron` / `Fe`, `nickel` / `Ni`, and `uranium` / `U`.

### Position, scanner, and alerts

- Use **Show my location** to paste a temporary current GPS marker; it is not saved to MySQL.
- Nearby scanner with selectable ranges from 5 km to 250 km.
- Proximity alerts for nearby stations, homes/bases, and danger markers. Alerts can be paused and use a separate 5–100 km range.
- Click a scanner or alert result to focus that GPS on the map.

### Activity and permissions

- Change Activity panel identifies GPS and cluster additions, updates, and removals detected during MySQL sync.
- Region, cluster, and GPS visibility can be limited by access level.
- Built-in user management for administrators.
- Account preferences, including favorites, labels, colors, symbols, map layers, route hazards, scanner settings, alerts, and auto-grouping, are saved to the local server so they load in another browser signed in to the same account.

Access levels:

- **User** — view permitted map data.
- **Trusted** — manage permitted GPS markers.
- **Council** — manage region and cluster details.
- **Leader** — connect the MySQL database.
- **Admin** — manage users and permissions.

## Map controls

| Action | Control |
| --- | --- |
| Rotate the view | Left-click and drag |
| Pan the view | Middle-click and drag |
| Travel/zoom | Mouse wheel, zoom buttons, or slider |
| Select a map item | Left-click its visible marker |
| Return to a wider map | Use the back button |
| Centre the view | Centre control or the view cube home face |
| Toggle visual layers | **Layers** in the map toolbar |

## Troubleshooting

### The server will not start

Install Python 3 and ensure `py` or `python` is on your PATH. Then install the required driver:

```powershell
py -m pip install pymysql
```

### MySQL says offline or fails to connect

- Confirm the server window is still open.
- Confirm MySQL is reachable from this PC and the IP/port are correct.
- Check the MySQL username, password, and database name.
- Confirm the account has permission to read `entries` and `clusters`; GPS editing also needs permission to update `entries`.

### The page looks out of date

Refresh the browser tab. Restart [start-server.bat](start-server.bat) after changing [server.py](server.py).
