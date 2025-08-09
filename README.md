<img src="https://raw.githubusercontent.com/wger-project/wger/master/wger/core/static/images/logos/logo.png" width="100" height="100" alt="wger logo" />


# docker compose stacks for wger
Contains 3 docker compose environments:

* prod (in root of this repository)
* dev (uses sqlite)
* dev-postgres (uses postgresql)

The production Docker Compose file initializes a production environment with the
application server, a reverse proxy, a database, a caching server, and a Celery
queue, all configured. Data is persisted in volumes, if you want to use folders,
read the warning in the env file.

**TLDR:** just do `docker compose up -d`

For more details, consult the documentation (and the config files):

* production: <https://wger.readthedocs.io/en/latest/production/docker.html>
* development: <https://wger.readthedocs.io/en/latest/development/docker.html>

It is recommended to regularly pull the latest version of the compose file,
since sometimes new configurations or environmental variables are added.

## Contact

Feel free to contact us if you found this useful or if there was something that
didn't behave as you expected. We can't fix what we don't know about, so please
report liberally. If you're not sure if something is a bug or not, feel free to
file a bug anyway.

* Mastodon: <https://fosstodon.org/@wger>
* Discord: <https://discord.gg/rPWFv6W>
* Issue tracker: <https://github.com/wger-project/docker/issues>


## Sources

All the code and the content is freely available:

* <https://github.com/wger-project/>

## Licence

The application is licenced under the Affero GNU General Public License 3 or
later (AGPL 3+).



## wger + wearipedia Cronometer sync

### what this adds

- goal: daily pull from Cronometer and track in your self-hosted wger (exercise + nutrition), with safe, idempotent writes.
- components:
  - wger services: web, db, cache, nginx, celery_worker, celery_beat
  - cronometer_sync sidecar (`sync/cronometer`): Python 3.11 + wearipedia; supercronic schedules runs; posts weight entries to wger and logs full payload for future ingest

### configuration (`config/prod.env`)

- CRONOMETER_SOURCE=WEARIPEDIA
- CRONOMETER_EMAIL, CRONOMETER_PASSWORD
- CRONOMETER_RANGE_DAYS (default 3), CRONOMETER_CRON (default `0 3 * * *`)
- WGER_API_URL=http://web:8000, WGER_API_TOKEN=<token>

### data flow

- sidecar authenticates to Cronometer via wearipedia
- fetches window: dailySummary, servings, exercises, biometrics
- posts weight biometrics to wger `api/v2/weightentry/`:
  - converts lbs→kg
  - idempotent by date (skips if an entry exists)
  - requires `Authorization: Token <WGER_API_TOKEN>`
- logs the full fetched payload (for later bulk nutrition ingest)

### scheduling

- supercronic reads CRONOMETER_CRON; default 03:00 daily

### manual run + logs

- run now: `docker compose exec -T cronometer_sync python /app/main.py`
- logs: `docker compose logs --tail=200 cronometer_sync`

### token (self-hosted)

Generate once:

```
docker compose exec -T web python3 manage.py shell -c 'from django.contrib.auth import get_user_model; from rest_framework.authtoken.models import Token; u=get_user_model().objects.get(username="admin"); t,_=Token.objects.get_or_create(user=u); print(t.key)'
```

Set `WGER_API_TOKEN` in `config/prod.env`.

### next steps (nutrition)

- Add a custom endpoint (`/api/v2/external/cronometer-ingest/`) to validate, enqueue, and upsert nutrition diary entries in bulk; or map to existing endpoints (`nutritiondiary`, `meal`, `mealitem`).

