-- Launch the Locher songs development environment in stacked iTerm panes.

set projectRoot to "/Users/benjaminlocher/projects/music"
set activateVenv to "source " & quoted form of (projectRoot & "/.venv/bin/activate")
set loadProjectEnv to "set -a; [ -f " & quoted form of (projectRoot & "/.env") & " ] && . " & quoted form of (projectRoot & "/.env") & "; set +a"
set localRedisUrl to "export REDIS_URL=${REDIS_URL:-redis://127.0.0.1:6381/3}"

-- Only stop listeners on ports reserved for this local development window.
set freeBackendPort to "pids=$(lsof -t -iTCP:8000 -sTCP:LISTEN 2>/dev/null || true); [ -z \"$pids\" ] || kill $pids 2>/dev/null || true"
set freeFrontendPort to "pids=$(lsof -t -iTCP:5173 -sTCP:LISTEN 2>/dev/null || true); [ -z \"$pids\" ] || kill $pids 2>/dev/null || true"
set freeRedisPort to "pids=$(lsof -t -iTCP:6381 -sTCP:LISTEN 2>/dev/null || true); [ -z \"$pids\" ] || kill $pids 2>/dev/null || true"

tell application "Finder"
	set screenBounds to bounds of window of desktop
	set screenWidth to item 3 of screenBounds
	set screenHeight to item 4 of screenBounds
end tell

tell application "iTerm"
	activate

	-- Close the previous Locher songs development window to avoid duplicates.
	set windowList to windows
	repeat with existingWindow in windowList
		try
			set sessionList to sessions of current tab of existingWindow
			repeat with existingSession in sessionList
				tell existingSession
					set locherSongsSession to variable named "user.LocherSongsSession"
					if locherSongsSession is not missing value then
						close existingWindow
						exit repeat
					end if
				end tell
			end repeat
		end try
	end repeat

	set devWindow to (create window with default profile)
	set bounds of devWindow to {0, 0, screenWidth * 0.75, screenHeight}

	-- Pane 1: local Redis broker on a project-specific port.
	tell current session of devWindow
		set variable named "user.LocherSongsSession" to "Redis"
		set name to "Locher songs Redis"
		write text "cd " & quoted form of projectRoot
		write text activateVenv
		write text freeRedisPort
		write text "redis-server --port 6381 --save '' --appendonly no"
		set backendPane to (split horizontally with default profile)
	end tell

	-- Pane 2: Django API with hot reload.
	tell backendPane
		set variable named "user.LocherSongsSession" to "Backend"
		set name to "Locher songs Backend"
		write text "cd " & quoted form of projectRoot
		write text activateVenv
		write text loadProjectEnv
		write text localRedisUrl
		write text freeBackendPort
		write text "python backend/manage.py migrate && python backend/manage.py runserver 127.0.0.1:8000"
		set frontendPane to (split horizontally with default profile)
	end tell

	-- Pane 3: Vite frontend with hot module reload.
	tell frontendPane
		set variable named "user.LocherSongsSession" to "Frontend"
		set name to "Locher songs Frontend"
		write text "cd " & quoted form of projectRoot
		write text activateVenv
		write text loadProjectEnv
		write text localRedisUrl
		write text freeFrontendPort
		write text "npm run dev --prefix frontend"
		set queuePane to (split horizontally with default profile)
	end tell

	-- Pane 4: Celery queue worker, waiting briefly for Redis to be ready.
	tell queuePane
		set variable named "user.LocherSongsSession" to "Queue"
		set name to "Locher songs Queue"
		write text "cd " & quoted form of projectRoot
		write text activateVenv
		write text loadProjectEnv
		write text localRedisUrl
		write text "until nc -z 127.0.0.1 6381; do sleep 0.2; done; celery --workdir backend -A config worker --loglevel=INFO"
		set workingPane to (split horizontally with default profile)
	end tell

	-- Pane 5: basic project shell.
	tell workingPane
		set variable named "user.LocherSongsSession" to "Working"
		set name to "Locher songs Working Session"
		write text "cd " & quoted form of projectRoot
		write text activateVenv
		write text loadProjectEnv
		write text localRedisUrl
		write text "git status"
	end tell

	-- Leave the frontend pane selected so its local URL is easy to spot.
	select frontendPane
end tell

try
	do shell script "sleep 2; open -a 'Google Chrome' 'http://localhost:5173/' > /dev/null 2>&1 &"
end try
