# Spatial Atlas prototype

Start the local bridge, then open `http://127.0.0.1:8765/index.html` in a browser. The Atlas uses the bridge for MySQL access and Atlas account access control.

Included now:

- orbitable 3D perspective map with grid, stars, cluster volumes, and labeled nodes
- search and filters for all, ore, and station records
- node inspector with coordinates and notes
- zoom, reset view, and “locate” controls
- add-location modal for local browser-session data
- local Atlas accounts with User, Trusted, Council, Leader, and Admin levels

## Importing the MySQL GPS list

1. Install the Python driver if needed: `pip install pymysql`
2. Start the local bridge from this folder by double-clicking `start-server.bat` (or run `C:\Users\kami\AppData\Local\Programs\Python\Python313\python.exe server.py`)
3. Open or refresh `index.html`.

The bridge reads the same `~/.se_gps_navigator/db_config.json` file and `SE_GPS_DB_*` environment variables as the original navigator. Database credentials never enter the browser. The map shows `MYSQL CONNECTED` when the import succeeds.

## Atlas user access

On the first visit, create the initial administrator account. There is no built-in password. After signing in, administrators can open **Manage access** in the top bar to create accounts, change roles, reset passwords, disable accounts, or delete accounts.

- **User** — view the shared map and GPS information.
- **Trusted** — User permissions plus GPS add, edit, and delete controls.
- **Council** — Trusted permissions plus local region and cluster naming/description curation.
- **Leader** — Council permissions plus MySQL connection control.
- **Admin** — Leader permissions plus account and permission management.

Existing Viewer accounts are automatically promoted to User, Editors to Trusted, and Admins remain Admin when the bridge starts.

### Shared visibility

GPS markers, clusters, and regions have a **Visible to** setting in their edit form. The selected level is the minimum level that can receive the item: **User** makes it visible to everyone, while **Leader** makes it visible only to Leaders and Admins. A GPS must pass its own visibility plus its parent cluster and region visibility before it is sent to a user.

Account records and securely salted password hashes are stored only on the machine running the local bridge, in `~/.se_gps_navigator/atlas_access.sqlite3`. Sessions expire after seven days.
