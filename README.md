# SE GPS Navigator — Web Map

## Run it locally

1. Open this folder in Windows Explorer.
2. Double-click `start-server.bat`.
3. Keep the server window open.
4. In your browser, open:

   `http://127.0.0.1:8765/index.html`

On the first visit, create the administrator account. After that, sign in normally.

## If the server does not start

Install the MySQL Python driver, then run `start-server.bat` again:

```powershell
py -m pip install pymysql
```

## Connect your GPS database

After signing in as a **Leader** or **Admin**, click **Connect MySQL** in the top bar and enter your database IP, port, username, password, and database name.

## Stop the web map

Close the server window, or press `Ctrl+C` inside it.

## Access levels

- **User** — view map data.
- **Trusted** — manage GPS markers.
- **Council** — manage region and cluster details.
- **Leader** — connect MySQL.
- **Admin** — manage users and permissions.
